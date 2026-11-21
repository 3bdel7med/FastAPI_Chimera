"""A scripted LLM that plays the role of Gemini for offline, deterministic tests."""

from __future__ import annotations

import json
import re

from fast_chimera.core.interfaces import LlmClient

CATALOG = {
    "project_name": "Mini Marketplace",
    "summary": "A tiny multi-vendor marketplace",
    "modules": [
        {
            "name": "Vendors",
            "description": "Vendor accounts",
            "features": [
                {"name": "Vendor registration", "description": "Create vendors", "priority": "core"},
                {"name": "Vendor badges", "description": "Badges", "priority": "optional"},
            ],
        },
        {
            "name": "Products",
            "description": "Catalog",
            "features": [{"name": "Product listing", "description": "Vendors list products", "priority": "core"}],
        },
    ],
}
ROADMAP = {
    "phases": [
        {"id": 1, "name": "Vendors", "goal": "Vendor CRUD", "modules": ["Vendors"]},
        {"id": 2, "name": "Products", "goal": "Products owned by vendors", "modules": ["Products"]},
    ]
}
PLANS = {
    1: {
        "files": [
            {"path": "tests/test_vendors.py", "purpose": "vendor tests", "kind": "test", "depends_on": ["app/routers/vendors.py"]},
            {
                "path": "app/routers/vendors.py",
                "purpose": "vendor endpoints",
                "kind": "router",
                "depends_on": ["app/models/vendor.py", "app/schemas/vendor.py"],
            },
            {"path": "app/models/vendor.py", "purpose": "Vendor model", "kind": "model"},
            {"path": "app/schemas/vendor.py", "purpose": "Vendor schemas", "kind": "schema"},
            {"path": "../../etc/evil.py", "purpose": "path traversal attempt", "kind": "util"},
            {"path": "app/core/security.py", "purpose": "tries to replace a protected file", "kind": "util"},
        ],
        "required_packages": [],
    },
    2: {
        "files": [
            {"path": "app/models/product.py", "purpose": "Product model", "kind": "model", "depends_on": ["app/models/vendor.py"]},
            {"path": "app/schemas/product.py", "purpose": "Product schemas", "kind": "schema"},
            {
                "path": "app/routers/products.py",
                "purpose": "product endpoints",
                "kind": "router",
                "depends_on": ["app/models/product.py", "app/schemas/product.py"],
            },
            {"path": "tests/test_products.py", "purpose": "product tests", "kind": "test"},
        ],
        "required_packages": ["stripe>=7", "fastapi"],
    },
}

CODE = {
    "app/models/vendor.py": """from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
""",
    "app/schemas/vendor.py": """from pydantic import BaseModel, ConfigDict


class VendorCreate(BaseModel):
    name: str


class VendorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
""",
    "app/routers/vendors.py": """from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.vendor import Vendor
from app.schemas.vendor import VendorCreate, VendorRead

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.post("", response_model=VendorRead, status_code=201)
def create_vendor(payload: VendorCreate, db: Session = Depends(get_db)) -> Vendor:
    vendor = Vendor(name=payload.name)
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor


@router.get("", response_model=list[VendorRead])
def list_vendors(db: Session = Depends(get_db)) -> list[Vendor]:
    return list(db.scalars(select(Vendor)))
""",
    "tests/test_vendors.py": """def test_create_and_list_vendor(client):
    assert client.post("/vendors", json={"name": "Acme"}).status_code == 201
    assert client.get("/vendors").json()[0]["name"] == "Acme"
""",
    "app/models/product.py": """from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"))
    title: Mapped[str] = mapped_column(String(200))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
""",
    "app/schemas/product.py": """from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProductCreate(BaseModel):
    vendor_id: int
    title: str
    price: Decimal


class ProductRead(ProductCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
""",
    "app/routers/products.py": """from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductRead

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", response_model=ProductRead, status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)) -> Product:
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("", response_model=list[ProductRead])
def list_products(db: Session = Depends(get_db)) -> list[Product]:
    return list(db.scalars(select(Product)))
""",
    "tests/test_products.py": """def test_create_product(client):
    vendor = client.post("/vendors", json={"name": "Acme"}).json()
    resp = client.post("/products", json={"vendor_id": vendor["id"], "title": "Lamp", "price": "9.99"})
    assert resp.status_code == 201
    assert resp.json()["price"] == "9.99"
""",
}

# The first attempt for these files is deliberately broken, to exercise validation and repair.
BROKEN_FIRST = {
    # import error (typo) -> caught by the import check, then repaired from the traceback
    "app/routers/products.py": CODE["app/routers/products.py"]
    .replace("import Product\n", "import Prodcut\n")
    .replace("Product(**", "Prodcut(**"),
    # syntax error -> caught by validate_python before the file is even written
    "app/schemas/product.py": "from pydantic import BaseModel\n\nclass ProductCreate(BaseModel)\n    title: str\n",
}


class FakeLlm(LlmClient):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []  # (task, path-or-phase)
        self._served: set[str] = set()

    async def generate_text(self, prompt, system_instruction=None, *, json_mode=False, temperature=None):
        system = system_instruction or ""
        if "[task:discover]" in system:
            self.calls.append(("discover", ""))
            return json.dumps(CATALOG)
        if "[task:roadmap]" in system:
            self.calls.append(("roadmap", ""))
            return json.dumps(ROADMAP)
        if "[task:plan_phase]" in system:
            phase_id = int(re.search(r"PHASE_ID: (\d+)", prompt).group(1))
            self.calls.append(("plan_phase", str(phase_id)))
            return "```json\n" + json.dumps(PLANS[phase_id]) + "\n```"  # fenced on purpose
        if "[task:generate]" in system:
            path = re.search(r"^PATH: (.+)$", prompt, re.M).group(1)
            self.calls.append(("generate", path))
            if path in BROKEN_FIRST and path not in self._served:
                self._served.add(path)
                return f"```python\n{BROKEN_FIRST[path]}```"
            return f"```python\n{CODE[path]}```"
        if "[task:repair]" in system:
            path = re.search(r"^FILE: (.+)$", prompt, re.M).group(1)
            self.calls.append(("repair", path))
            return f"```python\n{CODE[path]}```"
        raise AssertionError(f"unexpected prompt: {system[:80]}")
