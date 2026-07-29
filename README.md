# CaseFlow — Multi-Tenant AI Case Platform

[![Deploy to EC2](https://github.com/nxu22/CaseFlow-AI-Legal-Assistant/actions/workflows/deploy.yml/badge.svg)](https://github.com/nxu22/CaseFlow-AI-Legal-Assistant/actions/workflows/deploy.yml)

A B2B SaaS case-management platform for Manitoba traffic-defense law firms, built to answer two questions I wanted hands-on answers to:

1. **How do you make tenant isolation something you can prove, not just something you intended?**
2. **How do you put an LLM agent in a workflow with legal consequences without letting it write to the database unsupervised?**

Every firm's users, cases, clients, and documents are isolated at two independent layers — application-layer filtering *and* PostgreSQL Row-Level Security — with a 36-test regression suite that tries to break through both. The AI intake agent is a LangGraph pipeline that drafts a case memo and then **stops**, waiting for a lawyer's approval before anything is persisted.

Solo project: backend, frontend, infrastructure, and deployment.

---

## Try it

| | |
|---|---|
| **Live app** | https://caseflowmb.site |
| **Firm A login** | `lawyer@caseflow.mb` / `Demo1234!` |
| **Firm B login** | `bob@jones.law` / `Jones1234!` |
| **Public AI demo** | https://caseflowmb.site/demo *(no login)* |
| **Interactive architecture map** | https://nxu22.github.io/CaseFlow-AI-Legal-Assistant/ |

> **To see the isolation claim yourself:** log in as Firm A, copy a case UUID from the URL, log out, log in as Firm B, and paste that UUID into the address bar. You get a 404 — not a 403 — because confirming *"this exists but isn't yours"* is itself a leak. Then try it with the app-layer filter removed and the RLS policy still catches it (`backend/tests/test_rls_depth.py`).

---

## If you only have five minutes

The parts I'd want a reviewer to look at, in order:

| File | Why it's worth reading |
|---|---|
| [`backend/dependencies.py`](backend/dependencies.py) | `get_db_with_rls` — where tenant context is bound to the transaction |
| [`backend/alembic/versions/b7d3e1a9f5c2_*.py`](backend/alembic/versions/) | The RLS policy, and the `nullif()` fix for a cast failure it originally shipped with |
| [`backend/tests/test_rls_depth.py`](backend/tests/test_rls_depth.py) | Bypasses FastAPI entirely and attacks the database directly |
| [`backend/services/intake_agent.py`](backend/services/intake_agent.py) | LangGraph DAG with a human-in-the-loop interrupt |
| [`backend/routers/intake.py`](backend/routers/intake.py) | Two-phase endpoint pair; thread ownership check before resuming |
| [`backend/mcp_server.py`](backend/mcp_server.py) | Same data exposed as agent tools, with the same isolation guarantees |

---

## Architecture

```
Browser ──► TLS / reverse proxy (host-level, outside this repo)
                │
                ▼
        EC2 (Ubuntu 24.04)
        ├── caseflow_frontend_prod   Next.js 16, port 3000
        └── caseflow_backend_prod    Gunicorn + FastAPI, port 8000
                 │
                 ├─ JWT → look up user → resolve firm_id (never trusted from the token)
                 ├─ SET LOCAL app.current_tenant = <firm_id>   (per transaction)
                 └─ every query also filters firm_id explicitly
                          │
                          ▼
                 AWS RDS PostgreSQL 16
                 ├── cases · clients · documents · intake_sessions   (RLS policies)
                 └── LangGraph checkpoint tables                     (PostgresSaver)

AWS S3          private bucket, presigned URLs generated on demand
Anthropic API   Sonnet for summarize + intake · Haiku for public demo chat
Langfuse        traces every LLM call — tokens, latency, dev/prod tag

Claude Desktop ──► mcp_server.py (stdio, authenticated by FIRM_API_KEY)
```

---

## The hard part: tenant isolation you can test

A single forgotten `.filter(firm_id == ...)` in a B2B product is a data breach. So the app layer isn't the only thing standing between two law firms.

```
Request → app layer         every router query filters firm_id
              ↓
          PostgreSQL RLS    SET LOCAL app.current_tenant, per transaction
              ↓
          caseflow_app      non-superuser role → RLS always applies
```

**Application layer** — `get_db_with_rls` issues `SET LOCAL app.current_tenant = <firm_id>` at the start of every authenticated request, and each router filters `firm_id` explicitly.

**Database layer** — RLS policies on `cases`, `clients`, `documents`, and `intake_sessions`:

```sql
CASE WHEN nullif(current_setting('app.current_tenant', true), '') IS NULL
     THEN true                                    -- migrations / superuser tooling
     ELSE firm_id = current_setting('app.current_tenant')::uuid
END
```

The `ELSE` branch is the safety net: it catches any query where the application layer forgot to filter.

**Three decisions behind that, and why:**

- **`SET LOCAL`, not `SET`.** `SET LOCAL` is transaction-scoped, so the GUC reverts on `COMMIT`. With `SET`, tenant context would survive on a pooled connection and the next request — possibly a different firm — would inherit it. A pool-checkout event additionally fires `RESET app.current_tenant` to move the value from `''` to `NULL`.
- **No `FORCE ROW SECURITY`.** The app connects as `caseflow_app`, a non-superuser, non-owner role, so RLS applies automatically. `FORCE` only matters for table owners — reaching for it would have signalled I didn't know why RLS was being skipped.
- **`nullif()` in the policy.** The first version of the policy cast `current_setting(...)::uuid` directly, which fails at plan time when the GUC is an empty string rather than NULL. Migration `b7d3e1a9f5c2` fixes it. Left in the history deliberately — it's the kind of bug that only shows up under connection pooling.

### Regression suite — 36 cross-tenant tests

| File | Attack it simulates |
|---|---|
| `test_rls_depth.py` | Raw psycopg2, FastAPI bypassed — RLS alone must block cross-tenant reads |
| `test_cases_isolation.py` | Firm B reading/writing Firm A's cases over HTTP |
| `test_clients_isolation.py` | Cross-firm client lookup must 404 |
| `test_documents_isolation.py` | Upload / download / delete, blocked both directions |
| `test_intake_isolation.py` | Agent Phase 1 case ownership + Phase 2 thread ownership |
| `test_demo_isolation.py` | Public demo tools confined to Demo Firm data |
| `test_mcp_isolation.py` | MCP read *and* write blocked; DB verified unchanged after the write attempt |

```bash
pip install pytest                       # not in requirements.txt — test-only dependency
cd backend && pytest                     # 36 tests
pytest -m "not slow"                     # skip the tests that make real Claude calls
```

---

## The AI intake agent

A LangGraph `StateGraph` that reads a scanned ticket and produces a case intake memo — then hands control back to a human before anything is written.

```
document text
     │
     ▼
[extract_info]      Sonnet extracts accused, offence, speed, date, location, officer
     │
     ├──────────────────────────┐          two independent nodes, run in parallel
     ▼                          ▼
[lookup_hta]              [find_similar]
static HTA table          SQL search over the firm's own cases
     │                          │
     └──────────┬───────────────┘          fan-in
                ▼
        [draft_intake]         Sonnet drafts the memo
                │
             ⏸  INTERRUPT — graph pauses, state checkpointed to Postgres
                │
        lawyer reviews in the UI: approve · edit inline · reject · redraft
                │
                ▼
        hta_section + ai_summary written to the Case record (approve/edit only)
```

**Why it's built this way:**

- **The interrupt is the point.** `interrupt_after=["draft_intake"]` means no LLM output reaches the `Case` record without a lawyer clicking approve. Rejection writes nothing.
- **`lookup_hta` is a static table, not the model.** `hta_reference.py` maps offence keywords to real Manitoba Highway Traffic Act sections. Asking an LLM to recall statute numbers is exactly how you get a confident, fabricated citation in a legal document.
- **`PostgresSaver`, not in-memory state.** Phase 1 and Phase 2 are separate HTTP requests, possibly served by different Gunicorn workers, possibly minutes apart. The checkpoint is what makes `thread_id` reconnect them, and it survives restarts and redeploys.
- **Redrafts are capped.** "Regenerate" without a limit is an unbounded spend button on a public-facing product.

**Two-phase API:**

| | |
|---|---|
| `POST /cases/{id}/intake` | Phase 1 — returns `thread_id`, draft memo, HTA match |
| `POST /cases/{id}/intake/{thread_id}/decision` | Phase 2 — `approve` / `edit` / `reject` / `redraft`, resumes from the checkpoint |

**Isolating an agent is its own problem.** LangGraph's checkpoint tables are owned by the library — I can't add a `firm_id` column to them. So an `IntakeSession` sidecar table maps `thread_id → firm_id` outside the graph, and Phase 2 verifies ownership before resuming. A thread belonging to another firm returns 404.

---

## MCP server — the same data as agent tools

`backend/mcp_server.py` exposes CaseFlow to Claude Desktop over FastMCP (stdio). The interesting constraint: an MCP server has no HTTP request to hang auth off, so isolation has to be established differently.

- `_resolve_firm_id()` runs at **module import** and calls `sys.exit(1)` if `FIRM_API_KEY` is missing or invalid — the process refuses to start rather than starting unscoped.
- Every tool call opens its own session with `SET LOCAL app.current_tenant` for that firm.
- `ENVIRONMENT=production` is forced, because SQLAlchemy's echo output would otherwise corrupt the stdio JSON-RPC stream.

| Tool | Does |
|---|---|
| `search_cases` | Filter by status or client name |
| `get_case` | Full case detail |
| `list_documents` | Documents on a case |
| `get_hta_section` | Manitoba HTA lookup |
| `update_case_status` | Update status |

```json
{
  "mcpServers": {
    "caseflow": {
      "command": "path/to/venv/Scripts/python.exe",
      "args": ["path/to/backend/mcp_server.py"],
      "env": { "FIRM_API_KEY": "your-firm-api-key" }
    }
  }
}
```

---

## Public demo — shipping an LLM endpoint with no auth in front of it

`/demo` lets anyone chat with case data without logging in, which means the threat model is "the open internet has my API key budget."

- API key stays in backend env vars — the browser talks to `/demo/chat`, never to Anthropic
- Per-IP rate limit: 10 requests/hour
- Haiku, `max_tokens=1024`, 500-character message cap
- Read-only tools only — no write path is exposed
- Scoped to Demo Firm data via the same `SET LOCAL app.current_tenant` mechanism
- System prompt constrains the model to CaseFlow topics

---

## What the app actually does

- **Cases** — HTA violation cases (speeding, careless driving, red light) with Open / In Progress / Won / Lost / Dismissed statuses; auto-generated case numbers, per-firm sequence
- **Clients** — defendant profiles with driver's licence details, firm-isolated *(full REST API; UI currently read-through from the case view)*
- **Documents** — PDF/image upload straight to a private S3 bucket, presigned time-limited downloads
- **AI summarization** — one-click Claude summary of any uploaded document (offence details, dates, fines, defense notes)
- **AI intake agent** — the LangGraph pipeline above, with lawyer review
- **MCP tools** — query and update cases from Claude Desktop
- **Public demo chat** — rate-limited, read-only

---

## Run it locally

**Prerequisites:** Docker Desktop, Git.

```bash
git clone https://github.com/nxu22/CaseFlow-AI-Legal-Assistant.git
cd CaseFlow-AI-Legal-Assistant
cp .env.example .env
```

Fill in `.env` **at the repo root** (`docker-compose.yml` reads it via `env_file`, so compose won't start without it):

```ini
# Required. Generate with:
#   python -c "import secrets; print(secrets.token_hex(32))"
# If this is left unset there is no startup error — config.py declares
# SECRET_KEY with a default of _DEV_SECRET, so the app silently signs JWTs
# with a well-known development key.
SECRET_KEY=...
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

DATABASE_URL=postgresql://caseflow:caseflow_dev@db:5432/caseflow_mb
APP_DATABASE_URL=postgresql://caseflow_app:caseflow_app_dev@db:5432/caseflow_mb

ANTHROPIC_API_KEY=...            # required for summarize / intake / demo chat
AWS_ACCESS_KEY_ID=...            # required for document upload
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=ca-central-1
AWS_S3_BUCKET=...
LANGFUSE_PUBLIC_KEY=...          # optional — tracing
LANGFUSE_SECRET_KEY=...
```

```bash
docker compose up -d
docker compose exec backend alembic upgrade head    # includes the RLS migrations
docker compose exec backend python seed.py          # 2 firms, 2 lawyers, clients, cases
```

| | |
|---|---|
| App | http://localhost:3000 |
| Public demo | http://localhost:3000/demo |
| API docs (Swagger) | http://localhost:8000/docs |

Log in as either seeded firm — `lawyer@caseflow.mb` / `Demo1234!` or `bob@jones.law` / `Jones1234!`.

---

## Tech stack

**Backend** — Python 3.12 · FastAPI · SQLAlchemy 2.0 · Alembic · PostgreSQL 16 (RLS) · Pydantic v2 · python-jose (JWT) · bcrypt · boto3 · Anthropic SDK · LangGraph + `langgraph-checkpoint-postgres` · psycopg v3 · FastMCP · Langfuse · Gunicorn/Uvicorn

**Frontend** — Next.js 16 (App Router) · React 19 · TypeScript · Tailwind CSS v4 · Axios (JWT interceptor) · React Hook Form + Zod · Lucide

**Infrastructure** — AWS EC2 (t3.micro) · RDS PostgreSQL · S3 · Elastic IP · Docker Compose · GitHub Actions (push to `main` → build and restart containers on EC2)

---

## Design decisions and trade-offs

| Decision | Reasoning |
|---|---|
| **404, not 403, for cross-tenant resources** | A 403 confirms the resource exists. For a competitor's client list, existence *is* the leak. |
| **JWT carries user ID only** | `firm_id` is resolved from the database on every request. A token that carried `firm_id` would keep working after a user's firm membership changed. |
| **Two DB roles** | `DATABASE_URL` (owner) for Alembic; `APP_DATABASE_URL` (`caseflow_app`, non-superuser) for the running app, because a superuser silently bypasses RLS and the tests would pass for the wrong reason. |
| **S3 for files, Postgres for metadata** | Presigned URLs are minted on demand, never stored — a leaked database row can't be replayed into a download. |
| **Summarization is a separate endpoint from upload** | Upload stays fast and deterministic; a slow or failing Anthropic call can't take the upload path down with it. |
| **Sonnet for lawyers, Haiku for the public demo** | Quality where a human relies on the output; latency and cost where anonymous traffic does. |
| **Static HTA table over model recall** | Prevents fabricated statute citations in a legal document. |
| **Langfuse from the start** | Debugging a 4-node agent from application logs alone is guesswork; per-node spans and token counts made the parallel fan-in behaviour visible. |

---

## Scope and limitations

Honest about what this is: a portfolio build, not a product with customers.

- Tests cover **tenant isolation specifically** — that's the risk I set out to prove. Business-logic and frontend test coverage is thin.
- The demo's rate limiter is in-process, so it resets on deploy and wouldn't hold across multiple instances. Redis is the real answer.
- Single EC2 instance, no autoscaling or blue/green — deploys are a brief restart.
- Inline code comments are partly in Chinese (my working language while building). Translation is in progress.
- The clients REST API is complete; a dedicated clients management UI is not yet built.

---

<details>
<summary><b>API reference</b></summary>

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Create a user |
| POST | `/auth/login` | Login → JWT |
| GET | `/auth/me` | Current user + firm |
| GET | `/clients` | List clients (firm-scoped, search + pagination) |
| POST | `/clients` | Create client |
| GET | `/clients/{id}` | Client detail |
| PATCH | `/clients/{id}` | Update client |
| DELETE | `/clients/{id}` | Delete client |
| GET | `/cases` | List cases (filter by status / client) |
| POST | `/cases` | Create case |
| GET | `/cases/{id}` | Case detail |
| PATCH | `/cases/{id}` | Update case |
| DELETE | `/cases/{id}` | Delete case |
| POST | `/cases/{id}/documents` | Upload to S3 |
| GET | `/cases/{id}/documents` | List documents |
| GET | `/cases/{id}/documents/{doc_id}/download` | Presigned download URL |
| DELETE | `/cases/{id}/documents/{doc_id}` | Delete document |
| POST | `/cases/{id}/documents/{doc_id}/summarize` | Claude summary |
| POST | `/cases/{id}/intake` | Intake agent Phase 1 |
| POST | `/cases/{id}/intake/{thread_id}/decision` | Intake agent Phase 2 |
| POST | `/demo/chat` | Public demo chat (rate-limited) |

Every authenticated endpoint is firm-scoped at both layers.

</details>

<details>
<summary><b>Project structure</b></summary>

```
CaseFlow-AI-Legal-Assistant/
├── backend/
│   ├── main.py                  FastAPI app, CORS, PostgresSaver lifespan
│   ├── config.py                Pydantic settings
│   ├── database.py              Engine + pool-checkout RESET of tenant GUC
│   ├── dependencies.py          JWT auth + get_db_with_rls (SET LOCAL)
│   ├── security.py              bcrypt + JWT helpers
│   ├── observability.py         Langfuse client
│   ├── seed.py                  2 firms, 2 lawyers, clients, cases
│   ├── mcp_server.py            FastMCP server, per-firm API key auth
│   ├── models/                  firm · user · client · case · document · intake_session
│   ├── routers/                 auth · clients · cases · documents · intake · demo
│   ├── schemas/                 Pydantic request/response models
│   ├── services/
│   │   ├── s3.py                Upload, delete, presigned URLs
│   │   ├── ai.py                Document summarization (Sonnet)
│   │   ├── intake_agent.py      LangGraph DAG + human-in-the-loop
│   │   └── hta_reference.py     Static Manitoba HTA lookup
│   ├── alembic/versions/        Migrations, including the RLS policies
│   ├── scripts/                 Manual verification helpers
│   ├── tests/                   36 cross-tenant isolation tests
│   └── Dockerfile[.prod]
├── frontend/
│   ├── app/
│   │   ├── login/               Two-firm login (demo credentials pre-filled)
│   │   ├── cases/               List, detail, documents, intake review UI
│   │   └── demo/                Public chat, no auth
│   ├── lib/api.ts               Axios client + JWT interceptor
│   └── Dockerfile[.prod]
├── docker-compose.yml           Development stack
├── docker-compose.prod.yml      Production stack
└── .github/workflows/deploy.yml CI/CD → EC2
```

</details>
