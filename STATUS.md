## Project 2: Intelligent Document Processing System — Status

This file tracks what's been implemented in `doc-processing-system/` and what remains from **Project 2** in `project.md`.

---

### ✅ Achieved (boilerplate + first steps)

- **Service scaffold**: FastAPI app (`app/main.py`)
- **Config + logging**: env-driven settings + JSON logging (`app/core/`)
- **Database**: async SQLAlchemy engine/session (`app/db/session.py`)
- **Data models**: `documents`, `extractions`, `validations` tables (`app/db/models.py`)
- **OCR abstraction**: base interface + mock implementation (`app/ocr/base_ocr.py`, `app/ocr/mock_ocr.py`)
- **Extraction layer**: simple pattern-based extraction (`app/extraction/extractor.py`)
- **Validation engine**: rule-based validation (`app/validation/rule_engine.py`, `app/validation/validator.py`)
- **Confidence scoring**: weighted combination of OCR/extraction/validation (`app/confidence/confidence.py`)
- **Processing pipeline**: orchestrator with async support (`app/pipeline/pipeline.py`)
- **API endpoints**:
  - `GET /health`
  - `POST /documents/upload` (upload PDF → process → store)
  - `GET /documents/{id}` (view document details)
  - `GET /review/queue` (list documents needing review)
- **Local infra**: `docker-compose.yml` for Postgres

---

### ✅ Completed (this session)

#### 1) OCR Abstraction
- [x] Base OCR interface
- [x] Mock OCR engine (for dev/testing)
- [x] **LocalOCREngine using PaddleOCR** — `app/ocr/engines.py` (lazy-init, async, configurable lang/GPU)
- [x] **CloudOCREngine placeholder for AWS Textract** — `app/ocr/engines.py` (full API shape, needs boto3 + creds)
- [x] **OCR factory wired up** — `app/ocr/factory.py` now returns real engines instead of raising NotImplementedError

#### 2) Extraction Layer
- [x] Basic extraction (pattern-based, improved regex + date parsing)
- [x] **LLM-based structured extraction** — `EXTRACTION_MODE=llm` → OpenAI JSON mode, all 6 fields, graceful fallback
- [x] **Per-field confidence scores** — both LLM and simple paths return `field_confidences` dict

#### 3) Validation Engine
- [x] Rule engine framework
- [x] Line items sum validation
- [x] Tax ID format validation
- [x] Date consistency check
- [x] **Duplicate invoice detection** — `existing_invoice_numbers` forwarded from DB query

#### 4) Confidence Scoring
- [x] Weighted OCR + extraction + validation combination
- [x] **ConfidenceResult dataclass** with `overall`, `ocr_score`, `extraction_score`, `validation_score`
- [x] **Per-field confidence scores** propagated through pipeline → stored in `extractions.field_confidences`

#### 5) Processing Pipeline
- [x] Async orchestrator
- [x] Logging of each step
- [x] **Idempotent processing** — skips re-processing if status == "completed"
- [x] **Audit trail** — `processing_events` table with step, status, duration per stage

#### 6) API
- [x] `POST /documents/upload`
- [x] `GET /documents/{id}` — now includes `events` (audit trail) and `field_confidences`
- [x] `GET /review/queue`
- [x] `GET /health`

#### 7) Dataset
- [x] **Sample invoices**: `datasets/invoices/invoice_001.txt`, `invoice_002.txt`, `invoice_003.txt`

#### 8) Tests (target coverage ≥ 80%)
- [x] Rule validation tests — expanded to cover all 4 rules (13 tests)
- [x] **OCR mocked tests** — `tests/test_ocr.py` (base class, MockOCR, factory)
- [x] **Extractor tests** — `tests/test_extractor.py` (all fields, confidence, edge cases)
- [x] **End-to-end pipeline test** — `tests/test_pipeline.py` (happy path, idempotency, OCR failure, duplicate detection)
- [x] **pytest-cov** configured with ≥80% floor in `pyproject.toml`

#### 9) CI Pipeline
- [x] `.github/workflows/ci-doc-processing.yml` — lint + tests + integration smoke

#### 10) Architecture Documentation
- [x] `docs/architecture/overview.md` — pipeline diagram, OCR abstraction, DB schema, status lifecycle

---

### 🚫 Requires External Credentials (implement when keys are available)

- [ ] **EXTRACTION_MODE=llm** in production — requires `OPENAI_API_KEY` (code is complete, just needs the key)
- [ ] **OCR_PROVIDER=paddleocr** — requires `pip install paddlepaddle paddleocr` (heavy deps, ~2GB)
- [ ] **OCR_PROVIDER=aws_textract** — requires `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `pip install boto3`
