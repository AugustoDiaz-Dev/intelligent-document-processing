from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(128), default="application/pdf")
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending | processing | completed | failed | review
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    extraction: Mapped[Extraction | None] = relationship(back_populates="document", uselist=False)
    validations: Mapped[list[Validation]] = relationship(back_populates="document", cascade="all, delete-orphan")
    events: Mapped[list[ProcessingEvent]] = relationship(back_populates="document", cascade="all, delete-orphan", order_by="ProcessingEvent.created_at")


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), unique=True, index=True
    )

    vendor_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    invoice_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    line_items: Mapped[dict] = mapped_column(JSON, default=dict)  # list of {description, quantity, unit_price, total}
    # Per-field confidence scores (#F)
    field_confidences: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    extraction_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="extraction")


class Validation(Base):
    __tablename__ = "validations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )

    rule_name: Mapped[str] = mapped_column(String(128))
    passed: Mapped[bool] = mapped_column()
    score: Mapped[float] = mapped_column(Numeric(5, 4))
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="validations")


# ── Audit trail ──────────────────────────────────────────────────────────────────────
class ProcessingEvent(Base):
    """Audit trail: one row per pipeline step per document.

    step values: ocr | extraction | validation | confidence | completed | failed
    """
    __tablename__ = "processing_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    step: Mapped[str] = mapped_column(String(64))          # e.g. "ocr", "extraction"
    status: Mapped[str] = mapped_column(String(32))        # "started" | "completed" | "failed"
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)   # human-readable note
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)    # wall-clock ms for this step
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="events")
