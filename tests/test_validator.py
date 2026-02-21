"""#17 — Validation rule engine tests (expanded)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app.extraction.extractor import ExtractedData
from app.validation.rule_engine import RuleEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_extracted(**kwargs) -> ExtractedData:
    defaults = dict(
        vendor_name=None,
        tax_id=None,
        invoice_number=None,
        total_amount=None,
        invoice_date=None,
        due_date=None,
        line_items=None,
        extraction_confidence=0.8,
    )
    defaults.update(kwargs)
    return ExtractedData(**defaults)


# ---------------------------------------------------------------------------
# line_items_sum
# ---------------------------------------------------------------------------

def test_validate_line_items_sum_pass() -> None:
    engine = RuleEngine()
    extracted = _make_extracted(
        total_amount=Decimal("300.00"),
        line_items=[
            {"description": "Item 1", "total": "100.00"},
            {"description": "Item 2", "total": "200.00"},
        ],
    )
    results = engine.validate(extracted)
    r = next(r for r in results if r.rule_name == "line_items_sum")
    assert r.passed is True
    assert r.score == 1.0


def test_validate_line_items_sum_fail() -> None:
    engine = RuleEngine()
    extracted = _make_extracted(
        total_amount=Decimal("500.00"),
        line_items=[
            {"description": "Item 1", "total": "100.00"},
            {"description": "Item 2", "total": "200.00"},
        ],
    )
    results = engine.validate(extracted)
    r = next(r for r in results if r.rule_name == "line_items_sum")
    assert r.passed is False
    assert r.score == 0.0


def test_validate_line_items_sum_skipped_when_no_items() -> None:
    engine = RuleEngine()
    extracted = _make_extracted()
    results = engine.validate(extracted)
    r = next(r for r in results if r.rule_name == "line_items_sum")
    assert r.passed is True   # skipped = pass


# ---------------------------------------------------------------------------
# tax_id_format
# ---------------------------------------------------------------------------

def test_validate_tax_id_valid() -> None:
    engine = RuleEngine()
    extracted = _make_extracted(tax_id="12-3456789")
    results = engine.validate(extracted)
    r = next(r for r in results if r.rule_name == "tax_id_format")
    assert r.passed is True


def test_validate_tax_id_too_short() -> None:
    engine = RuleEngine()
    extracted = _make_extracted(tax_id="123")
    results = engine.validate(extracted)
    r = next(r for r in results if r.rule_name == "tax_id_format")
    assert r.passed is False


def test_validate_tax_id_skipped_when_none() -> None:
    engine = RuleEngine()
    extracted = _make_extracted()
    results = engine.validate(extracted)
    r = next(r for r in results if r.rule_name == "tax_id_format")
    assert r.passed is True


# ---------------------------------------------------------------------------
# date_consistency
# ---------------------------------------------------------------------------

def test_validate_dates_consistent() -> None:
    engine = RuleEngine()
    extracted = _make_extracted(
        invoice_date=datetime(2024, 1, 1),
        due_date=datetime(2024, 2, 1),
    )
    results = engine.validate(extracted)
    r = next(r for r in results if r.rule_name == "date_consistency")
    assert r.passed is True


def test_validate_dates_due_before_invoice() -> None:
    engine = RuleEngine()
    extracted = _make_extracted(
        invoice_date=datetime(2024, 3, 1),
        due_date=datetime(2024, 1, 1),
    )
    results = engine.validate(extracted)
    r = next(r for r in results if r.rule_name == "date_consistency")
    assert r.passed is False


# ---------------------------------------------------------------------------
# duplicate_invoice
# ---------------------------------------------------------------------------

def test_validate_no_duplicate_unique() -> None:
    engine = RuleEngine()
    extracted = _make_extracted(invoice_number="INV-001")
    results = engine.validate(extracted, existing_invoice_numbers={"INV-002", "INV-003"})
    r = next(r for r in results if r.rule_name == "duplicate_invoice")
    assert r.passed is True


def test_validate_duplicate_detected() -> None:
    engine = RuleEngine()
    extracted = _make_extracted(invoice_number="INV-001")
    results = engine.validate(extracted, existing_invoice_numbers={"INV-001", "INV-002"})
    r = next(r for r in results if r.rule_name == "duplicate_invoice")
    assert r.passed is False
    assert "Duplicate" in (r.message or "")


def test_validate_duplicate_skipped_when_no_invoice_number() -> None:
    engine = RuleEngine()
    extracted = _make_extracted()
    results = engine.validate(extracted, existing_invoice_numbers={"INV-001"})
    r = next(r for r in results if r.rule_name == "duplicate_invoice")
    assert r.passed is True   # skipped = pass


def test_validate_duplicate_not_run_when_set_is_none() -> None:
    engine = RuleEngine()
    extracted = _make_extracted(invoice_number="INV-999")
    results = engine.validate(extracted, existing_invoice_numbers=None)
    names = [r.rule_name for r in results]
    assert "duplicate_invoice" not in names
