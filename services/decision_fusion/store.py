from __future__ import annotations

import json
import threading
from typing import Protocol

from services.common.db import execute, fetchone

from .models import DecisionCase


class DecisionStore(Protocol):
    def create(self, case: DecisionCase) -> None: ...
    def get(self, proposal_id: str) -> DecisionCase | None: ...
    def save(self, case: DecisionCase) -> None: ...


class InMemoryDecisionStore:
    def __init__(self) -> None:
        self._items: dict[str, DecisionCase] = {}
        self._lock = threading.Lock()

    def create(self, case: DecisionCase) -> None:
        with self._lock:
            proposal_id = case.proposal.proposal_id
            if proposal_id in self._items:
                raise ValueError("proposal already exists")
            self._items[proposal_id] = case

    def get(self, proposal_id: str) -> DecisionCase | None:
        with self._lock:
            return self._items.get(proposal_id)

    def save(self, case: DecisionCase) -> None:
        with self._lock:
            proposal_id = case.proposal.proposal_id
            if proposal_id not in self._items:
                raise KeyError("proposal not found")
            self._items[proposal_id] = case


class PostgresDecisionStore:
    """Persist I7 cases in the existing workflows table."""

    def create(self, case: DecisionCase) -> None:
        payload = json.dumps({"i7": case.to_dict()})
        execute(
            "INSERT INTO workflows(workflow_id, status, payload, decision, reviewer) "
            "VALUES (%s, %s, %s, %s, %s)",
            (
                case.proposal.proposal_id,
                case.status.value,
                payload,
                case.proposal.decision.value,
                case.review.reviewer if case.review else None,
            ),
        )

    def get(self, proposal_id: str) -> DecisionCase | None:
        row = fetchone("SELECT payload FROM workflows WHERE workflow_id = %s", (proposal_id,))
        if not row:
            return None
        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not isinstance(payload, dict) or "i7" not in payload:
            return None
        return DecisionCase.from_dict(dict(payload["i7"]))

    def save(self, case: DecisionCase) -> None:
        payload = json.dumps({"i7": case.to_dict()})
        execute(
            "UPDATE workflows SET status=%s, payload=%s, decision=%s, reviewer=%s, "
            "updated_at=now() WHERE workflow_id=%s",
            (
                case.status.value,
                payload,
                case.proposal.decision.value,
                case.review.reviewer if case.review else None,
                case.proposal.proposal_id,
            ),
        )
