"""OCR engine tests — fully mocked, no real PDF/image required."""
from __future__ import annotations

import pytest

from app.ocr.base_ocr import OCREngine, OCRResult
from app.ocr.mock_ocr import MockOCREngine


# ---------------------------------------------------------------------------
# Base OCREngine
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_base_ocr_raises_not_implemented() -> None:
    engine = OCREngine()
    with pytest.raises(NotImplementedError):
        await engine.extract_text(b"fake bytes")


# ---------------------------------------------------------------------------
# MockOCREngine
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_ocr_returns_result() -> None:
    engine = MockOCREngine()
    result = await engine.extract_text(b"any bytes")
    assert isinstance(result, OCRResult)
    assert isinstance(result.text, str)
    assert len(result.text) > 0
    assert 0.0 <= result.confidence <= 1.0


@pytest.mark.asyncio
async def test_mock_ocr_contains_expected_fields() -> None:
    engine = MockOCREngine()
    result = await engine.extract_text(b"")
    # The mock should return something resembling an invoice
    assert "Vendor" in result.text or "INVOICE" in result.text


@pytest.mark.asyncio
async def test_mock_ocr_returns_high_confidence() -> None:
    engine = MockOCREngine()
    result = await engine.extract_text(b"test")
    # Mock OCR is intended to simulate a good scan
    assert result.confidence >= 0.5


# ---------------------------------------------------------------------------
# OCR Factory
# ---------------------------------------------------------------------------

def test_ocr_factory_returns_mock() -> None:
    import os
    os.environ["OCR_PROVIDER"] = "mock"

    # Reload settings with the new env var
    from importlib import reload
    import app.core.config as cfg_module
    reload(cfg_module)

    from app.ocr.factory import get_ocr_engine
    engine = get_ocr_engine()
    assert isinstance(engine, MockOCREngine)


def test_ocr_factory_raises_on_unknown_provider() -> None:
    import os
    os.environ["OCR_PROVIDER"] = "unknown_engine"

    from importlib import reload
    import app.core.config as cfg_module
    import app.ocr.factory as factory_module
    reload(cfg_module)
    reload(factory_module)

    from app.ocr.factory import get_ocr_engine
    with pytest.raises(ValueError, match="Unknown OCR_PROVIDER"):
        get_ocr_engine()

    # Restore
    os.environ["OCR_PROVIDER"] = "mock"
    reload(cfg_module)
    reload(factory_module)
