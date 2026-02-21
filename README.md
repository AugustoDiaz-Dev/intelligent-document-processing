# Intelligent Document Processing System (Project 2)

This folder contains the **boilerplate + first working steps** for **Project 2: Intelligent Document Processing System** from `project.md`.

## What you can do now

- Upload an invoice PDF → OCR → extract structured data → validate → store
- View processed documents and review queue

## Requirements

- Python **3.11+**
- Docker (for Postgres)
- PaddleOCR (for local OCR - optional, can use mock for now)

## Quickstart

Start Postgres:

```bash
cd "/Users/augustodiaz/Downloads/MVP-lab/fintech-portfolio /doc-processing-system"
docker compose up -d
```

Create a virtualenv and install:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the API:

```bash
export DATABASE_URL="postgresql+asyncpg://docproc:docproc@localhost:5432/docproc"
uvicorn app.main:app --reload --port 8001
```

## API

- `GET /health`
- `POST /documents/upload` (multipart form upload: `file=<pdf>`)
- `GET /documents/{id}`
- `GET /review/queue`

Example upload:

```bash
curl -X POST "http://localhost:8001/documents/upload" \
  -F "file=@invoice.pdf"
```

## Tracking

See `STATUS.md` for a checklist of what's completed and what remains for Project 2.
