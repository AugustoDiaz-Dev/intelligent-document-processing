"""LocalOCREngine using PaddleOCR and CloudOCREngine placeholder for AWS Textract."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.ocr.base_ocr import OCREngine, OCRResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LocalOCREngine — PaddleOCR
# ---------------------------------------------------------------------------

class LocalOCREngine(OCREngine):
    """OCR engine backed by PaddleOCR (runs 100% locally, no cloud calls).

    Install dependency:
        pip install paddlepaddle paddleocr

    Config (via .env):
        OCR_PROVIDER=paddleocr
        PADDLE_LANG=en      # language code: en | ch | fr | es | etc.
        PADDLE_USE_GPU=false
    """

    def __init__(self, lang: str = "en", use_gpu: bool = False) -> None:
        self._lang = lang
        self._use_gpu = use_gpu
        self._ocr = None   # lazy-init to avoid import cost at startup

    def _get_ocr(self):
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR  # type: ignore[import]
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "PaddleOCR is not installed. Run: pip install paddlepaddle paddleocr"
                ) from exc
            self._ocr = PaddleOCR(
                use_angle_cls=True,
                lang=self._lang,
                use_gpu=self._use_gpu,
                show_log=False,
            )
        return self._ocr

    async def extract_text(self, image_bytes: bytes) -> OCRResult:
        """Run PaddleOCR on *image_bytes* (PNG/JPEG) and return extracted text + confidence."""
        import io

        import numpy as np  # type: ignore[import]
        from PIL import Image  # type: ignore[import]

        # Decode image bytes → numpy array
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_array = np.array(img)

        ocr = self._get_ocr()
        result = ocr.ocr(img_array, cls=True)

        lines: list[str] = []
        confidences: list[float] = []

        if result and result[0]:
            for line in result[0]:
                # Each line: [bounding_box, [text, confidence]]
                text, conf = line[1]
                lines.append(text)
                confidences.append(float(conf))

        full_text = "\n".join(lines)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        logger.info(
            "paddleocr_complete",
            extra={"lines": len(lines), "avg_confidence": round(avg_confidence, 4)},
        )

        return OCRResult(text=full_text, confidence=avg_confidence)


# ---------------------------------------------------------------------------
# CloudOCREngine — AWS Textract placeholder
# ---------------------------------------------------------------------------

class CloudOCREngine(OCREngine):
    """OCR engine backed by AWS Textract.

    This is a **placeholder** implementation — the API shape is fully defined
    so it can be wired up when AWS credentials are available.

    Config (via .env):
        OCR_PROVIDER=aws_textract
        AWS_REGION=us-east-1
        AWS_ACCESS_KEY_ID=...      (or use IAM role)
        AWS_SECRET_ACCESS_KEY=...

    Install dependency:
        pip install boto3
    """

    def __init__(
        self,
        region: str = "us-east-1",
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
    ) -> None:
        self._region = region
        self._access_key = aws_access_key_id
        self._secret_key = aws_secret_access_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import boto3  # type: ignore[import]
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "boto3 is not installed. Run: pip install boto3"
                ) from exc
            kwargs: dict = {"region_name": self._region}
            if self._access_key:
                kwargs["aws_access_key_id"] = self._access_key
                kwargs["aws_secret_access_key"] = self._secret_key
            self._client = boto3.client("textract", **kwargs)
        return self._client

    async def extract_text(self, image_bytes: bytes) -> OCRResult:
        """Call AWS Textract DetectDocumentText and return extracted text + confidence."""
        import asyncio

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._call_textract, image_bytes)
        return result

    def _call_textract(self, image_bytes: bytes) -> OCRResult:
        client = self._get_client()
        response = client.detect_document_text(Document={"Bytes": image_bytes})

        lines: list[str] = []
        confidences: list[float] = []

        for block in response.get("Blocks", []):
            if block["BlockType"] == "LINE":
                lines.append(block.get("Text", ""))
                confidences.append(float(block.get("Confidence", 0)) / 100.0)

        full_text = "\n".join(lines)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        logger.info(
            "textract_complete",
            extra={"lines": len(lines), "avg_confidence": round(avg_confidence, 4)},
        )

        return OCRResult(text=full_text, confidence=avg_confidence)
