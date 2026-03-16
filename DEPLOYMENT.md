# Doc Processing System — Deployment Guide

This guide explains the **current state** of the project, how to run it locally, and how to deploy it for recruiters (production-like URL).

---

## Current state

### What’s done (production-ready core)

| Area | Status | Notes |
|------|--------|--------|
| **API** | ✅ | FastAPI with `/health`, `/documents/upload`, `/documents/{id}`, `/review/queue` |
| **Database** | ✅ | Async Postgres (SQLAlchemy + asyncpg), migrations via `init_db` |
| **OCR** | ✅ | Mock (default), PaddleOCR and AWS Textract placeholders |
| **Extraction** | ✅ | Simple (regex) + LLM (OpenAI) modes |
| **Validation** | ✅ | Rule engine (line items, tax ID, dates, duplicate detection) |
| **Pipeline** | ✅ | Async pipeline, audit trail, idempotency |
| **Tests** | ✅ | ≥80% coverage, CI workflow |
| **Docs** | ✅ | `STATUS.md`, `docs/architecture/overview.md` |

### What’s needed for “live” demo

1. **Run locally**: Docker (Postgres) + run API → works once Postgres is up.
2. **Deploy**: Host the API + Postgres (or managed DB) so recruiters can open a URL and use `/docs` or upload a PDF.

**Distance to production:** The app is **feature-complete** for a demo. To go live you only need:
- A host (e.g. Railway, Render, Fly.io).
- A Postgres instance (included by these platforms).
- Environment variables (e.g. `DATABASE_URL`, optional `OPENAI_API_KEY` for LLM extraction).

---

## Run locally

### 1. Start Postgres

Docker must be running (Docker Desktop on Mac).

```bash
cd doc-processing-system
docker compose up -d
```

Postgres listens on **port 5433** (host) with DB `docproc`, user/password `docproc`.

### 2. Environment

Copy and adjust if needed:

```bash
cp .env.example .env
# Edit .env: set DATABASE_URL (see below)
```

Use this URL with the above `docker compose`:

```env
DATABASE_URL=postgresql+asyncpg://docproc:docproc@localhost:5433/docproc
```

Optional for LLM extraction:

```env
EXTRACTION_MODE=llm
OPENAI_API_KEY=sk-...
```

### 3. Install and run API

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8001
```

- API: http://localhost:8001  
- Swagger UI: http://localhost:8001/docs  

### 4. Quick test

```bash
curl http://localhost:8001/health
curl -X POST "http://localhost:8001/documents/upload" -F "file=@path/to/invoice.pdf"
```

---

## Deploy for recruiters (live URL)

Goal: one public URL (e.g. `https://your-app.railway.app`) where recruiters can open `/docs` and try the API.

### Option A: Railway (recommended for demos)

1. **Sign up**: [railway.app](https://railway.app) (GitHub login).
2. **New project** → “Deploy from GitHub repo” (or use Railway CLI).
3. **Add Postgres**: In the project, “New” → “Database” → “Postgres”. Railway sets `DATABASE_URL` automatically for services in the same project.
4. **Add service from repo**:
   - Connect the `doc-processing-system` repo (or the repo that contains it).
   - Root directory: set to `doc-processing-system` if the repo is the whole workspace; otherwise use the path where `app/` and `pyproject.toml` live.
   - Build: Railway can use the **Dockerfile** (see repo) or **Nixpacks** (auto-detects Python).
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. **Variables**: In the service “Variables” tab, add:
   - `DATABASE_URL` — usually auto-injected if Postgres is in the same project; otherwise copy from Postgres service.
   - Optional: `EXTRACTION_MODE=llm`, `OPENAI_API_KEY=sk-...`, `OCR_PROVIDER=mock`.
6. **Deploy**: Push to the connected branch or trigger deploy. Railway gives you a URL like `https://your-app.railway.app`.
7. **Share**: Send recruiters `https://your-app.railway.app/docs` so they can try the API.

### Option B: Render

1. **Sign up**: [render.com](https://render.com).
2. **New Web Service** → connect GitHub repo.
3. **Build**:
   - Root directory: `doc-processing-system` (if needed).
   - Environment: Python 3.
   - Build: `pip install -e ".[dev]"` or `pip install -e .` (and use Dockerfile if you add one).
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. **Database**: “New” → “PostgreSQL”. Copy the “Internal Database URL” (or “External” if your app runs elsewhere).
5. **Environment**: Add `DATABASE_URL` (and optional `OPENAI_API_KEY`, `EXTRACTION_MODE=llm`).
6. **Deploy**: Save; Render builds and deploys. Use the generated URL (e.g. `https://your-service.onrender.com`) and share `/docs`.

### Option C: Fly.io

1. **Install**: `curl -L https://fly.io/install.sh | sh` and `fly auth login`.
2. **In `doc-processing-system`**: `fly launch` (creates `fly.toml`). Choose a Postgres app when prompted or add later with `fly postgres create`.
3. **Secrets**: `fly secrets set DATABASE_URL=...` (and optional `OPENAI_API_KEY`, etc.).
4. **Deploy**: `fly deploy`. Share the URL (e.g. `https://your-app.fly.dev`) and `/docs`.

---

## Production checklist (before sharing with recruiters)

- [ ] **Docker running** (for local) or **host chosen** (Railway / Render / Fly).
- [ ] **Postgres** running (local with `docker compose` or managed on the host).
- [ ] **DATABASE_URL** set correctly (port **5433** for local docker-compose).
- [ ] **OPENAI_API_KEY** set if you use `EXTRACTION_MODE=llm` (optional; `simple` works without it).
- [ ] **No secrets in repo** — use platform env vars; keep `.env` in `.gitignore`.
- [ ] **README** points to this guide or a one-line “Deploy: see DEPLOYMENT.md”.

---

## Environment variables reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | `postgresql+asyncpg://user:pass@host:port/dbname` |
| `OCR_PROVIDER` | No | `mock` | `mock` \| `paddleocr` \| `aws_textract` |
| `EXTRACTION_MODE` | No | `simple` | `simple` \| `llm` |
| `OPENAI_API_KEY` | If LLM | — | Required when `EXTRACTION_MODE=llm` |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `APP_ENV` | No | `dev` | `dev` \| `prod` |

---

## Summary

- **State**: The project is in good shape for a portfolio demo: API, DB, pipeline, tests, and docs are in place.
- **Run locally**: Start Docker → `docker compose up -d` → set `DATABASE_URL` (port 5433) → `uvicorn app.main:app --reload --port 8001`.
- **Go live**: Use **Railway** or **Render** (or Fly.io), add Postgres, set env vars, deploy. Share the `/docs` URL with recruiters so they can test the API from the browser.
