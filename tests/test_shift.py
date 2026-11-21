import json
import textwrap
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from fast_chimera.cli import dependencies
from fast_chimera.cli.app import app as cli_app
from fast_chimera.core.exceptions import ShiftConfigError, ShiftError
from fast_chimera.shift.extraction import FingerprintExtractor
from fast_chimera.shift.publishing import ShiftPublisher, ShiftSettings, display_url

FILES = {
    "app/__init__.py": "",
    "app/deps.py": """
        def get_db(): ...
        def get_current_user(): ...
        def verify_api_key(): ...
        def require_admin(): ...
        def require_owner(): ...
        def rate_limit(): ...
        def audit(): ...
    """,
    "app/main.py": """
        from fastapi import Depends, FastAPI
        from fastapi.middleware.cors import CORSMiddleware

        from app.deps import require_admin, verify_api_key
        from app.routers import products, vendors
        from app.routers.admin import router as admin_router

        app = FastAPI(title="Shop", dependencies=[Depends(verify_api_key)])
        app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True)


        @app.middleware("http")
        async def add_timing(request, call_next):
            return await call_next(request)


        app.include_router(vendors.router, prefix="/api/v1")
        app.include_router(products.router, prefix="/api/v1")
        app.include_router(admin_router, prefix="/admin", dependencies=[Depends(require_admin)])


        @app.get("/health")
        def health():
            return {"status": "ok"}
    """,
    "app/schemas.py": """
        from pydantic import BaseModel


        class VendorCreate(BaseModel):
            name: str


        class VendorRead(VendorCreate):
            id: int
    """,
    "app/routers/__init__.py": "",
    "app/routers/vendors.py": """
        from typing import Annotated

        from fastapi import APIRouter, Depends, Query, status

        from app.deps import get_current_user, get_db
        from app.schemas import VendorCreate, VendorRead

        router = APIRouter(prefix="/vendors", tags=["vendors"])


        @router.post("", response_model=VendorRead, status_code=status.HTTP_201_CREATED)
        def create_vendor(payload: VendorCreate, db=Depends(get_db), user=Depends(get_current_user)): ...


        @router.get("/{vendor_id}", response_model=VendorRead)
        def get_vendor(vendor_id: int, include_products: bool = False, db: Annotated[object, Depends(get_db)] = None): ...


        @router.get("", response_model=list[VendorRead])
        def list_vendors(limit: int = Query(10, le=100), q: str | None = None): ...
    """,
    "app/routers/products.py": """
        from fastapi import APIRouter, Depends, UploadFile

        from app.deps import rate_limit, require_owner

        router = APIRouter(prefix="/products", tags=["products"], dependencies=[Depends(rate_limit)])


        @router.delete("/{product_id}", status_code=204, dependencies=[Depends(require_owner)])
        def delete_product(product_id: int): ...


        @router.post("/upload")
        async def upload(file: UploadFile): ...


        @router.websocket("/ws")
        async def feed(ws): ...


        @router.get(some_dynamic_path)
        def dynamic(): ...
    """,
    "app/routers/admin/__init__.py": """
        from fastapi import APIRouter

        from app.routers.admin import reports

        router = APIRouter(prefix="/reports-root")
        router.include_router(reports.router, prefix="/r")


        @router.get("/stats")
        def stats(): ...
    """,
    "app/routers/admin/reports.py": """
        from fastapi import APIRouter, Depends

        from app.deps import audit

        router = APIRouter(prefix="/reports", dependencies=[Depends(audit)])


        @router.get("/sales")
        def sales(): ...
    """,
    "app/models.py": """
        import enum
        from datetime import datetime
        from decimal import Decimal

        from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Table, UniqueConstraint
        from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

        FLAG = True


        class Base(DeclarativeBase):
            pass


        class Status(enum.Enum):
            draft = "draft"


        class TimestampMixin:
            created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


        product_tags = Table(
            "product_tags",
            Base.metadata,
            Column("product_id", ForeignKey("products.id"), primary_key=True),
            Column("tag_id", ForeignKey("tags.id"), primary_key=True),
        )


        class Vendor(TimestampMixin, Base):
            __tablename__ = "vendors"
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column(String(120), unique=True)
            website: Mapped[str | None] = mapped_column(String(255))
            api_secret: Mapped[str] = mapped_column(String(64), default="s3cr3t-value")
            is_active: Mapped[bool] = mapped_column(Boolean, default=True)
            products: Mapped[list["Product"]] = relationship(back_populates="vendor")
            profile: Mapped["Profile"] = relationship(back_populates="vendor")


        class Product(Base):
            __tablename__ = "products"
            __table_args__ = (UniqueConstraint("vendor_id", "sku", name="uq_vendor_sku"), Index("ix_products_title", "title"))
            id: Mapped[int] = mapped_column(primary_key=True)
            vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id", ondelete="CASCADE"))
            sku: Mapped[str] = mapped_column(String(40))
            title: Mapped[str] = mapped_column(String(200), nullable=FLAG)
            price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
            status: Mapped[Status] = mapped_column(Enum("draft", "live", name="status"))
            vendor: Mapped["Vendor"] = relationship(back_populates="products")
            tags: Mapped[list["Tag"]] = relationship(secondary=product_tags, back_populates="products")


        class Tag(Base):
            __tablename__ = "tags"
            id = Column(Integer, primary_key=True)
            label = Column(String(50), nullable=False, unique=True)
            notes = Column(String)
            products = relationship("Product", secondary=product_tags, back_populates="tags")


        class Profile(Base):
            __tablename__ = "profiles"
            id: Mapped[int] = mapped_column(primary_key=True)
            vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), unique=True)
            vendor: Mapped["Vendor"] = relationship(back_populates="profile")


        class Weird(Base):
            __tablename__ = compute_name()
    """,
    "tests/test_ignored.py": """
        from fastapi import APIRouter
        router = APIRouter()

        @router.get("/should-not-appear")
        def nope(): ...
    """,
    "broken.py": "def (:",
}


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    for rel, content in FILES.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")
    return tmp_path


@pytest.fixture()
def fp(project):
    return FingerprintExtractor(project).extract()


def table(fp, name):
    return next(t for t in fp.tables if t.name == name)


def column(fp, tname, cname):
    return next(c for c in table(fp, tname).columns if c.name == cname)


def endpoint(fp, method, path):
    return next(e for e in fp.endpoints if e.method == method and e.path == path)


# ------------------------------------------------------------------ tables
def test_tables_and_association_tables(fp):
    assert {t.name for t in fp.tables} == {"vendors", "products", "tags", "profiles", "product_tags"}
    pivot = table(fp, "product_tags")
    assert pivot.kind == "association"
    assert [(c.name, c.foreign_key, c.primary_key) for c in pivot.columns] == [
        ("product_id", "products.id", True),
        ("tag_id", "tags.id", True),
    ]


def test_columns_types_nullability_and_mixins(fp):
    assert column(fp, "vendors", "id").model_dump() | {} == {
        "name": "id",
        "type": "integer",
        "nullable": False,
        "primary_key": True,
        "unique": False,
        "index": False,
        "foreign_key": None,
        "on_delete": None,
    }
    assert column(fp, "vendors", "name").type == "string(120)" and column(fp, "vendors", "name").unique
    assert column(fp, "vendors", "website").nullable is True  # Mapped[str | None]
    assert column(fp, "vendors", "is_active").type == "boolean"
    created = column(fp, "vendors", "created_at")  # inherited from TimestampMixin
    assert (created.type, created.nullable) == ("datetime", False)
    assert column(fp, "products", "price").type == "decimal(12,2)"
    assert column(fp, "products", "status").type == "enum(draft,live)"
    fk = column(fp, "products", "vendor_id")
    assert (fk.foreign_key, fk.on_delete) == ("vendors.id", "CASCADE")
    # classic Column() style
    assert column(fp, "tags", "label").model_dump(exclude_none=True)["nullable"] is False
    assert column(fp, "tags", "notes").type == "string" and column(fp, "tags", "notes").nullable is True


def test_table_level_constraints(fp):
    products = table(fp, "products")
    assert products.unique_constraints == [["vendor_id", "sku"]]
    assert [(i.name, i.columns) for i in products.indexes] == [("ix_products_title", ["title"])]


def test_relationship_kinds(fp):
    rel = lambda t, n: next(r for r in table(fp, t).relations if r.name == n)  # noqa: E731
    assert rel("vendors", "products").type == "has_many"
    assert rel("vendors", "profile").type == "has_one"
    assert rel("profiles", "vendor").type == "belongs_to"
    vendor = rel("products", "vendor")
    assert (vendor.type, vendor.target_table, vendor.back_populates) == ("belongs_to", "vendors", "products")
    tags = rel("products", "tags")
    assert (tags.type, tags.through, tags.target_table) == ("many_to_many", "product_tags", "tags")
    assert rel("tags", "products").type == "many_to_many"  # classic relationship("Product", secondary=...)


# ------------------------------------------------------------------ endpoints
def test_prefixes_status_and_body(fp):
    create = endpoint(fp, "POST", "/api/v1/vendors")
    assert (create.status_code, create.response_model, create.request_body) == (201, "VendorRead", "VendorCreate")
    assert create.injects == ["get_db", "get_current_user"] and create.tags == ["vendors"]
    assert create.module == "app.routers.vendors" and create.guards == []
    assert endpoint(fp, "GET", "/health").mounted is True


def test_params_locations_and_requiredness(fp):
    get = endpoint(fp, "GET", "/api/v1/vendors/{vendor_id}")
    by_name = {p.name: p for p in get.params}
    assert (by_name["vendor_id"].location, by_name["vendor_id"].required, by_name["vendor_id"].type) == ("path", True, "int")
    assert (by_name["include_products"].location, by_name["include_products"].required) == ("query", False)
    assert get.injects == ["get_db"]  # Annotated[..., Depends(get_db)]
    listing = endpoint(fp, "GET", "/api/v1/vendors")
    assert listing.response_model == "list[VendorRead]"
    assert {p.name for p in listing.params} == {"limit", "q"}
    assert endpoint(fp, "POST", "/api/v1/products/upload").params[0].location == "file"


def test_guards_websocket_and_nested_routers(fp):
    delete = endpoint(fp, "DELETE", "/api/v1/products/{product_id}")
    assert [(g.name, g.scope) for g in delete.guards] == [("rate_limit", "router"), ("require_owner", "endpoint")]
    assert delete.status_code == 204
    assert endpoint(fp, "WEBSOCKET", "/api/v1/products/ws")
    stats = endpoint(fp, "GET", "/admin/reports-root/stats")
    assert [(g.name, g.scope) for g in stats.guards] == [("require_admin", "router")]
    sales = endpoint(fp, "GET", "/admin/reports-root/r/reports/sales")
    assert [g.name for g in sales.guards] == ["require_admin", "audit"]


def test_global_middleware_lists_names_but_never_values(fp):
    by_name = {m.name: m for m in fp.middleware}
    assert by_name["verify_api_key"].kind == "dependency"
    assert by_name["CORSMiddleware"].options == ["allow_credentials", "allow_origins"]
    assert by_name["add_timing"].kind == "http"
    assert "verify_api_key" not in [g.name for e in fp.endpoints for g in e.guards]  # global: listed once


# ------------------------------------------------------------------ honesty and safety
def test_unresolved_is_reported_and_tests_are_ignored(fp):
    notes = " | ".join(fp.unresolved)
    assert "__tablename__ is not a constant" in notes
    assert "'nullable' is not a constant" in notes
    assert "route path is not a constant" in notes
    assert "broken.py: skipped" in notes
    assert not any("should-not-appear" in e.path for e in fp.endpoints)


def test_fingerprint_has_no_source_or_values_and_hash_is_stable(project, fp):
    text = fp.to_json()
    assert "s3cr3t-value" not in text and "def " not in text and '"*"' not in text
    assert FingerprintExtractor(project).extract().content_sha256 == fp.content_sha256
    models = project / "app/models.py"
    models.write_text(models.read_text().replace("String(40)", "String(41)"))
    assert FingerprintExtractor(project).extract().content_sha256 != fp.content_sha256


# ------------------------------------------------------------------ settings and publisher
def settings(**kw):
    return ShiftSettings(_env_file=None, **kw)


@pytest.mark.parametrize(
    "url", ["http://platform.example.com/x", "https://user:pw@platform.example.com/x", "ftp://x.com/y", "platform.example.com/x"]
)
def test_unsafe_server_urls_are_rejected(url):
    with pytest.raises(ShiftConfigError):
        settings(shift_server_url=url).server_url()


def test_safe_server_urls():
    assert settings(shift_server_url="https://p.example.com/api/shift").server_url()
    assert settings(shift_server_url="http://localhost:9000/in").server_url()
    assert settings(shift_server_url="http://p.example.com/x", shift_allow_insecure=True).server_url()
    assert settings(shift_server_url="  ").server_url() is None
    assert display_url("https://p.example.com/x?token=abc#frag") == "https://p.example.com/x"


def make_publisher(handler, **kw):
    return ShiftPublisher(settings(**kw), transport=httpx.MockTransport(handler), sleep=lambda s: None)


def test_send_posts_json_with_auth_and_idempotency_headers(fp):
    seen = {}

    def handler(request: httpx.Request):
        seen["req"] = request
        return httpx.Response(201, json={"id": "fp_123"})

    result = make_publisher(handler, shift_server_url="https://p.example.com/api/shift", shift_api_token="tok-1").send(fp)
    req = seen["req"]
    assert (result.status_code, result.remote_id, result.attempts) == (201, "fp_123", 1)
    assert req.method == "POST" and str(req.url) == "https://p.example.com/api/shift"
    assert req.headers["authorization"] == "Bearer tok-1"
    assert req.headers["idempotency-key"] == fp.content_sha256 == req.headers["x-fastchimera-content-sha256"]
    body = json.loads(req.content)
    assert body["project"] == fp.project and len(body["endpoints"]) == len(fp.endpoints)


def test_send_retries_transient_failures_then_succeeds(fp):
    answers = iter([httpx.Response(503), httpx.Response(429), httpx.Response(200)])
    result = make_publisher(lambda r: next(answers), shift_server_url="https://p.example.com/in").send(fp)
    assert result.attempts == 3


def test_client_errors_are_not_retried_and_token_never_leaks(fp):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(401, text="invalid token")

    with pytest.raises(ShiftError, match="HTTP 401") as err:
        make_publisher(handler, shift_server_url="https://p.example.com/in", shift_api_token="super-secret").send(fp)
    assert len(calls) == 1 and "super-secret" not in str(err.value)


def test_redirects_are_not_followed(fp):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(301, headers={"Location": "http://evil.example.com/steal"})

    with pytest.raises(ShiftError, match="redirected"):
        make_publisher(handler, shift_server_url="https://p.example.com/in", shift_api_token="tok").send(fp)
    assert calls == ["https://p.example.com/in"]


def test_gives_up_after_configured_attempts(fp):
    calls = []

    def handler(request):
        calls.append(1)
        raise httpx.ConnectError("down")

    with pytest.raises(ShiftError, match="after 2 attempt"):
        make_publisher(handler, shift_server_url="https://p.example.com/in", shift_retry_attempts=2).send(fp)
    assert len(calls) == 2


def test_send_without_configured_server_explains_what_to_do(fp):
    with pytest.raises(ShiftConfigError, match="SHIFT_SERVER_URL"):
        make_publisher(lambda r: httpx.Response(200)).send(fp)


# ------------------------------------------------------------------ the CLI command
runner = CliRunner()


@pytest.fixture()
def clean_env(monkeypatch, tmp_path_factory):
    for key in ("SHIFT_SERVER_URL", "SHIFT_API_TOKEN", "SHIFT_ALLOW_INSECURE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))


def patch_server(monkeypatch, handler):
    monkeypatch.setattr(
        dependencies, "create_publisher", lambda s: ShiftPublisher(s, transport=httpx.MockTransport(handler), sleep=lambda _: None)
    )


def flat(result) -> str:
    return " ".join(result.output.split())


def test_shift_saves_locally_and_sends_to_server_from_dotenv(project, clean_env, monkeypatch):
    (project / ".env").write_text("SHIFT_SERVER_URL=http://localhost:9999/api/shift\nSHIFT_API_TOKEN=tok-abc\nSECRET_KEY=x\n")
    seen = []
    patch_server(monkeypatch, lambda r: (seen.append(r), httpx.Response(200, json={"id": 7}))[1])

    result = runner.invoke(cli_app, ["shift", str(project)])
    assert result.exit_code == 0, result.output
    saved = json.loads((project / "fast-chimera.shift.json").read_text())
    assert saved["framework"] == "fastapi" and saved["tables"]
    assert len(seen) == 1 and seen[0].headers["authorization"] == "Bearer tok-abc"
    assert json.loads(seen[0].content)["content_sha256"] == saved["content_sha256"]
    out = flat(result)
    assert "Sent to http://localhost:9999/api/shift" in out and "id 7" in out
    assert "tok-abc" not in out


def test_shift_without_server_only_saves(project, clean_env, monkeypatch):
    patch_server(monkeypatch, lambda r: pytest.fail("must not send"))
    result = runner.invoke(cli_app, ["shift", str(project), "-o", str(project / "out" / "fp.json")])
    assert result.exit_code == 0 and (project / "out" / "fp.json").exists()
    assert "saved locally only" in flat(result)


def test_shift_no_send_flag_and_server_override(project, clean_env, monkeypatch):
    (project / ".env").write_text("SHIFT_SERVER_URL=http://localhost:1/never\n")
    seen = []
    patch_server(monkeypatch, lambda r: (seen.append(str(r.url)), httpx.Response(200))[1])
    assert runner.invoke(cli_app, ["shift", str(project), "--no-send"]).exit_code == 0 and not seen
    runner.invoke(cli_app, ["shift", str(project), "--server", "http://localhost:2/other"])
    assert seen == ["http://localhost:2/other"]


def test_failed_send_exits_nonzero_but_keeps_the_local_file(project, clean_env, monkeypatch):
    (project / ".env").write_text("SHIFT_SERVER_URL=http://localhost:9999/in\n")
    patch_server(monkeypatch, lambda r: httpx.Response(500, text="boom"))
    result = runner.invoke(cli_app, ["shift", str(project)])
    assert result.exit_code == 1 and (project / "fast-chimera.shift.json").exists()
    assert "saved locally" in flat(result)


def test_shift_needs_no_gemini_key(project, clean_env, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert runner.invoke(cli_app, ["shift", str(project), "--no-send"]).exit_code == 0
