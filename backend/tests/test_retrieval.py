import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.agent.schemas import SimilarArgs
from backend.app.agent.tools import ToolExecutor
from backend.app.config import get_settings
from backend.app.db.models import BankLine, Customer, ResolvedCase
from backend.app.ingest.seed import load_dataset
from backend.app.retrieval.embedder import HashEmbedder, LocalEmbedder, get_embedder
from backend.app.retrieval.index import cosine, index_runbook, search_runbook, similar_cases
from evals.generate_dataset import write_dataset


def test_seed_and_ablation(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "data"
    dataset = write_dataset(directory)
    assert load_dataset(session, directory)["history_cases"] == 300
    assert load_dataset(session, directory)["bank_lines"]["inserted"] == 0
    assert session.scalar(select(func.count()).select_from(ResolvedCase)) == 300
    customer = session.scalar(select(Customer))
    assert customer is not None and customer.notes_embedding is not None
    assert len(customer.notes_embedding) == 384
    line = session.get(BankLine, dataset["labels"][0]["bank_line_id"])
    assert line is not None
    candidates = similar_cases(session, line, 5, customer.id)
    assert candidates and all(c["customer_id"] == customer.id for c in candidates)
    assert search_runbook(session, "split oldest invoice", 3)
    monkeypatch.setenv("RETRIEVAL_ENABLED", "false")
    get_settings.cache_clear()
    assert similar_cases(session, line) == []
    assert search_runbook(session, "split") == []


def test_approval_is_retrievable_immediately(
    client: TestClient, session: Session, tmp_path: Path
) -> None:
    dataset = write_dataset(tmp_path)
    load_dataset(session, tmp_path)
    session.commit()
    headers = {"X-API-Key": "clearline-local-demo", "X-Reviewer": "Synthetic Reviewer"}
    client.post("/runs/reconcile", headers=headers)
    pending = next(p for p in client.get("/proposals").json() if p["decision"] == "partial")
    assert (
        client.post(f"/proposals/{pending['id']}/approve", headers=headers, json={}).status_code
        == 200
    )
    case = session.scalar(
        select(ResolvedCase).where(ResolvedCase.bank_line_id == pending["bank_line"]["id"])
    )
    assert case is not None and case.embedding is not None
    query = session.get(BankLine, dataset["labels"][0]["bank_line_id"])
    assert query is not None
    found = ToolExecutor(session, query).execute(
        "find_similar_cases", SimilarArgs(customer_id=case.customer_id)
    )
    assert case.id in [r["id"] for r in found]


def test_hash_and_local_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    embedder = HashEmbedder()
    assert embedder.encode("Lumen split payment") == embedder.encode("Lumen split payment")
    assert len(embedder.encode("Lumen")) == 384
    assert cosine(embedder.encode("Lumen"), embedder.encode("Lumen")) == pytest.approx(1)
    assert cosine(embedder.encode(""), embedder.encode("")) == 0
    model = MagicMock()
    model.encode.return_value.tolist.return_value = [1.0] * 384
    constructor = MagicMock(return_value=model)
    monkeypatch.setitem(
        sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=constructor)
    )
    assert len(LocalEmbedder().encode("masked text")) == 384
    assert constructor.call_args.kwargs["local_files_only"] is True
    model.encode.return_value.tolist.return_value = [1]
    with pytest.raises(ValueError):
        LocalEmbedder().encode("masked text")
    monkeypatch.setenv("EMBEDDER", "local")
    get_settings.cache_clear()
    get_embedder.cache_clear()
    assert isinstance(get_embedder(), LocalEmbedder)


def test_runbook_upsert(session: Session) -> None:
    assert index_runbook(session, "## Splits\nOldest first") == 1
    assert index_runbook(session, "## Splits\nReview oldest first") == 1
    assert "Review" in search_runbook(session, "oldest")[0]["text"]
