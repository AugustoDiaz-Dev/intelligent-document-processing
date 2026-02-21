from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Document
from app.db.session import get_session
from app.ocr.factory import get_ocr_engine
from app.pipeline.pipeline import ProcessingPipeline
from app.schemas import (
    DocumentDetailResponse,
    DocumentUploadResponse,
    ExtractionOut,
    ProcessingEventOut,
    ReviewQueueItem,
    ValidationOut,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    session: AsyncSession = Depends(get_session),
    file: UploadFile = File(...),
) -> DocumentUploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    content_type = file.content_type or "application/pdf"
    if content_type not in {"application/pdf"}:
        raise HTTPException(status_code=415, detail=f"Unsupported content_type={content_type!r}")

    pdf_bytes = await file.read()

    # Create document record
    doc = Document(filename=file.filename, content_type=content_type, status="pending")
    session.add(doc)
    await session.flush()

    # Process asynchronously (in a real app, use a task queue)
    ocr_engine = get_ocr_engine()
    pipeline = ProcessingPipeline(session, ocr_engine)
    await pipeline.process_document(doc.id, pdf_bytes)

    logger.info("document_uploaded", extra={"document_id": str(doc.id), "upload_filename": file.filename})
    return DocumentUploadResponse(document_id=doc.id, status=doc.status)


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> DocumentDetailResponse:
    stmt = (
        select(Document)
        .where(Document.id == document_id)
        .options(
            selectinload(Document.extraction),
            selectinload(Document.validations),
            selectinload(Document.events),
        )
    )
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    extraction_out = None
    if doc.extraction:
        extraction_out = ExtractionOut(
            vendor_name=doc.extraction.vendor_name,
            tax_id=doc.extraction.tax_id,
            invoice_number=doc.extraction.invoice_number,
            total_amount=doc.extraction.total_amount,
            invoice_date=doc.extraction.invoice_date,
            due_date=doc.extraction.due_date,
            line_items=doc.extraction.line_items or [],
            ocr_confidence=float(doc.extraction.ocr_confidence) if doc.extraction.ocr_confidence else None,
            extraction_confidence=float(doc.extraction.extraction_confidence)
            if doc.extraction.extraction_confidence
            else None,
            field_confidences=doc.extraction.field_confidences,
        )

    validations_out = [
        ValidationOut(
            rule_name=v.rule_name,
            passed=v.passed,
            score=float(v.score),
            message=v.message,
        )
        for v in doc.validations
    ]

    events_out = [
        ProcessingEventOut(
            step=e.step,
            status=e.status,
            detail=e.detail,
            duration_ms=e.duration_ms,
            created_at=e.created_at,
        )
        for e in doc.events
    ]

    return DocumentDetailResponse(
        id=doc.id,
        filename=doc.filename,
        status=doc.status,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        extraction=extraction_out,
        validations=validations_out,
        events=events_out,
    )


@router.get("/review/queue", response_model=list[ReviewQueueItem])
async def get_review_queue(
    session: AsyncSession = Depends(get_session),
) -> list[ReviewQueueItem]:
    stmt = (
        select(Document)
        .where(Document.status == "review")
        .options(selectinload(Document.extraction))
        .order_by(Document.created_at.desc())
    )
    result = await session.execute(stmt)
    docs = result.scalars().all()

    items: list[ReviewQueueItem] = []
    for doc in docs:
        extraction_out = None
        if doc.extraction:
            extraction_out = ExtractionOut(
                vendor_name=doc.extraction.vendor_name,
                tax_id=doc.extraction.tax_id,
                invoice_number=doc.extraction.invoice_number,
                total_amount=doc.extraction.total_amount,
                invoice_date=doc.extraction.invoice_date,
                due_date=doc.extraction.due_date,
                line_items=doc.extraction.line_items or [],
                ocr_confidence=float(doc.extraction.ocr_confidence) if doc.extraction.ocr_confidence else None,
                extraction_confidence=float(doc.extraction.extraction_confidence)
                if doc.extraction.extraction_confidence
                else None,
            )

        items.append(
            ReviewQueueItem(
                id=doc.id,
                filename=doc.filename,
                status=doc.status,
                created_at=doc.created_at,
                extraction=extraction_out,
            )
        )

    return items
