"""Confidence scoring module.

Combines OCR, extraction, and validation signals into:
- An overall confidence score (0.0 – 1.0)
- Per-field confidence scores (from LLM or pattern-based extractor)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.extraction.extractor import ExtractedData
from app.validation.rule_engine import ValidationResult


@dataclass(frozen=True)
class ConfidenceResult:
    overall: float                              # 0.0 – 1.0
    ocr_score: float
    extraction_score: float
    validation_score: float
    per_field: dict[str, float] = field(default_factory=dict)   # field → 0.0–1.0


def compute_confidence(
    ocr_confidence: float,
    extraction_confidence: float,
    validation_results: list[ValidationResult],
    extracted: ExtractedData | None = None,
) -> ConfidenceResult:
    """Compute overall and per-field confidence scores.

    Weights:
        OCR        30%
        Extraction 40%
        Validation 30%
    """
    ocr_weight = 0.30
    extraction_weight = 0.40
    validation_weight = 0.30

    validation_score = (
        sum(r.score for r in validation_results) / len(validation_results)
        if validation_results else 1.0
    )

    overall = max(0.0, min(1.0,
        ocr_weight * ocr_confidence
        + extraction_weight * extraction_confidence
        + validation_weight * validation_score
    ))

    # Per-field scores: prefer LLM-provided ones, fall back to simple heuristic
    per_field: dict[str, float] = {}
    if extracted is not None:
        if extracted.field_confidences:
            per_field = {k: round(float(v), 4) for k, v in extracted.field_confidences.items()}
        else:
            # Simple heuristic: 0.8 if field has a value, 0.0 otherwise
            for fname in ("vendor_name", "tax_id", "invoice_number", "total_amount", "invoice_date", "due_date"):
                per_field[fname] = 0.8 if getattr(extracted, fname, None) is not None else 0.0

    return ConfidenceResult(
        overall=round(overall, 4),
        ocr_score=round(ocr_confidence, 4),
        extraction_score=round(extraction_confidence, 4),
        validation_score=round(validation_score, 4),
        per_field=per_field,
    )

