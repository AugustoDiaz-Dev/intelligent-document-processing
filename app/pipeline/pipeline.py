"""Processing pipeline — orchestrates OCR → extraction → validation → confidence.

Improvements over v1:
- Idempotent: skips re-processing if document is already completed (#D)
- Audit trail: writes ProcessingEvent rows for every step (#E)
- Duplicate invoice detection: fetches known invoice numbers before validation (#C)
- Per-field confidence: passes ExtractedData to compute_confidence (#F)
"""
from __future__ import annotations

import logging
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.confidence.confidence import ConfidenceResult, compute_confidence
from app.db.models import Document, Extraction, ProcessingEvent, Validation
from app.extraction.extractor import Extractor
from app.ocr.base_ocr import OCREngine
from app.validation.validator import Validator

logger = logging.getLogger(__name__)


class ProcessingPipeline:
    def __init__(self, session: AsyncSession, ocr_engine: OCREngine) -> None:
        self._session = session
        self._ocr_engine = ocr_engine
        self._extractor = Extractor()
        self._validator = Validator()

    # ------------------------------------------------------------------ #
    #  Public entry point                                                  #
    # ------------------------------------------------------------------ #

    async def process_document(self, document_id: uuid.UUID, pdf_bytes: bytes) -> None:
        doc = await self._session.get(Document, document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        # ── Idempotency guard (#D) ─────────────────────────────────────
        if doc.status == "completed":
            logger.info(
                "processing_skipped_idempotent",
                extra={"document_id": str(document_id), "status": doc.status},
            )
            return

        try:
            doc.status = "processing"
            await self._session.flush()

            # ── Step 1: OCR ───────────────────────────────────────────
            ocr_result = await self._run_step(
                document_id,
                step="ocr",
                coro=self._ocr_engine.extract_text(pdf_bytes),
            )
            logger.info(
                "ocr_complete",
                extra={"document_id": str(document_id), "confidence": ocr_result.confidence},
            )

            # ── Step 2: Extraction ────────────────────────────────────
            extracted = await self._run_step(
                document_id,
                step="extraction",
                coro=self._extractor.extract(ocr_result.text),
            )
            logger.info(
                "extraction_complete",
                extra={
                    "document_id": str(document_id),
                    "invoice_number": extracted.invoice_number,
                    "confidence": extracted.extraction_confidence,
                },
            )

            # ── Step 3: Fetch existing invoice numbers for dup check (#C) ──
            existing_invoice_numbers = await self._get_existing_invoice_numbers(document_id)

            # ── Step 4: Validation ────────────────────────────────────
            validation_results = self._validator.validate(
                extracted,
                existing_invoice_numbers=existing_invoice_numbers,
            )
            await self._emit_event(
                document_id,
                step="validation",
                status="completed",
                detail=f"{len(validation_results)} rules evaluated, "
                       f"{sum(1 for r in validation_results if r.passed)} passed",
            )
            logger.info(
                "validation_complete",
                extra={"document_id": str(document_id), "rule_count": len(validation_results)},
            )

            # ── Step 5: Confidence scoring (#F) ──────────────────────
            confidence: ConfidenceResult = compute_confidence(
                ocr_confidence=ocr_result.confidence,
                extraction_confidence=extracted.extraction_confidence,
                validation_results=validation_results,
                extracted=extracted,
            )
            await self._emit_event(
                document_id,
                step="confidence",
                status="completed",
                detail=f"overall={confidence.overall:.3f}",
            )

            # ── Step 6: Persist extraction ────────────────────────────
            extraction = Extraction(
                document_id=document_id,
                vendor_name=extracted.vendor_name,
                tax_id=extracted.tax_id,
                invoice_number=extracted.invoice_number,
                total_amount=extracted.total_amount,
                invoice_date=extracted.invoice_date,
                due_date=extracted.due_date,
                line_items=extracted.line_items or [],
                field_confidences=confidence.per_field or None,
                ocr_text=ocr_result.text,
                ocr_confidence=ocr_result.confidence,
                extraction_confidence=extracted.extraction_confidence,
            )
            self._session.add(extraction)

            # ── Step 7: Persist validations ───────────────────────────
            for vr in validation_results:
                self._session.add(
                    Validation(
                        document_id=document_id,
                        rule_name=vr.rule_name,
                        passed=vr.passed,
                        score=vr.score,
                        message=vr.message,
                    )
                )

            # ── Determine final document status ───────────────────────
            all_passed = all(vr.passed for vr in validation_results)
            if confidence.overall < 0.6 or not all_passed:
                doc.status = "review"
            else:
                doc.status = "completed"

            await self._session.commit()

            await self._emit_event(
                document_id,
                step="completed",
                status="completed",
                detail=f"final_status={doc.status} confidence={confidence.overall:.3f}",
            )
            await self._session.commit()

            logger.info(
                "processing_complete",
                extra={
                    "document_id": str(document_id),
                    "status": doc.status,
                    "confidence": confidence.overall,
                },
            )

        except Exception:
            logger.exception("processing_failed", extra={"document_id": str(document_id)})
            doc.status = "failed"
            await self._session.commit()
            await self._emit_event(
                document_id, step="failed", status="failed", detail="Unhandled exception"
            )
            await self._session.commit()
            raise

    # ------------------------------------------------------------------ #
    #  Audit trail helper (#E)                                            #
    # ------------------------------------------------------------------ #

    async def _emit_event(
        self,
        document_id: uuid.UUID,
        *,
        step: str,
        status: str,
        detail: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Append a ProcessingEvent row for the audit trail."""
        event = ProcessingEvent(
            document_id=document_id,
            step=step,
            status=status,
            detail=detail,
            duration_ms=duration_ms,
        )
        self._session.add(event)
        await self._session.flush()

    async def _run_step(self, document_id: uuid.UUID, *, step: str, coro):
        """Run an async step, emit start/end audit events, and measure duration."""
        await self._emit_event(document_id, step=step, status="started")
        t0 = time.monotonic()
        try:
            result = await coro
            duration_ms = int((time.monotonic() - t0) * 1000)
            await self._emit_event(
                document_id, step=step, status="completed", duration_ms=duration_ms
            )
            return result
        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            await self._emit_event(
                document_id,
                step=step,
                status="failed",
                detail=str(exc),
                duration_ms=duration_ms,
            )
            raise

    # ------------------------------------------------------------------ #
    #  Duplicate invoice detection helper (#C)                            #
    # ------------------------------------------------------------------ #

    async def _get_existing_invoice_numbers(
        self, current_document_id: uuid.UUID
    ) -> set[str]:
        """Return all invoice numbers already stored (excluding the current doc)."""
        stmt = select(Extraction.invoice_number).where(
            Extraction.document_id != current_document_id,
            Extraction.invoice_number.is_not(None),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return {r for r in rows if r}
