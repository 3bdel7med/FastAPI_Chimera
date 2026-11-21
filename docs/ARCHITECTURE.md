# Architecture guide

How the code is organised, why, and where to look when you want to change something.
Every module starts with a docstring that says its **Responsibility** (and its **Pattern**, when it uses one).

## 1. Reading order (follow one command from the top)

1. `cli/app.py`: the Typer app; one line per command.
2. `cli/commands/build.py`: the `build` command: discover features, choose, plan, confirm, run.
3. `engine/factory.py`: **the one place where objects are created and wired together.**
4. `engine/build_engine.py`: loops over phases.
5. `engine/phase_runner.py`: one phase: plan its files, build them in batches, verify.
6. `engine/file_builder.py`: one file: decide, generate, write, register router, record.
7. `generation/generator.py` then `generation/writer.py`: ask the LLM, validate, write safely.

## 2. Folder map

| Folder | Responsibility |
|---|---|
| `core/` | Exceptions, the `LlmClient` interface, path and text helpers. Imports nothing from the package. |
| `llm/` | Talking to Gemini: `request.py` (body), `response.py` (parsing), `retry.py` (policy), `gemini_client.py` (the adapter), `json_extraction.py`, `structured.py` |
| `planning/` | The three planning questions (`steps/`), their prompts (`prompts/`), data models (`schemas/`), and small pure helpers (`file_plan.py`, `catalog_formatting.py`) |
| `analysis/` | Read-only scanning of a project with `ast`: file discovery, per-module analysis, the symbol index used in prompts |
| `scaffold/` | The deterministic project skeleton (never written by the LLM) |
| `generation/` | Write one file: prompt builder, validators, generator, path policy, backup, safe writer |
| `injection/` | Register a router in `main.py` with LibCST: predicates, insertion points, transformer, facade |
| `verification/` | Import check, pytest, pip install as small command objects; subprocess runner; traceback parsing |
| `state/` | What is saved between runs (`models.py`) and where (`repository.py`) |
| `engine/` | Runs a roadmap: phase runner, file builder, verification + repair loop, finalizer, composition root |
| `shift/` | The project fingerprint: `schema/`, `extraction/` (one small module per concern), `publishing/` |
| `cli/` | Typer commands (`commands/`), Rich rendering (`ui/`), factories (`dependencies.py`) |

## 3. SOLID, with the actual files

**S: Single Responsibility.** One reason to change per class.
`llm/retry.py` changes only when the retry rules change; `llm/response.py` only when Gemini's response format changes;
`generation/path_policy.py` only when path rules change. The old 800-line extractor is now 25 small modules
(`columns.py`, `relations.py`, `router_graph.py`, `params.py`, ...), none over 150 lines.

**O: Open/Closed.** Extend by adding, not editing.
- New validation rule: add a class with a `check` method and put it in `ValidatorChain` (`generation/validators.py`).
- New verification (ruff, mypy): add a class like `PytestCheck` in `verification/checks.py`.
- New command: write `cli/commands/<name>.py` and add it to the tuple at the bottom of `cli/app.py`.

**L: Liskov Substitution.** Any `LlmClient` can replace another. `GeminiClient` is the real one;
`tests/fakes.py::FakeLlm` is a second one, and the whole engine runs on it unchanged. That is the proof.

**I: Interface Segregation.** Small interfaces, shaped by what the caller needs.
`Verifier` (3 methods) is all the engine knows about verification; `StateRepository` (3 methods) all it knows about
storage; `Reporter` is a set of optional hooks, so a caller implements only what it cares about.

**D: Dependency Inversion.** High-level code depends on abstractions; concrete classes are wired in ONE place.
`engine/` classes receive their collaborators in the constructor. Only `engine/factory.py` and
`cli/dependencies.py` say `GeminiClient`, `ProjectVerifier`, `JsonStateRepository`.

> Honest note: abstractions exist where they pay off (a real second implementation, or a test needs a fake):
> `LlmClient`, `Verifier`, `StateRepository`, `Reporter`, `CodeValidator`. Classes like `SafeWriter` are used
> concretely because nothing else would implement them (YAGNI). SOLID is a tool, not a quota.

## 4. Design patterns used (and why)

| Pattern | Where | Why it fits |
|---|---|---|
| **Adapter** | `llm/gemini_client.py` | Hides Gemini's HTTP API behind our `LlmClient` interface |
| **Facade** | `engine/build_engine.py`, `planning/planner.py`, `injection/code_injector.py`, `verification/verifier.py`, `shift/extraction/extractor.py` | One simple entry point over several small collaborators |
| **Strategy + Chain** | `generation/validators.py` | Each rule is a swappable object; the chain runs them in order |
| **Command** | `verification/checks.py` | Each check is an object with `run()`; easy to add, queue or retry |
| **Observer / Null Object** | `engine/events.py`, `cli/ui/reporter.py` | The engine announces events; the CLI listens; a no-op base means nobody has to |
| **Repository** | `state/repository.py` | Only one class knows the state is a JSON file |
| **Composition Root / Factory** | `engine/factory.py`, `cli/dependencies.py` | All object creation in one place; tests swap parts by patching one function |
| **Visitor-style traversal** | `analysis/module_analyzer.py`, `shift/extraction/*` | Each extractor walks the AST looking for ONE kind of node |
| **Builder** | `shift/extraction/extractor.py` | Assembles the Fingerprint from independently produced parts |

## 5. The dependency rule

```
cli ──▶ engine ──▶ generation ──▶ planning ──▶ llm ──▶ core
          │            │
          ├──▶ verification, injection, analysis, state, scaffold
shift ──▶ analysis, core        (shift never depends on engine, planning or generation)
```

Arrows point toward the more stable, more general code. `tests/test_architecture.py` enforces this: a
lower layer importing a higher one fails the test suite. The same test fails any module over 200 lines.

## 6. How do I...?

| I want to... | Change |
|---|---|
| use another LLM (OpenAI, Ollama) | implement `LlmClient` (one method) and return it from `cli/dependencies.py::create_llm_client` |
| reject generated code that does X | add a `CodeValidator` class in `generation/validators.py` |
| also run `ruff` on generated code | add a `RuffCheck` in `verification/checks.py`, a method on `ProjectVerifier`, and a call in `engine/batch_verification.py` |
| change the coding rules the model follows | `planning/prompts/conventions.py` |
| change which files the model may never touch | `scaffold/constants.py::PROTECTED_PATHS` |
| understand one more ORM in `shift` | a new parser next to `shift/extraction/columns.py`, used from `class_members.py` |
| add a command | `cli/commands/<name>.py` + one entry in `cli/app.py` |

## 7. The `build` flow in ten steps

1. `build` asks `FeatureDiscovery` for the feature catalog; the user selects modules.
2. `RoadmapPlanning` splits the work into phases.
3. The target folder is checked, `Scaffolder` writes the skeleton, `JsonStateRepository` saves the initial state.
4. `create_build_engine` wires the engine; `BuildEngine.run` loops over phases.
5. `PhaseRunner` asks `PhaseFilePlanner` which files the phase needs (cleaned by `file_plan.py`).
6. Files are split into batches; for each file `FileBuilder` runs.
7. `OverwritePolicy` decides; `FileGenerator` asks the LLM and `ValidatorChain` checks the answer (with repair).
8. `SafeWriter` writes (path policy, backup); `RouterRegistrar` registers routers; state is saved.
9. After each batch `BatchVerification` runs the import check; at the end of the phase, the phase's tests. Failures go
   through `triage_failure` and `FileRepairer` (bounded by `max_repair_attempts`).
10. `Finalizer` writes `FEATURES.md`, `requirements-extra.txt` and runs the final test run.
