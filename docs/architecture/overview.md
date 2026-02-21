# Architecture Overview — Intelligent Document Processing System

> **Project 2** · `project-2/doc-processing-system/`

## System Overview

The Doc Processing System automates extraction and validation of business documents (invoices). It accepts a PDF upload, runs OCR, extracts structured fields via LLM or regex, validates the data with deterministic rules, and returns a confidence-scored result.

```
                 ┌──────────────────┐
   PDF Upload    │                  │  POST /documents/upload
  ──────────────▶│   FastAPI API    │──────────────────────────▶  ProcessingPipeline
                 │   (async)        │                                     │
   GET detail    │                  │  GET /documents/{id}                │
  ──────────────▶│                  │◀────────────────────────────────────┤
                 │                  │                                     │
   Review queue  │                  │  GET /review/queue                  │
  ──────────────▶└──────────────────┘                                     │
                                                                          ▼
                                                              ┌───────────────────────┐
                                                              │  PostgreSQL            │
                                                              │  documents             │
                                                              │  extractions           │
                                                              │  validations           │
                                                              │  processing_events     │
                                                              └───────────────────────┘
```

---

## Processing Pipeline

```
PDF bytes
   │
   ▼  Step 1
OCREngine.extract_text()           ← mock | PaddleOCR (local) | AWS Textract
   │ OCRResult(text, confidence)
   ▼  Step 2
Extractor.extract()                ← simple (regex) | LLM (OpenAI JSON mode)
   │ ExtractedData(vendor, tax_id, invoice_number, total, dates, line_items,
   │               field_confidences)
   ▼  Step 3
_get_existing_invoice_numbers()    ← DB query for duplicate detection
   │ set[str]
   ▼  Step 4
Validator.validate()
   ├─ line_items_sum               ← Σ(line items) ≈ total_amount
   ├─ tax_id_format                ← alphanumeric, 5–20 chars
   ├─ date_consistency             ← due_date ≥ invoice_date
   └─ duplicate_invoice            ← invoice_number not already in DB
   │ list[ValidationResult]
   ▼  Step 5
compute_confidence()               ← weighted: OCR(30%) + extract(40%) + validation(30%)
   │ ConfidenceResult(overall, per_field)
   ▼  Step 6
Persist Extraction + Validations + ProcessingEvents to DB
   │
   ▼
Document.status = "completed" | "review" | "failed"
```

Each step emits a `ProcessingEvent` row (audit trail) with step name, status, duration, and optional detail message.

---

## OCR Abstraction Layer

| Class | Provider | Notes |
|---|---|---|
| `MockOCREngine` | Synthetic text | Dev/test — zero deps |
| `LocalOCREngine` | PaddleOCR | Runs fully local; `pip install paddlepaddle paddleocr` |
| `CloudOCREngine` | AWS Textract | Placeholder; requires `boto3` + AWS credentials |

Selected via `OCR_PROVIDER` env var.

---

## Extraction Modes

| Mode | Class path | Config |
|---|---|---|
| `simple` | `_simple_extract()` in `Extractor` | `EXTRACTION_MODE=simple` (default) |
| `llm` | `_llm_extract()` via OpenAI JSON mode | `EXTRACTION_MODE=llm` + `OPENAI_API_KEY` |

LLM mode falls back to simple on failure.

---

## Database Schema

| Table | Purpose |
|---|---|
| `documents` | Document metadata + lifecycle status |
| `extractions` | All extracted fields + per-field confidence JSON |
| `validations` | One row per rule per document |
| `processing_events` | Audit trail — step × status × duration |

---

## Document Status Lifecycle

```
pending → processing → completed
                   ↘ review      (confidence < 0.6 or a rule failed)
                   ↘ failed      (unhandled exception)

completed → (idempotent — re-upload skipped)
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/documents/upload` | Upload PDF → run pipeline |
| `GET` | `/documents/{id}` | Full details incl. extraction, validations, audit trail |
| `GET` | `/review/queue` | Documents requiring human review |
