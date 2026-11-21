"""Tests for the small, single-purpose pieces. Each one needs no LLM, no network and almost no setup:
that is the payoff of separating responsibilities."""

import ast
import asyncio

import libcst as cst
import pytest

from fast_chimera.core.exceptions import ShiftConfigError
from fast_chimera.engine.events import Reporter
from fast_chimera.engine.failure_triage import triage_failure
from fast_chimera.engine.overwrite_policy import OverwritePolicy, WriteDecision
from fast_chimera.engine.verification_loop import VerificationLoop
from fast_chimera.generation.validators import CodeValidator, ValidatorChain
from fast_chimera.injection.insertion_points import import_insert_index, include_router_insert_index
from fast_chimera.llm.retry import RetryPolicy
from fast_chimera.planning.catalog_formatting import describe_for_prompt
from fast_chimera.planning.schemas import FeatureCatalog, FileSpec, Roadmap
from fast_chimera.shift.extraction.annotations import unwrap_annotation
from fast_chimera.shift.extraction.imports import absolute_module_name
from fast_chimera.shift.extraction.type_names import normalize_type_name
from fast_chimera.shift.publishing.url_policy import validate_server_url
from fast_chimera.state.factory import create_initial_state
from fast_chimera.verification.results import CheckResult

from .fakes import CATALOG


def expr(source: str) -> ast.expr:
    return ast.parse(source, mode="eval").body


# ------------------------------------------------------------------ retry policy
def test_retry_policy_decisions():
    policy = RetryPolicy(max_attempts=3, base_delay=1, max_delay=4)
    assert policy.is_retryable(429) and policy.is_retryable(503)
    assert not policy.is_retryable(400) and not policy.is_retryable(401)
    assert 4 <= policy.delay_before_next_attempt(10) <= 5  # capped at max_delay (+ up to 25% jitter)
    assert policy.delay_before_next_attempt(1, retry_after=2.5) == 2.5
    assert policy.delay_before_next_attempt(1, retry_after=9999) == 60  # a server cannot make us wait forever


# ------------------------------------------------------------------ overwrite policy
@pytest.mark.parametrize(
    "exists, ours, action, force, expected",
    [
        (False, False, "CREATE", False, WriteDecision.WRITE_NEW),
        (True, True, "CREATE", False, WriteDecision.OVERWRITE),  # our own file: safe to regenerate
        (True, False, "MODIFY", False, WriteDecision.OVERWRITE),  # the plan explicitly says modify
        (True, False, "CREATE", False, WriteDecision.SKIP_USER_FILE),  # the user's work: leave it
        (True, False, "CREATE", True, WriteDecision.OVERWRITE),  # --force
    ],
)
def test_overwrite_policy(exists, ours, action, force, expected):
    decision = OverwritePolicy(force).decide(file_exists=exists, written_by_us=ours, action=action)
    assert decision is expected


# ------------------------------------------------------------------ validators (Strategy + Chain)
def test_validators_can_be_extended_without_touching_existing_ones():
    class NoPrintValidator:
        def check(self, code: str, spec: FileSpec) -> list[str]:
            return ["print() is not allowed"] if "print(" in code else []

    validators: list[CodeValidator] = [NoPrintValidator()]
    chain = ValidatorChain(validators)
    spec = FileSpec(path="app/x.py", purpose="")
    assert chain.check("print('hi')", spec) == ["print() is not allowed"]
    assert chain.check("x = 1", spec) == []


def test_chain_stops_at_the_first_failing_rule():
    spec = FileSpec(path="app/routers/a.py", purpose="", kind="router")
    problems = ValidatorChain().check("def (:", spec)
    assert len(problems) == 1 and problems[0].startswith("SyntaxError")  # the router rule never ran on broken code


# ------------------------------------------------------------------ injector insertion points (pure functions)
def body_of(source: str):
    return list(cst.parse_module(source).body)


def test_import_goes_after_last_import_then_after_docstring_then_top():
    assert import_insert_index(body_of("import a\nimport b\nx = 1\n")) == 2
    assert import_insert_index(body_of('"""doc"""\nx = 1\n')) == 1
    assert import_insert_index(body_of("x = 1\n")) == 0


def test_include_goes_after_last_include_then_after_app_then_before_main_guard():
    after_include = body_of("app = FastAPI()\napp.include_router(a)\nx = 1\n")
    assert include_router_insert_index(after_include, "app") == 2
    after_app = body_of("app = FastAPI()\nx = 1\n")
    assert include_router_insert_index(after_app, "app") == 1
    before_guard = body_of('x = 1\nif __name__ == "__main__":\n    pass\n')
    assert include_router_insert_index(before_guard, "app") == 1


# ------------------------------------------------------------------ failure triage
def test_triage_separates_missing_packages_from_our_own_bugs(tmp_path):
    (tmp_path / "app").mkdir()
    generated = {"app/routers/a.py"}
    assert triage_failure("No module named 'stripe'", tmp_path, generated).kind == "missing_dependency"
    assert triage_failure("No module named 'app.models.ghost'", tmp_path, generated).kind != "missing_dependency"
    trace = f'File "{tmp_path}/app/routers/a.py", line 3, in <module>\nNameError: x'
    triage = triage_failure(trace, tmp_path, generated)
    assert (triage.kind, triage.file) == ("repairable", "app/routers/a.py")
    assert triage_failure("something odd", tmp_path, generated).kind == "unknown"


# ------------------------------------------------------------------ verification loop with a fake repairer (Dependency Inversion)
class FakeRepairer:
    def __init__(self):
        self.repaired = []

    async def repair(self, state, relative_path, error_output):
        self.repaired.append(relative_path)


class RecordingReporter(Reporter):
    def __init__(self):
        self.checks = []

    def check(self, label, ok, detail=""):
        self.checks.append((label, ok))


def make_state():
    catalog = FeatureCatalog.model_validate(CATALOG)
    roadmap = Roadmap.model_validate({"phases": [{"name": "p", "goal": "g"}]}).renumbered()
    state = create_initial_state("x", catalog, roadmap, "build")
    state.file_hashes["app/a.py"] = "hash"
    return state


def run_loop(tmp_path, results, max_repairs=2):
    repairer, reporter = FakeRepairer(), RecordingReporter()
    loop = VerificationLoop(tmp_path, repairer, reporter, max_repairs)
    outputs = iter(results)
    state = make_state()
    asyncio.run(loop.run(state, "check", lambda: next(outputs)))
    return repairer, reporter, state


def test_loop_repairs_then_succeeds(tmp_path):
    failing = CheckResult(False, f'File "{tmp_path}/app/a.py", line 1\nboom')
    repairer, reporter, _ = run_loop(tmp_path, [failing, CheckResult(True, "")])
    assert repairer.repaired == ["app/a.py"] and reporter.checks == [("check", True)]


def test_loop_gives_up_after_the_configured_number_of_repairs(tmp_path):
    failing = CheckResult(False, f'File "{tmp_path}/app/a.py", line 1\nboom')
    repairer, reporter, state = run_loop(tmp_path, [failing] * 5, max_repairs=2)
    assert len(repairer.repaired) == 2 and reporter.checks == [("check", False)]
    assert any("check failing" in w for w in state.warnings)


def test_loop_does_not_burn_repairs_on_a_missing_package(tmp_path):
    repairer, _, state = run_loop(tmp_path, [CheckResult(False, "No module named 'stripe'")])
    assert repairer.repaired == [] and any("stripe" in w for w in state.warnings)


# ------------------------------------------------------------------ shift helpers
def test_annotation_unwrapping():
    note = unwrap_annotation(expr('Mapped[Optional[list["Product"]]]'))
    assert (note.wrapped_in_mapped, note.optional, note.is_collection) == (True, True, True)
    assert ast.unparse(note.core) == "Product"
    assert unwrap_annotation(expr("str | None")).optional
    assert unwrap_annotation(expr("Annotated[int, Depends(x)]")).core.id == "int"


def test_type_names():
    assert normalize_type_name(expr("String(120)")) == "string(120)"
    assert normalize_type_name(expr("Numeric(12, 2)")) == "decimal(12,2)"
    assert normalize_type_name(expr("int")) == "integer"
    assert normalize_type_name(None) == "unknown"


def test_relative_imports_are_made_absolute():
    assert absolute_module_name("app.routers.vendors", False, 1, "schemas") == "app.routers.schemas"
    assert absolute_module_name("app.routers.vendors", False, 2, "deps") == "app.deps"
    assert absolute_module_name("app.routers", True, 1, "vendors") == "app.routers.vendors"


def test_server_url_policy():
    assert validate_server_url("https://p.example.com/in")
    with pytest.raises(ShiftConfigError):
        validate_server_url("http://p.example.com/in")


# ------------------------------------------------------------------ catalog formatting is separate from the model
def test_describe_for_prompt_lists_features_only_for_focused_modules():
    catalog = FeatureCatalog.model_validate(CATALOG)
    focused = describe_for_prompt(catalog, ["Vendors"])
    assert "Vendor registration" in focused and "Product listing" not in focused
    assert "Product listing" in describe_for_prompt(catalog)
