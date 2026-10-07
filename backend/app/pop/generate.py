"""Generate deterministic, clearly fictional proofs in three bank-style layouts."""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

LAYOUTS = [
    (
        "Bank A",
        "Transfer confirmation",
        ["Amount", "Payment date", "Reference", "Payer", "Beneficiary account"],
    ),
    (
        "Bank B",
        "Payment advice",
        ["Paid amount", "Value date", "Your reference", "Remitter", "To account"],
    ),
    (
        "Bank A",
        "EFT receipt",
        [
            "Transfer total",
            "Processed on",
            "Payment reference",
            "Account holder",
            "Beneficiary suffix",
        ],
    ),
]


def money(cents: int) -> str:
    """Format cents without converting money to binary floating point."""
    whole, fraction = divmod(abs(cents), 100)
    return f"{'-' if cents < 0 else ''}R {whole:,}.{fraction:02d}"


def generate_pdf(path: Path, fields: dict[str, Any], layout: int = 0) -> None:
    """Render one synthetic claim; invariant mode makes identical inputs byte-identical."""
    bank, title, labels = LAYOUTS[layout % 3]
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas = Canvas(str(path), pagesize=A4, invariant=1)
    canvas.setTitle(f"SYNTHETIC - {title}")
    width, height = A4
    accent = ["#173C39", "#28374D", "#7A482F"][layout % 3]
    canvas.setFillColor(HexColor(accent))
    canvas.rect(0, height - 172, width, 172, fill=1, stroke=0)
    canvas.setFillColor(HexColor("#FFFFFF"))
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawString(48, height - 52, bank.upper())
    canvas.setFont("Helvetica-Bold", 27)
    canvas.drawString(48, height - 100, title)
    canvas.setFont("Helvetica", 10)
    canvas.drawString(
        48, height - 131, "Synthetic demonstration / No funds transferred by this document"
    )
    canvas.setFillColor(HexColor("#173C39"))
    canvas.setFont("Helvetica-Bold", 29)
    canvas.drawString(48, height - 232, money(int(fields["amount_cents"])))
    values = [
        money(int(fields["amount_cents"])),
        str(fields["payment_date"]),
        fields["reference"],
        fields["payer_name"],
        f"****{fields.get('beneficiary_last4', '0042')}",
    ]
    for n, (label, value) in enumerate(zip(labels, values, strict=True)):
        y = height - 296 - n * 61
        canvas.setStrokeColor(HexColor("#E1E7E4"))
        canvas.line(48, y - 20, width - 48, y - 20)
        canvas.setFillColor(HexColor("#394942"))
        canvas.setFont("Helvetica", 11)
        canvas.drawString(48, y, f"{label}: {value}")
    canvas.setFillColor(HexColor("#7D857F"))
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(48, 135, "A PAYMENT CLAIM, NOT BANK-FEED EVIDENCE")
    canvas.setFont("Helvetica", 9)
    canvas.drawString(
        48, 114, "Verify receipt independently before approving an allocation or releasing goods."
    )
    canvas.drawString(48, 63, "CLEARLINE SYNTHETIC FIXTURE")
    canvas.drawRightString(width - 48, 63, "1 / 1")
    canvas.save()


def generate_pop_set(directory: Path, dataset: dict[str, Any]) -> list[dict[str, Any]]:
    """Create the PRD's 60-file PoP mix without exposing verdict labels to the extractor."""
    directory.mkdir(parents=True, exist_ok=True)
    exact = [
        line
        for line, label in zip(dataset["bank_lines"], dataset["labels"], strict=True)
        if label["scenario"] == "exact"
    ]
    labels: list[dict[str, Any]] = []
    for n in range(60):
        line = exact[40 + n]
        fields = {
            "amount_cents": line["amount_cents"],
            "payment_date": line["value_date"],
            "reference": line["raw_reference"],
            "payer_name": line["payer_name"],
            "beneficiary_last4": "0042",
        }
        verdict, scenario = "verified", "genuine"
        claimed: str | None = line["raw_reference"]
        if 30 <= n < 45:
            fields["payer_name"] = f"Absent Synthetic Payer P{n}"
            fields["reference"] = f"INV-{880000 + n:06d}"
            claimed = None
            verdict, scenario = "not_received", "not_received"
        elif 45 <= n < 54:
            fields["amount_cents"] += 10000
            verdict, scenario = "mismatch", "amount_mismatch"
        elif n >= 54:
            if n % 2:
                fields["payment_date"] = str(
                    date.fromisoformat(line["value_date"]) + timedelta(days=8)
                )
                scenario = "date_mismatch"
            else:
                fields["reference"] = f"INV-{880000 + n:06d}"
                scenario = "reference_mismatch"
            verdict = "mismatch"
        filename = f"proof-{n + 1:03d}.pdf"
        generate_pdf(directory / filename, fields, n % 3)
        labels.append(
            {
                "filename": filename,
                "scenario": scenario,
                "verdict": verdict,
                "claimed_invoice_number": claimed,
                "layout": n % 3,
            }
        )
    (directory / "labels.json").write_text(json.dumps(labels, indent=2) + "\n")
    return labels
