"""End-to-end: scripted LLM -> scaffold -> phased generation -> injection -> real import checks + pytest."""

import asyncio

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("bcrypt")
pytest.importorskip("jwt")
pytest.importorskip("httpx")

from fast_chimera.engine.events import Reporter  # noqa: E402
from fast_chimera.engine.factory import create_build_engine  # noqa: E402
from fast_chimera.engine.options import EngineOptions  # noqa: E402
from fast_chimera.planning.planner import Planner  # noqa: E402
from fast_chimera.scaffold.scaffolder import Scaffolder  # noqa: E402
from fast_chimera.state.models import BuildState, PhaseState  # noqa: E402
from fast_chimera.state.repository import JsonStateRepository  # noqa: E402

from .fakes import FakeLlm  # noqa: E402


class Recorder(Reporter):
    def __init__(self):
        self.events = []

    def phase_planned(self, phase, batches):
        self.events.append(("batches", phase.outline.id, [len(b) for b in batches]))

    def check(self, label, ok, detail=""):
        self.events.append(("check", label, ok))

    def info(self, message):
        self.events.append(("info", message))

    def warning(self, message):
        self.events.append(("warning", message))


async def plan(llm, prompt="build a mini marketplace"):
    planner = Planner(llm)
    catalog = (await planner.discover_features(prompt)).select(include_optional=False)
    roadmap = await planner.create_roadmap(prompt, catalog)
    return BuildState(prompt=prompt, catalog=catalog, phases=[PhaseState(outline=p) for p in roadmap.phases])


def test_full_build_is_phased_safe_and_self_repairing(tmp_path):
    llm, reporter = FakeLlm(), Recorder()
    Scaffolder().create(tmp_path, "mini-marketplace")

    async def go():
        state = await plan(llm)
        await create_build_engine(tmp_path, llm, EngineOptions(batch_size=2, max_repair_attempts=2), reporter).run(state)
        return state

    state = asyncio.run(go())

    # 1. every phase finished, and each phase was planned by its OWN call, right before its files
    assert [p.status for p in state.phases] == ["done", "done"]
    order = [(task, arg) for task, arg in llm.calls if task in ("plan_phase", "generate")]
    assert order.index(("plan_phase", "2")) > max(i for i, (t, a) in enumerate(order) if a == "tests/test_vendors.py")

    # 2. files were generated one at a time in dependency order (models -> schemas -> routers -> tests)
    generated = [a for t, a in llm.calls if t == "generate"]
    assert generated[:4] == [
        "app/models/vendor.py",
        "app/schemas/vendor.py",
        "app/routers/vendors.py",
        "tests/test_vendors.py",
    ]

    # 3. the plan was batched (4 files, batch size 2)
    assert ("batches", 1, [2, 2]) in reporter.events

    # 4. unsafe / protected planned files were ignored and never written
    assert not (tmp_path.parent / "etc").exists()
    assert "tests/../" not in "".join(state.file_hashes)
    assert any("app/core/security.py" in w for w in state.warnings)
    assert "bcrypt" in (tmp_path / "app/core/security.py").read_text()  # scaffold untouched

    # 5. routers were registered in main.py exactly once each
    main = (tmp_path / "app/main.py").read_text()
    assert main.count("app.include_router(") == 2
    assert "from app.routers.vendors import router as routers_vendors_router" in main

    # 6. syntax error repaired before writing; import error repaired after the import check
    assert ("repair", "app/schemas/product.py") in llm.calls
    assert ("repair", "app/routers/products.py") in llm.calls
    assert not any(e[0] == "check" and e[2] is False for e in reporter.events)

    # 7. LLM-suggested extra packages are listed for review, never auto-installed; baseline ones are not duplicated
    assert (tmp_path / "requirements-extra.txt").read_text().strip() == "stripe>=7"
    assert (tmp_path / "FEATURES.md").exists()

    # 8. the generated project really works
    import subprocess
    import sys

    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 passed" in result.stdout

    # 9. `shift` understands the project this very pipeline just built (router registered via an injected alias)
    from fast_chimera.shift.extraction import FingerprintExtractor

    fp = FingerprintExtractor(tmp_path).extract()
    assert {t.name for t in fp.tables} == {"vendors", "products"}
    products = next(t for t in fp.tables if t.name == "products")
    assert any(c.foreign_key == "vendors.id" for c in products.columns)
    paths = {(e.method, e.path, e.mounted) for e in fp.endpoints}
    assert {("POST", "/vendors", True), ("GET", "/products", True), ("GET", "/health", True)} <= paths


def test_resume_skips_finished_work_after_a_crash(tmp_path):
    Scaffolder().create(tmp_path, "mini-marketplace")
    llm = FakeLlm()

    class Crash(Exception):
        pass

    class CrashingReporter(Reporter):
        def file_done(self, spec):
            if spec.path == "app/schemas/product.py":
                raise Crash

    async def first_run():
        state = await plan(llm)
        JsonStateRepository(tmp_path).save(state)
        try:
            await create_build_engine(tmp_path, llm, EngineOptions(verify=False), CrashingReporter()).run(state)
        except Crash:
            pass

    asyncio.run(first_run())
    saved = JsonStateRepository(tmp_path).load()
    assert [p.status for p in saved.phases] == ["done", "failed"]

    calls_before = len(llm.calls)

    async def second_run():
        await create_build_engine(tmp_path, llm, EngineOptions(verify=False), Reporter()).run(saved)

    asyncio.run(second_run())
    new_calls = llm.calls[calls_before:]
    assert not any(t == "discover" or (t == "plan_phase") for t, _ in new_calls)  # phases already planned
    assert not any(a in ("app/models/vendor.py", "app/models/product.py") for t, a in new_calls if t == "generate")
    assert JsonStateRepository(tmp_path).load().phases[-1].status == "done"


def test_existing_user_file_is_never_overwritten_without_force(tmp_path):
    Scaffolder().create(tmp_path, "mini-marketplace")
    mine = tmp_path / "app" / "models" / "vendor.py"
    mine.write_text("# my own work\n")
    llm = FakeLlm()

    async def go(force):
        state = await plan(llm)
        await create_build_engine(tmp_path, llm, EngineOptions(verify=False, force=force), Reporter()).run(state)
        return state

    state = asyncio.run(go(False))
    assert mine.read_text() == "# my own work\n"
    assert any("app/models/vendor.py" in w for w in state.warnings)
