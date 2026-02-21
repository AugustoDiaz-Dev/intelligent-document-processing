from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OCRResult:
    text: str
    confidence: float  # 0.0 to 1.0


class OCREngine:
    async def extract_text(self, image_bytes: bytes) -> OCRResult:
        raise NotImplementedError

