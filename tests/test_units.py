import json

import pytest

from fast_chimera.analysis.module_analyzer import find_router_variables
from fast_chimera.analysis.scanner import ProjectScanner
from fast_chimera.analysis.symbol_index import format_symbol_index
from fast_chimera.core.exceptions import FileConflictError, LlmResponseError, UnsafePathError
from fast_chimera.core.paths import normalize_relative_path, path_to_module
from fast_chimera.generation.backup import BackupService
from fast_chimera.generation.path_policy import PathPolicy
from fast_chimera.generation.validators import ValidatorChain
from fast_chimera.generation.writer import SafeWriter
from fast_chimera.injection.code_injector import CodeInjector
from fast_chimera.llm.json_extraction import extract_code, extract_json
from fast_chimera.llm.structured import generate_model
from fast_chimera.planning.file_plan import drop_unusable_files, order_by_dependencies, split_into_batches
from fast_chimera.planning.schemas import FeatureCatalog, FileSpec, PhasePlan, Roadmap
from fast_chimera.verification.traceback_parser import find_missing_module, locate_failing_file

from .fakes import CATALOG


# ------------------------------------------------------------------ paths / schemas
@pytest.mark.parametrize("bad", ["/etc/passwd.py", "../x.py", "app/../../x.py", "C:/x.py", "app/readme.md", ""])
def test_unsafe_paths_rejected(bad):
    with pytest.raises(UnsafePathError):
        normalize_relative_path(bad)


def test_path_helpers():
    assert normalize_relative_path("./app\\models/user.py") == "app/models/user.py"
    assert path_to_module("app/models/user.py") == "app.models.user"
    assert path_to_module("app/models/__init__.py") == "app.models"


def test_phase_plan_drops_unsafe_files_and_bad_packages():
    plan = PhasePlan.model_validate(
        {
            "files": [{"path": "app/a.py", "purpose": "a"}, {"path": "../evil.py", "purpose": "x"}],
            "required_packages": ["stripe>=7", "rm -rf /", "good_pkg[extra]"],
        }
    )
    assert [f.path for f in plan.files] == ["app/a.py"]
    assert plan.required_packages == ["stripe>=7", "good_pkg[extra]"]


def test_enums_are_normalized_leniently():
    spec = FileSpec.model_validate({"path": "app/a.py", "purpose": "p", "kind": "Router", "action": "modify"})
    assert (spec.kind, spec.action) == ("router", "MODIFY")
    assert FileSpec.model_validate({"path": "app/a.py", "purpose": "p", "kind": "weird"}).kind == "other"


def test_catalog_selection():
    catalog = FeatureCatalog.model_validate(CATALOG)
    assert catalog.project_name == "mini-marketplace"
    assert catalog.total_features == 3
    selected = catalog.select(exclude_modules=["products"], include_optional=False)
    assert [m.name for m in selected.modules] == ["Vendors"]
    assert selected.total_features == 1


def test_order_and_chunk():
    files = [
        FileSpec(path="tests/test_a.py", purpose="", kind="test"),
        FileSpec(path="app/routers/a.py", purpose="", kind="router", depends_on=["app/models/a.py"]),
        FileSpec(path="app/models/a.py", purpose="", kind="model"),
    ]
    assert [f.path for f in order_by_dependencies(files)] == ["app/models/a.py", "app/routers/a.py", "tests/test_a.py"]
    assert [len(b) for b in split_into_batches(files, 2)] == [2, 1]


def test_sanitize_drops_disallowed_and_dangling_dependencies():
    files = [
        FileSpec(path="app/a.py", purpose="", depends_on=["app/missing.py", "app/b.py"]),
        FileSpec(path="app/b.py", purpose=""),
        FileSpec(path="app/b.py", purpose=""),
        FileSpec(path="other/c.py", purpose=""),
    ]
    kept, dropped = drop_unusable_files(files, lambda p: p.startswith("app/"), lambda p: False)
    assert [f.path for f in kept] == ["app/a.py", "app/b.py"]
    assert kept[0].depends_on == ["app/b.py"]
    assert dropped == ["other/c.py"]


# ------------------------------------------------------------------ structured output
def test_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('Sure!\n```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('text before {"a": {"b": 2}} text after') == {"a": {"b": 2}}


def test_extract_code_picks_largest_block_or_raw_text():
    assert extract_code("x = 1") == "x = 1"
    assert extract_code("Here:\n```python\nprint('hi')\n```\nDone") == "print('hi')"


def test_generate_model_retries_with_error_feedback():
    from fast_chimera.core.interfaces import LlmClient

    class Flaky(LlmClient):
        def __init__(self):
            self.prompts = []

        async def generate_text(self, prompt, system_instruction=None, *, json_mode=False, temperature=None):
            self.prompts.append(prompt)
            return "not json" if len(self.prompts) == 1 else json.dumps({"phases": [{"name": "a", "goal": "b"}]})

    import asyncio

    llm = Flaky()
    roadmap = asyncio.run(generate_model(llm, Roadmap, "plan", "sys"))
    assert roadmap.phases[0].name == "a" and "previous answer was invalid" in llm.prompts[1]

    class Broken(Flaky):
        async def generate_text(self, *a, **k):
            return "nope"

    with pytest.raises(LlmResponseError):
        asyncio.run(generate_model(Broken(), Roadmap, "plan", "sys", max_attempts=2))


# ------------------------------------------------------------------ scanner
def test_scanner_finds_routes_models_and_skips_noise(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "ignored.py").write_text("class Hidden: ...")
    (tmp_path / "app" / "broken.py").write_text("def (:")
    (tmp_path / "app" / "api.py").write_text(
        "from fastapi import APIRouter\nfrom pydantic import BaseModel\n"
        "router = APIRouter(prefix='/items')\n"
        "class Item(BaseModel):\n    id: int\n    name: str\n"
        "@router.get('/{item_id}')\nasync def get_item(item_id: int) -> Item: ...\n"
        "@router.budget_report('/x')\ndef not_a_route(): ...\n"  # 'get' substring bug from v1
    )
    summary = ProjectScanner(tmp_path).scan()
    assert [(r.method, r.path, r.function) for r in summary.routes] == [("GET", "/{item_id}", "get_item")]
    assert [(c.name, c.kind, c.fields) for c in summary.models] == [("Item", "schema", ["id", "name"])]
    assert summary.skipped == ["app/broken.py"]
    assert "router (prefix='/items')" in format_symbol_index(summary)
    assert find_router_variables("router = APIRouter()\nother = 1") == ["router"]


# ------------------------------------------------------------------ injector
MAIN = '''"""Main."""
import os

from fastapi import FastAPI

app = FastAPI()  # keep this comment


@app.get("/health")
def health():
    return {}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app)
'''


def test_injector_places_code_correctly_and_is_idempotent(tmp_path):
    main = tmp_path / "main.py"
    main.write_text(MAIN)
    assert CodeInjector.inject_router(main, "app.routers.users", alias="routers_users_router") is True
    assert CodeInjector.inject_router(main, "app.routers.orders", alias="routers_orders_router") is True
    once = main.read_text()
    assert CodeInjector.inject_router(main, "app.routers.users", alias="routers_users_router") is False
    assert main.read_text() == once

    lines = once.splitlines()
    imp = lines.index("from app.routers.users import router as routers_users_router")
    assert imp > lines.index("from fastapi import FastAPI")
    include_users = lines.index("app.include_router(routers_users_router)")
    include_orders = lines.index("app.include_router(routers_orders_router)")
    assert lines.index("app = FastAPI()  # keep this comment") < include_users < include_orders
    assert include_orders < lines.index('if __name__ == "__main__":')
    compile(once, "main.py", "exec")


# ------------------------------------------------------------------ writer
def make_writer(root, protected=()):
    return SafeWriter(PathPolicy(root, protected_paths=protected), BackupService(root / ".fast-chimera" / "backups"))


def writer_backups(root):
    return root / ".fast-chimera" / "backups"


def test_writer_blocks_traversal_protected_and_conflicts(tmp_path):
    writer = make_writer(tmp_path, protected={"app/main.py"})
    with pytest.raises(UnsafePathError):
        writer.write("../escape.py", "x = 1", overwrite=True)
    with pytest.raises(UnsafePathError):
        writer.write("app/main.py", "x = 1", overwrite=True)
    with pytest.raises(UnsafePathError):
        writer.write("scripts/x.py", "x = 1", overwrite=True)

    writer.write("app/models/user.py", "x = 1", overwrite=False)
    assert (tmp_path / "app" / "__init__.py").exists() and (tmp_path / "app" / "models" / "__init__.py").exists()
    with pytest.raises(FileConflictError):
        writer.write("app/models/user.py", "x = 2", overwrite=False)

    writer.write("app/models/user.py", "x = 3", overwrite=True)
    backups = list(writer_backups(tmp_path).rglob("user.py"))
    assert len(backups) == 1 and backups[0].read_text() == "x = 1\n"


def test_writer_blocks_symlink_escape(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    project = tmp_path / "project"
    (project / "app").mkdir(parents=True)
    (project / "app" / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(UnsafePathError):
        make_writer(project).write("app/link/evil.py", "x = 1", overwrite=True)


# ------------------------------------------------------------------ validation / verification helpers
def test_validator_chain():
    router = FileSpec(path="app/routers/a.py", purpose="", kind="router")
    assert "SyntaxError" in ValidatorChain().check("def (:", router)[0]
    assert ValidatorChain().check("x = 1", router)
    assert not ValidatorChain().check("from fastapi import APIRouter\nrouter = APIRouter()", router)
    assert ValidatorChain().check("x = 1", FileSpec(path="tests/test_a.py", purpose="", kind="test"))


def test_failure_location_helpers(tmp_path):
    (tmp_path / "app").mkdir()
    trace = (
        "Traceback (most recent call last):\n"
        f'  File "{tmp_path}/app/routers/a.py", line 3, in <module>\n'
        f'  File "{tmp_path}/lib/site-packages/x.py", line 9, in f\n'
        "ImportError: cannot import name 'Prodcut'\n"
        "tests/test_a.py:12: AssertionError\n"
    )
    assert locate_failing_file(trace, tmp_path, {"app/routers/a.py"}) == "app/routers/a.py"
    assert locate_failing_file(trace, tmp_path, {"app/routers/a.py", "tests/test_a.py"}) == "tests/test_a.py"
    assert locate_failing_file("nothing here", tmp_path, {"app/x.py"}) is None
    assert find_missing_module("ModuleNotFoundError: No module named 'stripe'") == "stripe"
