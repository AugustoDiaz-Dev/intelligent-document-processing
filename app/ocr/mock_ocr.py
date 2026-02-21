from __future__ import annotations

from app.ocr.base_ocr import OCRResult, OCREngine


class MockOCREngine(OCREngine):
    async def extract_text(self, image_bytes: bytes) -> OCRResult:
        # Mock OCR for development/testing
        return OCRResult(
            text="INVOICE\nVendor: Acme Corp\nTax ID: 12-3456789\nInvoice #: INV-2024-001\nDate: 2024-01-15\n\nLine Items:\nItem 1: $100.00\nItem 2: $200.00\nTotal: $300.00",
            confidence=0.85,
        )
