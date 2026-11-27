# FastChimera

Describe a FastAPI product in one sentence, review the feature catalog the AI proposes, and let it build the project **phase by phase**—planned in small steps, verified after every batch, and resumable at any point.

```console
$ fast-chimera build "multi vendor e-commerce store with products, categories, cart, orders, and user authentication"
```

---

## How It Works

1. **Feature Discovery.** A single LLM call decomposes your one-sentence prompt into a structured, prioritized feature catalog (`core`, `recommended`, `optional`) grouped by domain modules. You can exclude entire modules or drop optional features before a single line of code is written.
2. **Phased Roadmap.** A second call splits the approved scope into ordered phases (foundation first, ~8 files per phase).
3. **Context-Aware Generation.** Each phase is planned right before execution so later phases see what was actually built. Files are generated **one at a time** with exact context (the project's symbol index plus the source of direct dependencies) and checkpointed in batches.
4. **Automated Verification & Self-Repair.** Syntax checks run before writing, import and SQLAlchemy mapper checks run after every batch, and `pytest` runs after every phase. Any failure is fed back to the model with the exact traceback for bounded self-repair (`CHIMERA_REPAIR_ATTEMPTS`).

A large 60-file codebase never hits the model as one massive request—it becomes ~10 focused phases, and every file is generated cleanly with verified imports and tests.

---

## Real-World Run: Multi-Vendor E-Commerce API

Tested directly against the Gemini API with a single natural-language prompt:

```console
$ fast-chimera build "multi vendor e-commerce store with products, categories, cart, orders, and user authentication"
```

### Generated Catalog Summary (`50 features across 12 modules`)

From a one-line prompt, FastChimera produced a production-oriented domain breakdown covering:

| # | Module | Key Capabilities Generated | Priority Mix |
|---|---|---|---|
| **1** | **Authentication & Authorization** | User registration, JWT login/refresh, RBAC (`customer`, `vendor`, `admin`), bcrypt password reset, session revocation | 4 core, 1 recommended |
| **2** | **Vendor Onboarding & Management** | Vendor applications, admin approval workflow, store profile management, commission rules, vendor analytics | 3 core, 1 recommended, 1 optional |
| **3** | **Product Catalog & Inventory** | Vendor Product CRUD, SKU/size/color variants, real-time stock tracking, CSV/Excel bulk import, product moderation | 3 core, 2 recommended |
| **4** | **Category & Taxonomy** | Nested parent-child category trees, admin category CRUD, product tagging, category-specific attributes | 2 core, 1 recommended, 1 optional |
| **5** | **Search, Filtering & Pagination** | Full-text search, faceted filtering (price, category, vendor, rating), sorting, cursor/offset pagination | 3 core, 1 recommended |
| **6** | **Cart & Wishlist** | Persistent user carts, automatic multi-vendor cart grouping, pre-checkout stock validation, wishlists | 2 core, 2 recommended |
| **7** | **Orders & Checkout** | Master checkout with per-vendor **split order generation**, lifecycle states, vendor fulfillment dashboard, returns | 4 core, 1 recommended |
| **8** | **Payments & Financials** | Payment intent integration, async webhook handling, automatic platform commission & net payout calculation, refunds | 3 core, 2 recommended |
| **9** | **Reviews & Ratings** | Verified purchase product reviews, aggregate vendor store ratings, moderation, vendor replies | 2 recommended, 2 optional |
| **10** | **Shipping & Fulfillment** | Vendor shipping profiles (flat/weight/free), checkout shipping rate calculation, carrier tracking numbers | 3 recommended |
| **11** | **Promotions & Discounts** | Global and vendor-specific coupon codes, expiration/usage limits, split checkout discount application | 3 recommended |
| **12** | **Notifications & Communication** | Transactional email alerts, in-app notification center, buyer-to-vendor messaging | 1 recommended, 2 optional |

> **Interactive Scope Control:** Before generating files, FastChimera prompts you to exclude modules by number or trim optional features—letting you start lean (e.g., Core Auth + Catalog + Cart + Orders) and expand later via `fast-chimera add`.

---

## Installation

```bash
pip install -e ".[dev]"
export GEMINI_API_KEY="your_api_key_here"   # or place inside a .env file in your working directory
```

---

## CLI Commands

| Command | Description |
|---|---|
| `fast-chimera build "<idea>"` | Scaffold and build a new FastAPI project from scratch (`-o DIR`, `--dry-run`, `-y`, `--batch-size N`, `--no-verify`, `--no-install`, `--allow-package NAME`, `--force`) |
| `fast-chimera resume [DIR]` | Resume a build after interruption, rate limits, or package approval (`-y`, `--allow-package NAME`) |
| `fast-chimera add "<feature>"` | Extend an existing FastAPI project using the same phased engine |
| `fast-chimera scan [DIR]` | Inspect detected SQLAlchemy models and FastAPI routes (`--json` supported) |
| `fast-chimera shift [DIR]` | Extract a framework-neutral structural fingerprint (`fast-chimera.shift.json`) and optionally POST it to a target server (`-o FILE`, `--server URL`, `--no-send`, `-v`) |
| `fast-chimera status [DIR]` | View phase-by-phase build progress |

> **Tip:** Run with `--dry-run` first to inspect the proposed feature catalog and roadmap without writing files to disk.

---

## What Gets Generated

* **Deterministic Security & Core Scaffold:** Written without LLM guesswork—includes `app/main.py`, typed settings, SQLAlchemy 2.0 session & `Base`, password hashing, JWT helpers, and `pytest` fixtures backed by an in-memory database.
* **Domain Layers:** Modular `app/models/`, `app/schemas/`, `app/services/`, `app/routers/`, and matching test suites in `tests/`.
* **AST-Safe Router Wiring:** Routers are automatically registered in `app/main.py` using LibCST (idempotent, formatting-preserved).
* **Documentation & Reproducible Environment:** Generates `FEATURES.md`, manages an isolated `.venv` inside the output project, and pins approved dependencies in `requirements.txt`.

---

## Package Vetting & Isolation

Every generated project gets its own `.venv` so your global Python environment and FastChimera's environment stay clean:

```
Feature Catalog -> Roadmap -> PyPI Package Vetting -> Single Confirmation
               -> Scaffold + .venv + Baseline Install -> Phased Generation & Verification
```

* **Baseline Stack:** Core packages (`fastapi`, `sqlalchemy`, `pyjwt`, `pytest`, etc.) are installed automatically upon confirmation.
* **PyPI Safety Checks:** Extra model-suggested packages are verified on PyPI for existence, release history, age, and prebuilt wheel availability. Invented or wheel-less packages are rejected automatically.
* **Binary-Only Installs:** Approved extra packages are installed with `--only-binary=:all:` and recorded in `requirements.txt`.
* **Non-Interactive Runs (`-y`):** Passing `-y` never auto-approves unknown third-party packages; explicitly whitelist them with repeatable `--allow-package NAME` flags.
* **Fast / Lightweight Mode:** Use `--no-install` and `--no-verify` when running in constrained environments (such as lightweight servers or CI runners) where you only want source file generation.

---

## `shift`: Portable Project Fingerprinting

```console
$ fast-chimera shift                      # generates fast-chimera.shift.json and sends if SHIFT_SERVER_URL is configured
$ fast-chimera shift ./my-api --no-send   # generates local fingerprint file only
```

`shift` performs pure static AST analysis (never imports or executes target code) to export a compact JSON schema (`schema_version: 1`) capturing:
* **Tables & Columns:** Types, primary/foreign keys, `on_delete` rules, unique constraints, indexes, and pivot tables.
* **Relations:** `belongs_to`, `has_one`, `has_many`, and `many_to_many` mappings.
* **Endpoints:** Full resolved router paths, HTTP methods, handlers, parameters, request/response models, status codes, and WebSockets.
* **Guards & Middleware:** Router/endpoint `Depends(...)` scopes and global middleware.

**Receiver Contract:**
```http
POST <SHIFT_SERVER_URL>
Content-Type: application/json
Authorization: Bearer <SHIFT_API_TOKEN>
Idempotency-Key: <content_sha256>
X-FastChimera-Content-SHA256: <content_sha256>
```
See `examples/shift_receiver.py` for a ready-to-run reference server.

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *required* | Google Gemini API key |
| `CHIMERA_GEMINI_MODEL` | `gemini-3.5-flash-lite` | Target Gemini model name |
| `CHIMERA_RETRY_ATTEMPTS` | `4` | Exponential backoff retries on `429`/`5xx`/network errors |
| `CHIMERA_BATCH_SIZE` | `4` | Generated files per verification checkpoint |
| `CHIMERA_REPAIR_ATTEMPTS` | `2` | Automated self-repair attempts per failing check |
| `CHIMERA_TIMEOUT` | `120` | LLM request timeout in seconds |
| `CHIMERA_TEMPERATURE` | `0.2` | Sampling temperature |
| `SHIFT_SERVER_URL` | *unset* | Destination endpoint for `fast-chimera shift` (`https` required except localhost) |
| `SHIFT_API_TOKEN` | *unset* | Bearer token for `shift` uploads |
| `SHIFT_TIMEOUT` | `30` | `shift` upload timeout in seconds |
| `SHIFT_RETRY_ATTEMPTS` | `3` | Retry count for `shift` uploads |
| `SHIFT_ALLOW_INSECURE` | `false` | Allow plain `http` for non-local `SHIFT_SERVER_URL` |

---

## Architecture & Safety

```
cli ──▶ engine ──▶ generation ──▶ planning ──▶ llm ──▶ core
          ├──▶ verification · injection · analysis · state · scaffold
shift ──▶ analysis · core
```

* **Path Sandboxing:** Generated files are restricted to relative `.py` paths inside `app/` and `tests/`; path traversal, symlink escapes, and scaffold overwrites are blocked. Existing files are backed up under `.fast-chimera/backups/`.
* **Secret Isolation:** `GEMINI_API_KEY` is passed via request headers and stripped from verification subprocess environments.
* **Modular Codebase:** Enforced via `tests/test_architecture.py` (strict package dependency rules and 200-line module limits).

---

## Scope & Current Boundaries

* **Backend REST API Focus:** Generates FastAPI backends, SQLAlchemy models, Pydantic schemas, services, routers, and `pytest` suites. Frontend UIs, Alembic migration scripts, and live payment gateway credentials are outside the automated generation scope.
* **Static Analysis Boundaries (`shift`):** Dynamically constructed routes/tables and `add_api_route(...)` calls are flagged under `unresolved` in the shift fingerprint.
* **Human Review Recommended:** Always review generated pricing, permissions, and financial ledger logic before production deployment.

---

## Roadmap

* Automated multi-project benchmark suite tracking import and `pytest` pass rates across domains.
* Alembic database migration generation and async SQLAlchemy 2.0 support.
* Pluggable LLM provider adapters via `core/interfaces.LlmClient`.
