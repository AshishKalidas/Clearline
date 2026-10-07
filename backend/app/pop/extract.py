"""Extract supported text-based synthetic PDF layouts; never infer missing fields."""

import io
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

import pdfplumber

LABELS = {
    "amount": r"Amount|Paid amount|Transfer total",
    "date": r"Payment date|Value date|Processed on",
    "reference": r"Reference|Your reference|Payment reference",
    "payer": r"Payer|Remitter|Account holder",
    "beneficiary": r"Beneficiary account|To account|Beneficiary suffix",
}


@dataclass(frozen=True)
class PaymentClaim:
    """Required fields extracted from a claim, with no assumption that it is genuine."""

    amount_cents: int
    payment_date: date
    reference: str
    payer_name: str
    beneficiary_last4: str

    def as_dict(self) -> dict[str, Any]:
        """Produce JSON-safe extracted fields."""
        return {
            "amount_cents": self.amount_cents,
            "payment_date": str(self.payment_date),
            "reference": self.reference,
            "payer_name": self.payer_name,
            "beneficiary_last4": self.beneficiary_last4,
        }


def parse_money(value: str) -> int:
    """Parse either supported decimal separator directly to integer cents."""
    match = re.fullmatch(r"(?:ZAR|R)\s*([\d ,]+)[.,](\d{2})", value.strip())
    if not match:
        raise ValueError("unsupported amount")
    whole = re.sub(r"[ ,]", "", match[1])
    return int(whole) * 100 + int(match[2])


def extract_pdf(content: bytes) -> PaymentClaim | None:
    """Read bounded text PDFs and return unreadable for unsupported/ambiguous layouts."""
    if not content.startswith(b"%PDF"):
        return None
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            if not 1 <= len(pdf.pages) <= 5:
                return None
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        fields: dict[str, str] = {}
        for field, labels in LABELS.items():
            matches = re.findall(rf"^(?:{labels})\s*:\s*(.+)$", text, re.M | re.I)
            if len(matches) != 1:
                return None
            fields[field] = matches[0].strip()
        suffix = re.fullmatch(r"\*{4}(\d{4})", fields["beneficiary"])
        if suffix is None:
            return None
        amount = parse_money(fields["amount"])
        if amount <= 0:
            return None
        return PaymentClaim(
            amount,
            date.fromisoformat(fields["date"]),
            fields["reference"],
            fields["payer"],
            suffix[1],
        )
    except Exception:
        # Parse/decryption failures are verdicts; raw PDF data never appears in logs.
        return None
