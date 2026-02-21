from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

import re

from app.extraction.extractor import ExtractedData

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ValidationResult:
    rule_name: str
    passed: bool
    score: float  # 0.0 to 1.0
    message: str | None = None


class RuleEngine:
    def validate(
        self,
        extracted: ExtractedData,
        *,
        existing_invoice_numbers: set[str] | None = None,
    ) -> list[ValidationResult]:
        """Run all validation rules.

        Args:
            extracted: The extracted invoice data.
            existing_invoice_numbers: Set of already-known invoice numbers for
                duplicate detection. Pass None to skip that check.
        """
        results: list[ValidationResult] = []
        results.append(self._validate_line_items_sum(extracted))
        results.append(self._validate_tax_id_format(extracted))
        results.append(self._validate_dates(extracted))
        if existing_invoice_numbers is not None:
            results.append(self._validate_no_duplicate(extracted, existing_invoice_numbers))
        return results

    def _validate_line_items_sum(self, extracted: ExtractedData) -> ValidationResult:
        if not extracted.line_items or not extracted.total_amount:
            return ValidationResult(
                rule_name="line_items_sum",
                passed=True,
                score=1.0,
                message="Skipped: no line items or total",
            )

        calculated_total = sum(
            Decimal(str(item.get("total", 0))) for item in extracted.line_items if isinstance(item, dict)
        )
        diff = abs(calculated_total - extracted.total_amount)
        tolerance = Decimal("0.01")

        if diff <= tolerance:
            return ValidationResult(
                rule_name="line_items_sum",
                passed=True,
                score=1.0,
                message=f"Line items sum matches total: {calculated_total}",
            )
        else:
            return ValidationResult(
                rule_name="line_items_sum",
                passed=False,
                score=0.0,
                message=f"Line items sum ({calculated_total}) does not match total ({extracted.total_amount})",
            )

    def _validate_tax_id_format(self, extracted: ExtractedData) -> ValidationResult:
        if not extracted.tax_id:
            return ValidationResult(
                rule_name="tax_id_format",
                passed=True,
                score=1.0,
                message="Skipped: no tax ID",
            )

        tax_id = extracted.tax_id.replace("-", "").replace(" ", "")
        # Simple validation: alphanumeric, reasonable length
        if tax_id.isalnum() and 5 <= len(tax_id) <= 20:
            return ValidationResult(
                rule_name="tax_id_format",
                passed=True,
                score=1.0,
                message="Tax ID format is valid",
            )
        else:
            return ValidationResult(
                rule_name="tax_id_format",
                passed=False,
                score=0.5,
                message=f"Tax ID format may be invalid: {extracted.tax_id}",
            )

    def _validate_dates(self, extracted: ExtractedData) -> ValidationResult:
        if not extracted.invoice_date:
            return ValidationResult(
                rule_name="date_consistency",
                passed=True,
                score=1.0,
                message="Skipped: no invoice date",
            )

        if extracted.due_date and extracted.invoice_date:
            if extracted.due_date < extracted.invoice_date:
                return ValidationResult(
                    rule_name="date_consistency",
                    passed=False,
                    score=0.0,
                    message="Due date is before invoice date",
                )

        return ValidationResult(
            rule_name="date_consistency",
            passed=True,
            score=1.0,
            message="Dates are consistent",
        )

    def _validate_no_duplicate(
        self,
        extracted: ExtractedData,
        existing_invoice_numbers: set[str],
    ) -> ValidationResult:
        """Check that the invoice number has not been processed before (#C)."""
        inv_num = extracted.invoice_number
        if not inv_num:
            return ValidationResult(
                rule_name="duplicate_invoice",
                passed=True,
                score=1.0,
                message="Skipped: no invoice number extracted",
            )

        if inv_num in existing_invoice_numbers:
            return ValidationResult(
                rule_name="duplicate_invoice",
                passed=False,
                score=0.0,
                message=f"Duplicate invoice number detected: {inv_num}",
            )

        return ValidationResult(
            rule_name="duplicate_invoice",
            passed=True,
            score=1.0,
            message=f"Invoice number {inv_num!r} is unique",
        )
