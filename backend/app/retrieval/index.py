"""Transactional indexing and cosine retrieval with a measurable ablation switch."""

import math
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db.models import BankLine, Customer, ResolvedCase, RunbookChunk
from backend.app.retrieval.embedder import get_embedder


def index_case(case: ResolvedCase) -> None:
    """Attach the embedding before the resolving transaction is committed."""
    case.embedding = get_embedder().encode(case.summary_text)


def index_customer(customer: Customer) -> None:
    """Embed local payment-behavior notes."""
    customer.notes_embedding = get_embedder().encode(customer.notes)


def cosine(left: list[float], right: list[float]) -> float:
    """Compute cosine similarity for the isolated SQLite test backend."""
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    magnitude = math.sqrt(sum(a * a for a in left) * sum(b * b for b in right))
    return dot / magnitude if magnitude else 0


def line_description(line: BankLine) -> str:
    """Construct the common local retrieval query."""
    return (
        f"Payer {line.payer_name}; reference {line.raw_reference}; amount_cents {line.amount_cents}"
    )


def similar_cases(
    session: Session,
    line: BankLine,
    k: int = 5,
    customer_id: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve prior cases, excluding the current and reversed bank observations."""
    if not get_settings().retrieval_enabled:
        return []
    vector = get_embedder().encode(line_description(line))
    query = (
        select(ResolvedCase)
        .join(BankLine)
        .where(
            ResolvedCase.embedding.is_not(None),
            ResolvedCase.bank_line_id != line.id,
            BankLine.status != "reversed",
        )
    )
    if customer_id:
        query = query.where(ResolvedCase.customer_id == customer_id)
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SET LOCAL ivfflat.probes = 10"))
        rows = session.scalars(
            query.order_by(ResolvedCase.embedding.cosine_distance(vector)).limit(k)
        ).all()
    else:
        rows = sorted(
            session.scalars(query).all(),
            key=lambda c: cosine(list(c.embedding or []), vector),
            reverse=True,
        )[:k]
    return [
        {
            "id": c.id,
            "customer_id": c.customer_id,
            "summary": c.summary_text,
            "resolution": c.resolution_json,
            "resolved_by": c.resolved_by,
        }
        for c in rows
    ]


def search_runbook(session: Session, query: str, k: int = 5) -> list[dict[str, Any]]:
    """Retrieve policy sections using local cosine similarity."""
    if not get_settings().retrieval_enabled:
        return []
    vector = get_embedder().encode(query)
    statement = select(RunbookChunk).where(RunbookChunk.embedding.is_not(None))
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SET LOCAL ivfflat.probes = 10"))
        rows = session.scalars(
            statement.order_by(RunbookChunk.embedding.cosine_distance(vector)).limit(k)
        ).all()
    else:
        rows = sorted(
            session.scalars(statement).all(),
            key=lambda c: cosine(list(c.embedding or []), vector),
            reverse=True,
        )[:k]
    return [{"id": c.id, "section": c.section, "text": c.text} for c in rows]


def index_runbook(session: Session, document: str) -> int:
    """Chunk the policy by heading and upsert each locally embedded section."""
    sections: dict[str, list[str]] = {}
    heading = "Introduction"
    for line in document.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
        else:
            sections.setdefault(heading, []).append(line)
    for section, lines in sections.items():
        body = "\n".join(lines).strip()
        if not body:
            continue
        chunk = session.scalar(select(RunbookChunk).where(RunbookChunk.section == section))
        if chunk is None:
            chunk = RunbookChunk(section=section, text=body)
            session.add(chunk)
        chunk.text = body
        chunk.embedding = get_embedder().encode(f"{section}\n{body}")
    session.flush()
    return len(sections)
