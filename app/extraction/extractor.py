"""LLM-based structured extraction for invoice documents.

Uses an OpenAI LLM (or any BaseLLM-compatible provider) to extract all
required invoice fields from raw OCR text in a single structured call.

The extractor falls back to the pattern-based implementation when no
LLM provider is configured (OCR_EXTRACTION_MODE=simple in .env).

Config:
    EXTRACTION_MODE=llm        # llm | simple (default: simple)
    OPENAI_API_KEY=...         # required when EXTRACTION_MODE=llm
    LLM_MODEL=gpt-4o-mini
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model (shared with rest of app)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExtractedData:
    vendor_name: str | None = None
    tax_id: str | None = None
    invoice_number: str | None = None
    total_amount: Decimal | None = None
    invoice_date: datetime | None = None
    due_date: datetime | None = None
    line_items: list[dict] | None = None
    extraction_confidence: float = 0.0
    # Per-field confidence scores (F — per-field confidence)
    field_confidences: dict[str, float] | None = None


# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

_EXTRACTION_SYSTEM_PROMPT = """\
You are a precise invoice data extraction assistant.
Given raw OCR text from an invoice, extract ALL of the following fields as a
JSON object. Use null for fields that cannot be found.

Fields to extract:
- vendor_name: string — the company or individual issuing the invoice
- tax_id: string — EIN, VAT ID, or equivalent (e.g. "12-3456789")
- invoice_number: string — the invoice reference/number
- invoice_date: string — ISO 8601 date (YYYY-MM-DD) or null
- due_date: string — ISO 8601 date (YYYY-MM-DD) or null
- total_amount: number — the final total amount as a decimal number
- line_items: array of objects, each with:
    - description: string
    - quantity: number or null
    - unit_price: number or null
    - total: number

Also include a "confidence" object with a 0.0–1.0 score for each field
indicating how confident you are in the extracted value.

Respond ONLY with valid JSON. No explanation, no markdown fences.
"""


# ---------------------------------------------------------------------------
# LLM helper (thin OpenAI wrapper, no external base class dependency)
# ---------------------------------------------------------------------------

class _OpenAIExtractor:
    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self._model = model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _call(self, ocr_text: str) -> str:
        try:
            from openai import AsyncOpenAI  # type: ignore[import]
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "openai package is not installed. Run: pip install openai"
            ) from exc

        client = AsyncOpenAI()
        response = await client.chat.completions.create(
            model=self._model,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": f"Invoice OCR text:\n\n{ocr_text}"},
            ],
        )
        return response.choices[0].message.content or "{}"


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _parse_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


# ---------------------------------------------------------------------------
# Main Extractor class
# ---------------------------------------------------------------------------

class Extractor:
    """Extraction facade — delegates to LLM or pattern-based depending on config."""

    def __init__(self) -> None:
        pass

    async def extract(self, ocr_text: str) -> ExtractedData:
        from app.core.config import settings
        mode = getattr(settings, "extraction_mode", "simple")

        if mode == "llm":
            try:
                return await self._llm_extract(ocr_text)
            except Exception as exc:
                logger.warning(
                    "llm_extraction_failed_fallback",
                    extra={"error": str(exc)},
                )
                # Fall back to simple extraction on LLM failure
                return self._simple_extract(ocr_text)

        return self._simple_extract(ocr_text)

    # ------------------------------------------------------------------ #
    #  LLM extraction path                                                #
    # ------------------------------------------------------------------ #

    async def _llm_extract(self, ocr_text: str) -> ExtractedData:
        from app.core.config import settings
        extractor = _OpenAIExtractor(model=getattr(settings, "llm_model", "gpt-4o-mini"))
        raw_json = await extractor._call(ocr_text)

        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            logger.error("llm_extraction_json_parse_error", extra={"raw": raw_json[:200]})
            raise

        confidence_map: dict[str, float] = data.get("confidence", {})
        avg_confidence = (
            sum(confidence_map.values()) / len(confidence_map)
            if confidence_map else 0.7
        )

        line_items: list[dict] = []
        for item in data.get("line_items") or []:
            line_items.append({
                "description": item.get("description", ""),
                "quantity": item.get("quantity"),
                "unit_price": item.get("unit_price"),
                "total": item.get("total", 0),
            })

        logger.info(
            "llm_extraction_complete",
            extra={"fields_extracted": len([v for v in data.values() if v is not None])},
        )

        return ExtractedData(
            vendor_name=data.get("vendor_name"),
            tax_id=data.get("tax_id"),
            invoice_number=data.get("invoice_number"),
            total_amount=_parse_decimal(data.get("total_amount")),
            invoice_date=_parse_date(data.get("invoice_date")),
            due_date=_parse_date(data.get("due_date")),
            line_items=line_items,
            extraction_confidence=round(avg_confidence, 4),
            field_confidences=confidence_map,
        )

    # ------------------------------------------------------------------ #
    #  Pattern-based extraction (no LLM needed)                           #
    # ------------------------------------------------------------------ #

    def _simple_extract(self, text: str) -> ExtractedData:
        lines = text.split("\n")
        vendor_name = None
        tax_id = None
        invoice_number = None
        total_amount = None
        invoice_date = None
        due_date = None
        line_items: list[dict] = []

        for line in lines:
            line_lower = line.lower()

            if "vendor" in line_lower or "company" in line_lower or "from:" in line_lower:
                vendor_name = line.split(":", 1)[-1].strip() if ":" in line else vendor_name

            if "tax id" in line_lower or "ein" in line_lower or "vat" in line_lower:
                tax_id = line.split(":", 1)[-1].strip() if ":" in line else tax_id

            if "invoice #" in line_lower or "invoice number" in line_lower or "inv #" in line_lower:
                invoice_number = line.split(":", 1)[-1].strip() if ":" in line else invoice_number

            if ("invoice date" in line_lower or "date:" in line_lower) and invoice_date is None:
                raw = line.split(":", 1)[-1].strip() if ":" in line else ""
                invoice_date = _parse_date(raw)

            if "due date" in line_lower or "payment due" in line_lower:
                raw = line.split(":", 1)[-1].strip() if ":" in line else ""
                due_date = _parse_date(raw)

            if "total" in line_lower and "$" in line:
                amount_str = re.sub(r"[^\d.]", "", line.split("$")[-1])
                if amount_str:
                    total_amount = _parse_decimal(amount_str)

            # Simple line-item detection: lines with $ price
            item_match = re.match(r"^(.+?)[\s:]+\$?([\d,]+\.?\d*)\s*$", line.strip())
            if item_match and "total" not in line_lower:
                desc = item_match.group(1).strip()
                try:
                    amt = Decimal(item_match.group(2).replace(",", ""))
                    line_items.append({"description": desc, "total": str(amt)})
                except InvalidOperation:
                    pass

        found_fields = [vendor_name, tax_id, invoice_number, total_amount]
        confidence = 0.7 if any(f is not None for f in found_fields) else 0.3
        field_confidences = {
            "vendor_name": 0.8 if vendor_name else 0.0,
            "tax_id": 0.8 if tax_id else 0.0,
            "invoice_number": 0.8 if invoice_number else 0.0,
            "total_amount": 0.8 if total_amount else 0.0,
            "invoice_date": 0.8 if invoice_date else 0.0,
            "due_date": 0.8 if due_date else 0.0,
        }

        return ExtractedData(
            vendor_name=vendor_name,
            tax_id=tax_id,
            invoice_number=invoice_number,
            total_amount=total_amount,
            invoice_date=invoice_date,
            due_date=due_date,
            line_items=line_items,
            extraction_confidence=confidence,
            field_confidences=field_confidences,
        )
