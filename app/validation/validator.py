from __future__ import annotations

from app.extraction.extractor import ExtractedData
from app.validation.rule_engine import RuleEngine, ValidationResult


class Validator:
    def __init__(self) -> None:
        self._rule_engine = RuleEngine()

    def validate(
        self,
        extracted: ExtractedData,
        *,
        existing_invoice_numbers: set[str] | None = None,
    ) -> list[ValidationResult]:
        return self._rule_engine.validate(
            extracted,
            existing_invoice_numbers=existing_invoice_numbers,
        )

