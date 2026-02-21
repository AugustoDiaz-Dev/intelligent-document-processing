from __future__ import annotations

from app.core.config import settings
from app.ocr.base_ocr import OCREngine
from app.ocr.mock_ocr import MockOCREngine


def get_ocr_engine() -> OCREngine:
    """Return the configured OCR engine instance.

    OCR_PROVIDER options:
        mock         — synthetic text (dev/test, no deps required)
        paddleocr    — LocalOCREngine (pip install paddlepaddle paddleocr)
        aws_textract — CloudOCREngine (pip install boto3 + AWS credentials)
    """
    provider = settings.ocr_provider.lower().strip()

    if provider == "mock":
        return MockOCREngine()

    if provider == "paddleocr":
        from app.ocr.engines import LocalOCREngine
        return LocalOCREngine(
            lang=getattr(settings, "paddle_lang", "en"),
            use_gpu=getattr(settings, "paddle_use_gpu", False),
        )

    if provider == "aws_textract":
        from app.ocr.engines import CloudOCREngine
        return CloudOCREngine(
            region=getattr(settings, "aws_region", "us-east-1"),
            aws_access_key_id=getattr(settings, "aws_access_key_id", None),
            aws_secret_access_key=getattr(settings, "aws_secret_access_key", None),
        )

    raise ValueError(f"Unknown OCR_PROVIDER={settings.ocr_provider!r}")
