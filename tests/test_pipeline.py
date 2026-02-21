"""End-to-end processing pipeline test — fully mocked DB and OCR."""
from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.extraction.extractor import ExtractedData
from app.ocr.base_ocr import OCRResult
from app.ocr.mock_ocr import MockOCREngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(status: str = "pending") -> MagicMock:
    doc = MagicMock()
    doc.id = uuid.uuid4()
    doc.status = status
    doc.filename = "test_invoice.pdf"
    return doc


def _make_session(doc: MagicMock) -> AsyncMock:
    session = AsyncMock()
    session.get = AsyncMock(return_value=doc)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    # Mock execute for the existing invoice numbers query
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)
    return session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pipeline_processes_document_successfully() -> None:
    """Full pipeline runs OCR → extract → validate → persist."""
    doc = _make_doc()
    session = _make_session(doc)
    ocr_engine = MockOCREngine()

    from app.pipeline.pipeline import ProcessingPipeline
    pipeline = ProcessingPipeline(session, ocr_engine)
    await pipeline.process_document(doc.id, b"fake pdf bytes")

    # Document status should have been set
    assert doc.status in ("completed", "review")
    # Session should have been committed
    session.commit.assert_called()


@pytest.mark.asyncio
async def test_pipeline_skips_already_completed_document() -> None:
    """Idempotency: completed documents are not re-processed."""
    doc = _make_doc(status="completed")
    session = _make_session(doc)
    ocr_engine = MockOCREngine()

    from app.pipeline.pipeline import ProcessingPipeline
    pipeline = ProcessingPipeline(session, ocr_engine)
    await pipeline.process_document(doc.id, b"bytes")

    # Status should remain completed, no commit needed
    assert doc.status == "completed"
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_raises_on_missing_document() -> None:
    """Pipeline raises ValueError if document not found in DB."""
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    ocr_engine = MockOCREngine()

    from app.pipeline.pipeline import ProcessingPipeline
    pipeline = ProcessingPipeline(session, ocr_engine)

    with pytest.raises(ValueError, match="not found"):
        await pipeline.process_document(uuid.uuid4(), b"bytes")


@pytest.mark.asyncio
async def test_pipeline_marks_failed_on_ocr_error() -> None:
    """If OCR raises, the document is marked 'failed'."""
    doc = _make_doc()
    session = _make_session(doc)

    failing_ocr = AsyncMock()
    failing_ocr.extract_text = AsyncMock(side_effect=RuntimeError("OCR hardware error"))

    from app.pipeline.pipeline import ProcessingPipeline
    pipeline = ProcessingPipeline(session, failing_ocr)

    with pytest.raises(RuntimeError):
        await pipeline.process_document(doc.id, b"bytes")

    assert doc.status == "failed"


@pytest.mark.asyncio
async def test_pipeline_detects_duplicate_invoice() -> None:
    """When an existing invoice_number is returned by the DB, duplicate rule fails."""
    doc = _make_doc()
    session = _make_session(doc)

    # Make the DB return an existing invoice number
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ["INV-2024-001"]
    session.execute = AsyncMock(return_value=mock_result)

    ocr_engine = MockOCREngine()   # MockOCR returns INV-2024-001

    from app.pipeline.pipeline import ProcessingPipeline
    pipeline = ProcessingPipeline(session, ocr_engine)
    await pipeline.process_document(doc.id, b"bytes")

    # Duplicate detected → should be sent to review (not completed)
    assert doc.status == "review"
