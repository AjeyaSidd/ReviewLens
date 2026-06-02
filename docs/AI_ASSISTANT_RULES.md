# AI Assistant Rules — App Review Intelligence

**Project root:** `C:\Users\Ajeya Siddhartha\Projects\app-review-intelligence`

**Canonical references (read before coding):**

1. [ARCHITECTURE.md](./ARCHITECTURE.md) — system design, stack, APIs, data model
2. **This file** — implementation phases, testing, logging, tooling

Cursor also loads: `.cursor/rules/app-review-intelligence.mdc`

---

## A. Mandatory assistant behavior

### A.1 Documentation and artifacts

- **Never** create project artifacts only in chat memory (no “here’s a README” without writing a file).
- **Always** write deliverables under the project folder: `docs/`, `backend/`, `frontend/`, `supabase/`, etc.
- Architecture changes → update `docs/ARCHITECTURE.md` first, then implement.

### A.2 Tests

- **Write tests for all production code** (backend services, API routes, utilities; frontend components and API client where applicable).
- Backend: **pytest** under `backend/tests/` mirroring `backend/app/` structure.
- Frontend: **Vitest** or **Jest** + React Testing Library under `frontend/__tests__/` or colocated `*.test.tsx`.
- Each phase is not complete until tests for that phase pass via `make test`.

### A.3 Logging

- **Log every significant function and execution flow** to **log files**, not only stdout.
- Backend: Python `logging` → `backend/logs/app.log` (rotate or daily file e.g. `app-YYYY-MM-DD.log`).
- Log at minimum: sync start/end per app, scrape counts, prune counts, sentiment batch id/size, embed batch, rollup, chat request (app_id, no PII), errors with stack traces.
- Frontend: server-side/API route logs if any; browser console only for dev — optional `frontend/logs/` for SSR scripts.
- Use structured fields where helpful: `catalog_app_id`, `job_id`, `duration_ms`.

### A.4 Secrets and environment

- Store secrets in **`.env`** at repo root (and/or `backend/.env` if split). **Never commit `.env`.**
- Provide **`.env.example`** with empty placeholders and comments.
- **`.gitignore`** must include `.env`, `.env.local`, `backend/.env`, `frontend/.env.local`.

### A.5 Makefile

- Maintain a root **`Makefile`** with common targets. Implementation must keep targets working as phases add code.
- See [Makefile](../Makefile) in project root.

### A.6 Implementation discipline

- Follow [ARCHITECTURE.md](./ARCHITECTURE.md) exactly unless the user approves a documented change.
- Max **15** active catalog apps; max **2000** latest reviews per app (combined Play + iOS); **prune after sync**.
- Sentiment: **Gemini bulk on review text**, not star-rating proxy.
- No Redis/Celery in v1; use cron + `refresh` background tasks.

---

## B. Implementation phases (detailed)

### Phase 1 — Foundation: database, admin API, scrape, prune, sentiment

**Goal:** Admin can add apps; background sync stores reviews with Gemini sentiment; data in Supabase.

**Backend**

- `supabase/migrations/001_init.sql`: `catalog_apps`, `reviews`, `daily_rollups`, pgvector extension, indexes, HNSW.
- FastAPI app skeleton: `backend/app/main.py`, config from env, Supabase client.
- Admin routes + `X-Admin-Key` dependency: `POST/DELETE/GET /admin/apps`, `POST .../refresh`, `POST /admin/sync-all`.
- Scrapers: `services/scrape_play.py`, `services/scrape_ios.py`, normalized review schema.
- `services/sync_app.py`: scrape → upsert → prune (2000) → **sentiment bulk (Gemini)** → stub embed step.
- `services/sentiment.py`: batch reviews to Gemini Flash, JSON scores -1..1, labels.
- Enforce `MAX_ACTIVE_APPS=15`, `MAX_REVIEWS_PER_APP=2000`.
- Logging to `backend/logs/`; pytest for scraper normalize, prune logic, admin auth, sentiment parser.

**Deliverables**

- Deployable Dockerfile for Koyeb (optional in phase 1 end).
- `.env.example` with all keys.

**Exit criteria**

- Via `/docs`: add app → refresh → `scrape_status=ready`, reviews in Supabase with `sentiment_score` on text reviews.
- `make test` passes for phase 1 tests.

---

### Phase 2 — Embeddings and vector search

**Goal:** Text reviews have 1536-dim embeddings; similarity search works.

**Backend**

- `services/embed.py`: Gemini `gemini-embedding-001`, batch, truncate title+body, skip empty text.
- Integrate into sync pipeline after sentiment.
- SQL function or query: match by `catalog_app_id` + optional date filter + `ORDER BY embedding <=> query`.
- Tests: embed skip on empty, dimension 1536, vector query mocked.

**Exit criteria**

- Embeddings populated; manual/scripted similarity query returns relevant rows.
- `make test` passes.

---

### Phase 3 — Daily rollups and trends API

**Goal:** Precomputed trends for charts.

**Backend**

- `services/rollup.py`: aggregate per `catalog_app_id` + `date` (`avg_rating`, `avg_sentiment`, star counts, count).
- `GET /apps/{id}/trends?from=&to=`
- Public `GET /catalog`, `GET /apps/{id}` (ready apps only).
- Tests: rollup math, trends API filters.

**Exit criteria**

- Rollups correct for a test app with known reviews.
- `make test` passes.

---

### Phase 4 — Hybrid RAG chat

**Goal:** PM questions answered with citations.

**Backend**

- `services/query_planner.py`: extract dates, semantic query, intent (trend vs semantic).
- `services/chat.py`: SQL rollups + pgvector top-K + Gemini Flash prompt with citation rules.
- `POST /apps/{id}/chat` response shape per ARCHITECTURE.md.
- Tests: planner parsing (fixtures), chat with mocked Gemini and DB.

**Exit criteria**

- Example questions return answer + citations + metrics.
- `make test` passes.

---

### Phase 5 — Next.js frontend (Vercel)

**Goal:** Public UI for catalog, trends, chat.

**Frontend**

- Next.js App Router, Tailwind, `lib/api.ts` → Koyeb `NEXT_PUBLIC_API_URL`.
- `/` catalog grid; `/apps/[id]` trends (Recharts) + chat panel + citations.
- Loading/error states; display `last_synced_at`.
- Tests: component tests for catalog card, chat message list (mocked API).

**Ops**

- Vercel project linked; env `NEXT_PUBLIC_API_URL`; CORS on backend updated.

**Exit criteria**

- End-to-end demo from browser.
- `make test` passes (frontend + backend).

---

### Phase 6 — Production ops

**Goal:** Reliable daily sync and guardrails.

- External cron → `POST /admin/sync-all` with admin key.
- Rate limits on public chat (optional middleware).
- Failed scrape visible in `GET /admin/apps`.
- Document deploy steps in `docs/DEPLOY.md` (not README in chat only).
- Full `make lint` clean; `make docker-build` produces runnable image.

**Exit criteria**

- Daily sync runs; 15-app cap enforced; logs show job history.
- `make test` and `make lint` pass.

---

## C. File layout expectations

```text
app-review-intelligence/
  .cursor/rules/app-review-intelligence.mdc
  .env.example
  .gitignore                 # includes .env
  Makefile
  docs/
    ARCHITECTURE.md
    AI_ASSISTANT_RULES.md      # this file
    DEPLOY.md                  # Phase 6
  backend/
    app/
    tests/
    logs/                      # gitignored
  frontend/
  supabase/migrations/
```

---

## D. Commands (Makefile)

Use `make help` for the current list. Standard targets:

| Target | Purpose |
|--------|---------|
| `make install` | Install backend + frontend dependencies |
| `make build` | Build frontend production bundle |
| `make test` | Run backend pytest + frontend tests |
| `make lint` | Ruff/black/mypy + eslint |
| `make run-api` | Local FastAPI dev server |
| `make run-web` | Local Next.js dev server |
| `make docker-build` | Build API Docker image |

---

## E. Prompt template for agents

When starting work, say:

> Implement Phase N per `docs/ARCHITECTURE.md` and `docs/AI_ASSISTANT_RULES.md`. Write tests and file logs. Do not commit `.env`.
