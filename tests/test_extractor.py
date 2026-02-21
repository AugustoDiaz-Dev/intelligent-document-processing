"""Extractor tests — pattern-based extraction (no LLM, no external deps)."""
from __future__ import annotations

import pytest

from app.extraction.extractor import ExtractedData, Extractor


SAMPLE_INVOICE_TEXT = """INVOICE

Vendor: Acme Corp
Tax ID: 12-3456789
Invoice #: INV-2024-001
Invoice Date: 2024-01-15
Due Date: 2024-02-15

Item 1: $100.00
Item 2: $200.00
Total: $300.00
"""

MINIMAL_TEXT = "Just some random text with no invoice fields."


@pytest.mark.asyncio
async def test_extract_returns_extracted_data() -> None:
    extractor = Extractor()
    result = await extractor.extract(SAMPLE_INVOICE_TEXT)
    assert isinstance(result, ExtractedData)


@pytest.mark.asyncio
async def test_extract_vendor_name() -> None:
    extractor = Extractor()
    result = await extractor.extract(SAMPLE_INVOICE_TEXT)
    assert result.vendor_name == "Acme Corp"


@pytest.mark.asyncio
async def test_extract_tax_id() -> None:
    extractor = Extractor()
    result = await extractor.extract(SAMPLE_INVOICE_TEXT)
    assert result.tax_id == "12-3456789"


@pytest.mark.asyncio
async def test_extract_invoice_number() -> None:
    extractor = Extractor()
    result = await extractor.extract(SAMPLE_INVOICE_TEXT)
    assert result.invoice_number == "INV-2024-001"


@pytest.mark.asyncio
async def test_extract_total_amount() -> None:
    from decimal import Decimal
    extractor = Extractor()
    result = await extractor.extract(SAMPLE_INVOICE_TEXT)
    assert result.total_amount == Decimal("300.00")


@pytest.mark.asyncio
async def test_extract_confidence_high_when_fields_found() -> None:
    extractor = Extractor()
    result = await extractor.extract(SAMPLE_INVOICE_TEXT)
    assert result.extraction_confidence >= 0.5


@pytest.mark.asyncio
async def test_extract_confidence_low_when_no_fields() -> None:
    extractor = Extractor()
    result = await extractor.extract(MINIMAL_TEXT)
    assert result.extraction_confidence < 0.7


@pytest.mark.asyncio
async def test_extract_field_confidences_present() -> None:
    extractor = Extractor()
    result = await extractor.extract(SAMPLE_INVOICE_TEXT)
    # Pattern-based extractor should always return field_confidences
    assert result.field_confidences is not None
    assert "vendor_name" in result.field_confidences
    assert "total_amount" in result.field_confidences


@pytest.mark.asyncio
async def test_extract_empty_text_returns_defaults() -> None:
    extractor = Extractor()
    result = await extractor.extract("")
    assert result.vendor_name is None
    assert result.invoice_number is None
    assert result.total_amount is None
