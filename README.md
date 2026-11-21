# FastChimera

Describe a FastAPI product in one sentence, review the feature list the AI proposes, and let it build the
project **phase by phase**: planned in small steps, verified after every step, resumable at any point.

```console
$ fast-chimera build "multi vendor e-commerce website"
```

1. **Feature discovery.** One LLM call returns the full feature catalog (modules, features, priorities).
   You see every feature and can exclude modules or drop optional features.
2. **Roadmap.** A second call splits the work into ordered phases (foundation first, ~8 files each).
3. **Phase by phase.** Each phase is planned on its own right before it is built, so later phases see what was
   really generated. Files are generated **one at a time** with exactly the context they need
   (symbol index of the project + the source of the files they depend on), and checkpointed in batches.
4. **Verification after every batch.** Syntax check before writing, import check + SQLAlchemy mapper
   configuration after each batch, pytest after each phase. Failures are fed back to the model with the
   traceback (self-repair, bounded by `CHIMERA_REPAIR_ATTEMPTS`).

A 60-file project therefore never goes to the model as one request: it becomes ~10 phases, each with its own
small plan, and every file is a separate, focused request.

## Install

```bash
pip install git+https://github.com/3bdel7med/FastAPI_Chimera.git
export GEMINI_API_KEY=...        # or put it in a .env file in the directory you run the tool from
```

## Commands

| Command | What it does |
|---|---|
| `fast-chimera build "<idea>"` | New project from scratch (`-o DIR`, `--dry-run`, `-y`, `--batch-size N`, `--no-verify`, `--install`, `--force`) |
| `fast-chimera resume [DIR]` | Continue after a crash, a rate limit or Ctrl+C: finished phases and files are not redone |
| `fast-chimera add "<feature>"` | Same phased engine, applied to an existing FastAPI project |
| `fast-chimera scan [DIR]` | Show the routes/models the tool sees (`--json` for scripts) |
| `fast-chimera shift [DIR]` | Fingerprint a project (tables, columns, relations, endpoints, middleware), save `fast-chimera.shift.json` and POST it to your server (`-o FILE`, `--server URL`, `--no-send`, `-v`) |
| `fast-chimera status [DIR]` | Progress per phase |

Tip: run `--dry-run` first to see the features and roadmap without writing anything.

## `shift`: a portable fingerprint of your project

```console
$ fast-chimera shift                      # saves fast-chimera.shift.json, sends it if SHIFT_SERVER_URL is set
$ fast-chimera shift ./my-api --no-send   # local file only
```

The fingerprint is a light JSON file (a few KB) that describes the project's structure in framework-neutral terms,
so it can be used to rebuild the project in another framework (e.g. Laravel):

- **tables**: name, model, columns (type, nullable, primary key, unique, index, foreign key + `on_delete`),
  composite unique constraints, indexes, pivot (association) tables
- **relations**: `belongs_to`, `has_one`, `has_many`, `many_to_many` (+ pivot table, `back_populates`)
- **endpoints**: method, **full path** (router prefix + every `include_router` prefix), handler, tags, path/query/body/file
  params, request body, response model, status code, WebSocket routes
- **guards / middleware**: `Depends(...)` on routers and endpoints (with scope), injected dependencies (e.g. current user),
  and global middleware (`add_middleware`, `@app.middleware`, app-level dependencies)
- **unresolved**: everything static analysis could not determine (dynamic table names, computed paths, unparsable files)

Analysis is static (AST only): the project is never imported or executed. The file contains names, types and shapes only:
no source code, no default values, no option values. It captures **structure, not behavior**: business logic still has
to be ported or regenerated.

**Server contract** (what your platform must implement):

```
POST <SHIFT_SERVER_URL>
Content-Type: application/json
Authorization: Bearer <SHIFT_API_TOKEN>            # only when a token is configured
Idempotency-Key: <content_sha256>                  # same structure => same key, safe to retry
X-FastChimera-Content-SHA256: <content_sha256>

body: the fingerprint JSON (schema_version 1)
-> any 2xx = success; optional {"id": "..."} is shown to the user
```

Redirects are not followed, and the token is never printed. A failed send keeps the local file and exits with code 1.
`examples/shift_receiver.py` is a ready-to-run reference receiver.

## What is generated

A deterministic scaffold (no LLM, so the security-critical parts are not hallucinated): `app/main.py`,
settings, SQLAlchemy 2.0 session/`Base`, password hashing + JWT helpers, pytest fixtures with an in-memory DB.
The model then adds `app/models`, `app/schemas`, `app/services`, `app/routers` and `tests/` per phase.
Routers are registered in `app/main.py` automatically (LibCST: formatting preserved, idempotent).
You also get `FEATURES.md` (the agreed feature list) and `requirements-extra.txt` when the model needs more packages.

## Safety model

- Generated paths must be relative `.py` files under `app/` or `tests/`; traversal, symlink escapes and the
  scaffold files are rejected. Files you wrote yourself are never overwritten without `--force`, and anything
  that is replaced is backed up in `.fast-chimera/backups/`.
- Package names suggested by the model are **never auto-installed**; they go to `requirements-extra.txt` for review.
- The Gemini key is sent in a header (not the URL) and is removed from the environment of verification subprocesses.
- Verification **executes the generated code** (imports and pytest). The tool asks before building;
  use `--no-verify` to skip execution, and prefer running inside a virtualenv or container.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | required | API key |
| `CHIMERA_GEMINI_MODEL` | `gemini-3.5-flash-lite` | Model name; verify it exists for your key |
| `CHIMERA_RETRY_ATTEMPTS` | 4 | Retries (exponential backoff) on 429/5xx/network errors |
| `CHIMERA_BATCH_SIZE` | 4 | Files per verification checkpoint |
| `CHIMERA_REPAIR_ATTEMPTS` | 2 | Self-repair rounds per failing check |
| `CHIMERA_TIMEOUT` / `CHIMERA_TEMPERATURE` | 120 / 0.2 | Request timeout (s) / sampling temperature |
| `SHIFT_SERVER_URL` | unset | Where `shift` sends the fingerprint (https required, except localhost) |
| `SHIFT_API_TOKEN` | unset | Sent as `Authorization: Bearer ...` |
| `SHIFT_TIMEOUT` / `SHIFT_RETRY_ATTEMPTS` | 30 / 3 | Send timeout (s) / retries on 429, 5xx and network errors |
| `SHIFT_ALLOW_INSECURE` | false | Allow plain http to a non-local host (not recommended) |

`SHIFT_*` are read from the environment, then `.env` in the project folder, then `.env` in the current directory.

The LLM sits behind `core/interfaces.LlmClient`; adding another provider means implementing one method.

## Architecture

Small modules, one responsibility each, wired together in a single composition root.
See **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** for the folder map, the SOLID and design-pattern mapping,
the dependency rule and "how do I ...?" recipes.

```
cli ──▶ engine ──▶ generation ──▶ planning ──▶ llm ──▶ core
          ├──▶ verification · injection · analysis · state · scaffold
shift ──▶ analysis · core
```

## Development

```bash
pytest          # fully offline: a scripted FakeLlm plays Gemini, httpx.MockTransport plays your server
ruff check . && mypy src
```

`tests/test_architecture.py` enforces the dependency rule between packages and a 200-line limit per module.

The end-to-end test builds a two-phase marketplace with the fake LLM (including a deliberate syntax error and
a deliberate import typo), then runs the generated project's own test-suite.

## Limitations

- Output quality depends on the model; business-critical logic (payments, pricing, permissions) always needs human review.
- `shift` is static analysis: it misses dynamically generated tables/routes (reported under `unresolved`), and `add_api_route(...)` registrations are not followed.
- Backend only (REST API). No frontend, migrations (Alembic) or payment-provider integrations are generated.
- Not yet benchmarked against the real Gemini API; see the roadmap below.

## Roadmap

- Benchmark suite: N feature requests x M projects, report import/test success rate.
- Alembic migration generation, async SQLAlchemy option, more LLM providers.
