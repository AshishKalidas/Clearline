"""Shared, write-free CSV validation with bounded, safe field-level feedback."""

import csv
import io
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

ImportKind = Literal["invoices", "bank-lines"]
MAX_ROWS = 10000
MAX_ISSUES = 20


class InvoiceRow(BaseModel):
    """One CSV invoice, including its fictional customer."""

    model_config = ConfigDict(extra="forbid")
    invoice_number: str = Field(pattern=r"^INV-\d{6}$")
    account_code: str = Field(pattern=r"^C-\d{5}$")
    customer_name: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=2000)
    issue_date: date
    due_date: date
    amount_cents: int = Field(gt=0, le=10**12)

    @model_validator(mode="after")
    def valid_dates(self) -> "InvoiceRow":
        if self.due_date < self.issue_date:
            raise ValueError("due date precedes issue date")
        return self


class BankRow(BaseModel):
    """A bank-provided observation. Sequence distinguishes genuine repeated EFTs."""

    model_config = ConfigDict(extra="forbid")
    value_date: date
    amount_cents: int = Field(ge=-(10**12), le=10**12)
    raw_reference: str = Field(max_length=2000)
    payer_name: str = Field(min_length=1, max_length=200)
    payer_account_masked: str = Field(pattern=r"^\d{4}$")
    bank_transaction_id: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def nonzero_amount(self) -> "BankRow":
        if self.amount_cents == 0:
            raise ValueError("zero-value bank lines are not payments")
        return self


class CsvIssue(BaseModel):
    """A record position and safe explanation; never echo the rejected value."""

    row: int
    field: str | None
    message: str


class CsvInputError(ValueError):
    """Expose bounded diagnostics without returning Pydantic's raw input values."""

    def __init__(self, issues: list[CsvIssue], issue_count: int | None = None) -> None:
        super().__init__("The CSV needs a few corrections before it can be imported.")
        self.issues = issues[:MAX_ISSUES]
        self.issue_count = issue_count if issue_count is not None else len(issues)


def invalid_csv(message: str, row: int = 1) -> CsvInputError:
    """Create a file-level diagnostic without including file content."""
    return CsvInputError([CsvIssue(row=row, field=None, message=message)])


def parse_csv(content: bytes) -> list[dict[str, str]]:
    """Read strict UTF-8 CSV, rejecting ambiguous headers and malformed records."""
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")), strict=True)
        headers = reader.fieldnames
        if not headers or any(not header.strip() for header in headers):
            raise invalid_csv("Start with a header row using the downloaded template.")
        if len(headers) != len(set(headers)):
            raise invalid_csv("Each column must have a unique header.")
        rows: list[dict[str, str]] = []
        for position, row in enumerate(reader, start=2):
            if len(rows) == MAX_ROWS:
                raise invalid_csv("Split files larger than 10000 records into smaller imports.")
            if None in row or any(value is None for value in row.values()):
                raise invalid_csv(
                    "This record has a different number of columns than the header.", position
                )
            rows.append(row)
        if not rows:
            raise invalid_csv("Include at least one data record below the header.")
        return rows
    except UnicodeDecodeError as exc:
        raise invalid_csv("Save the file as UTF-8 CSV and try again.") from exc
    except csv.Error as exc:
        raise invalid_csv("Check CSV quoting and delimiters against the template.") from exc


def validate_rows[Row: BaseModel](model: type[Row], content: bytes) -> list[Row]:
    """Validate the complete file before any caller may start inserting records."""
    validated: list[Row] = []
    issues: list[CsvIssue] = []
    issue_count = 0
    for position, row in enumerate(parse_csv(content), start=2):
        try:
            validated.append(model.model_validate(row))
        except ValidationError as exc:
            for error in exc.errors(include_input=False, include_context=False, include_url=False):
                issue_count += 1
                if len(issues) == MAX_ISSUES:
                    continue
                field = str(error["loc"][0]) if error["loc"] else None
                if field not in model.model_fields:
                    field = None
                if error["type"] == "missing":
                    message = "This column is required."
                elif error["type"] == "extra_forbidden":
                    message = "Remove columns that are not in the template."
                elif field == "amount_cents":
                    message = (
                        "Use non-zero whole cents within the supported range; "
                        "invoices must be positive."
                    )
                elif field in {"issue_date", "due_date", "value_date"}:
                    message = "Use a valid date in YYYY-MM-DD format."
                elif error["type"] == "string_pattern_mismatch":
                    message = "Use the identifier format shown in the template."
                elif field is None:
                    message = "Check date order and ensure bank amounts are non-zero."
                else:
                    message = "Enter a value within the template's required limits."
                issues.append(CsvIssue(row=position, field=field, message=message))
    if issues:
        raise CsvInputError(issues, issue_count)
    return validated


class ImportPreview(BaseModel):
    """A schema preview, with no database reads, writes, or model calls."""

    kind: ImportKind
    row_count: int
    columns: list[str]
    rows: list[dict[str, str | int]]


def preview_csv(kind: ImportKind, content: bytes) -> ImportPreview:
    """Return the first five validated records; identity conflicts are checked at import."""
    if kind == "invoices":
        records: list[BaseModel] = list(validate_rows(InvoiceRow, content))
        columns = list(InvoiceRow.model_fields)
    else:
        records = list(validate_rows(BankRow, content))
        columns = list(BankRow.model_fields)
    return ImportPreview(
        kind=kind,
        row_count=len(records),
        columns=columns,
        rows=[record.model_dump(mode="json") for record in records[:5]],
    )
