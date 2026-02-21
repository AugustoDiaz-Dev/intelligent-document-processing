from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    status: str


class ValidationOut(BaseModel):
    rule_name: str
    passed: bool
    score: float
    message: str | None


class ExtractionOut(BaseModel):
    vendor_name: str | None
    tax_id: str | None
    invoice_number: str | None
    total_amount: Decimal | None
    invoice_date: datetime | None
    due_date: datetime | None
    line_items: list[dict]
    ocr_confidence: float | None
    extraction_confidence: float | None
    # Per-field confidence scores (#F)
    field_confidences: dict[str, float] | None = None
    overall_confidence: float | None = None


class ProcessingEventOut(BaseModel):
    """Single audit trail entry."""
    step: str
    status: str
    detail: str | None
    duration_ms: int | None
    created_at: datetime


class DocumentDetailResponse(BaseModel):
    id: uuid.UUID
    filename: str
    status: str
    created_at: datetime
    updated_at: datetime
    extraction: ExtractionOut | None
    validations: list[ValidationOut]
    events: list[ProcessingEventOut] = Field(default_factory=list)


class ReviewQueueItem(BaseModel):
    id: uuid.UUID
    filename: str
    status: str
    created_at: datetime
    extraction: ExtractionOut | None

