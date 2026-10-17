"""In-memory snapshot behind the published API routes.

This lets replay and evaluation exercise revision guards, quarantine, and
certificate checks without FalkorDB. It is a test double, not the service store.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from threading import RLock
from typing import Any
from uuid import uuid4

from agents.demo_memory import (
    ASSERTION_INPUTS,
    ATOM_IDS,
    CREATED_AT,
    REVISION_ID,
    WORKSPACE_ID,
    demo_assertions,
    demo_knowledge_hash,
    evidence_for,
)
from memopops.formula import formula_hash, formula_to_json, parse_formula
from memopops.store import (
    AssertionRecord,
    IdempotencyConflictError,
    RevisionHeadConflictError,
    Snapshot,
    SnapshotIntegrityError,
    SnapshotNotFoundError,
    calculate_knowledge_hash,
)


@dataclass
class StoredAssertion:
    record: AssertionRecord
    actor_id: str
    acceptance: str
    created_at: str
    evidence: tuple[dict[str, str], ...]


class LabSnapshotStore:
    def __init__(self) -> None:
        self._lock = RLock()
        records = demo_assertions()
        stored = []
        for record, (assertion_id, _formula, uri, excerpt) in zip(records, ASSERTION_INPUTS, strict=True):
            stored.append(
                StoredAssertion(
                    record=record,
                    actor_id="seed",
                    acceptance="trusted_fixture",
                    created_at=CREATED_AT,
                    evidence=(evidence_for(assertion_id, uri, excerpt),),
                )
            )
        self._members: dict[str, tuple[StoredAssertion, ...]] = {REVISION_ID: tuple(stored)}
        self._meta: dict[str, dict[str, Any]] = {
            REVISION_ID: {
                "revision_id": REVISION_ID,
                "parent_revision_id": None,
                "sequence": 1,
                "knowledge_hash": demo_knowledge_hash(),
                "reason": "Seed the release demo-42 snapshot.",
                "acceptance": "trusted_fixture",
                "actor_id": "seed",
                "created_at": CREATED_AT,
                "removed_assertion_ids": [],
            }
        }
        self.head: str | None = REVISION_ID
        self._revision_receipts: dict[str, tuple[str, dict[str, Any]]] = {}
        self._query_receipts: dict[str, tuple[str, dict[str, Any]]] = {}
        self._decision_receipts: dict[str, tuple[str, dict[str, Any]]] = {}
        self._query_premises: dict[str, list[str]] = {}
        self.quarantined: list[dict[str, Any]] = []

    def ping(self) -> bool:
        return True

    def close(self) -> None:
        return None

    def current_head(self, workspace_id: str) -> str | None:
        with self._lock:
            if workspace_id != WORKSPACE_ID:
                return None
            return self.head

    def load_snapshot(self, workspace_id: str, revision_id: str) -> Snapshot:
        with self._lock:
            members = self._require_members(workspace_id, revision_id)
            meta = self._meta[revision_id]
            return Snapshot(
                workspace_id=workspace_id,
                revision_id=revision_id,
                knowledge_hash=meta["knowledge_hash"],
                atom_ids=ATOM_IDS,
                assertions=tuple(item.record for item in members),
            )

    def load_memory(self, workspace_id: str, revision_id: str) -> dict[str, Any]:
        with self._lock:
            members = self._require_members(workspace_id, revision_id)
            assertions = []
            for item in members:
                evidence = [dict(entry) for entry in item.evidence]
                for entry in evidence:
                    digest = __import__("hashlib").sha256(entry["excerpt"].encode("utf-8")).hexdigest()
                    if digest != entry["content_digest"]:
                        raise SnapshotIntegrityError(f"evidence digest mismatch for assertion {item.record.id}")
                assertions.append(
                    {
                        "id": item.record.id,
                        "formula": formula_to_json(item.record.formula),
                        "formula_hash": item.record.formula_hash,
                        "actor_id": item.actor_id,
                        "acceptance": item.acceptance,
                        "created_at": item.created_at,
                        "evidence": evidence,
                    }
                )
            meta = self._meta[revision_id]
            return {
                "workspace_id": workspace_id,
                "revision_id": revision_id,
                "knowledge_hash": meta["knowledge_hash"],
                "atom_ids": sorted(ATOM_IDS),
                "assertions": sorted(assertions, key=lambda item: item["id"]),
            }

    def list_revisions(
        self, workspace_id: str, *, before_sequence: int | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        with self._lock:
            if workspace_id != WORKSPACE_ID or self.head is None:
                return []
            items = [
                {key: value for key, value in meta.items() if key != "removed_assertion_ids"}
                for meta in self._meta.values()
                if before_sequence is None or meta["sequence"] < before_sequence
            ]
            items.sort(key=lambda item: item["sequence"], reverse=True)
            return items[:limit]

    def get_revision_impact(
        self,
        workspace_id: str,
        revision_id: str,
        *,
        before_query_id: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        with self._lock:
            self._require_members(workspace_id, revision_id)
            meta = self._meta[revision_id]
            parent_revision_id = meta["parent_revision_id"]
            changed_ids = set(meta["removed_assertion_ids"])
            if parent_revision_id is None or not changed_ids:
                return {
                    "workspace_id": workspace_id,
                    "revision_id": revision_id,
                    "parent_revision_id": parent_revision_id,
                    "changed_assertion_ids": sorted(changed_ids),
                    "total_count": 0,
                    "items": [],
                    "next_cursor": None,
                }
            items = []
            for _digest, result in self._query_receipts.values():
                if result.get("revision_id") != parent_revision_id:
                    continue
                query_id = str(result.get("query_id", ""))
                if before_query_id is not None and query_id <= before_query_id:
                    continue
                premises = set(self._query_premises.get(query_id, []))
                affected = sorted(premises & changed_ids)
                if not affected:
                    continue
                proof_status = result.get("proof_status", "NOT_REQUESTED")
                items.append(
                    {
                        "query_id": query_id,
                        "revision_id": parent_revision_id,
                        "query_hash": result.get("query_hash"),
                        "result": result.get("result"),
                        "proof_status": proof_status,
                        "dependency_basis": "CHECKED_SUPPORT" if proof_status == "VERIFIED" else "FULL_SNAPSHOT",
                        "support_assertion_ids": result.get("support_assertion_ids", []),
                        "changed_assertion_ids": affected,
                        "freshness": "HISTORICAL",
                    }
                )
            items.sort(key=lambda item: item["query_id"])
            page = items[:limit]
            return {
                "workspace_id": workspace_id,
                "revision_id": revision_id,
                "parent_revision_id": parent_revision_id,
                "changed_assertion_ids": sorted(changed_ids),
                "total_count": len(items),
                "items": page,
                "next_cursor": page[-1]["query_id"] if len(items) > limit else None,
            }

    def get_query_result(self, workspace_id: str, query_id: str) -> dict[str, Any] | None:
        with self._lock:
            if workspace_id != WORKSPACE_ID:
                return None
            for _digest, result in self._query_receipts.values():
                if result.get("query_id") == query_id:
                    return result
            return None

    def get_query_receipt(
        self, workspace_id: str, idempotency_key: str, request_hash: str
    ) -> dict[str, Any] | None:
        return self._receipt(self._query_receipts, workspace_id, idempotency_key, request_hash)

    def get_revision_receipt(
        self, workspace_id: str, idempotency_key: str, request_hash: str
    ) -> dict[str, Any] | None:
        return self._receipt(self._revision_receipts, workspace_id, idempotency_key, request_hash)

    def list_quarantined_proposals(self, workspace_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            if workspace_id != WORKSPACE_ID:
                return []
            records = []
            for proposal in self.quarantined[:limit]:
                records.append(
                    {
                        "proposal_id": proposal["id"],
                        "base_revision_id": proposal.get("base_revision_id", REVISION_ID),
                        "reason": "INCONSISTENT_CANDIDATE",
                        "request_json": proposal["request_json"],
                        "created_at": proposal["created_at"],
                    }
                )
            return records

    def get_decision_receipt(
        self, workspace_id: str, idempotency_key: str, request_hash: str
    ) -> dict[str, Any] | None:
        return self._receipt(self._decision_receipts, workspace_id, idempotency_key, request_hash)

    def persist_decision(
        self,
        workspace_id: str,
        expected_revision_id: str,
        query_id: str,
        idempotency_key: str,
        request_hash: str,
        decision: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            prior = self.get_decision_receipt(workspace_id, idempotency_key, request_hash)
            if prior is not None:
                return prior
            if workspace_id != WORKSPACE_ID:
                raise SnapshotNotFoundError(expected_revision_id)
            if expected_revision_id != self.head:
                raise RevisionHeadConflictError(expected_revision_id, self.head)
            query = self.get_query_result(workspace_id, query_id)
            if query is None or query.get("revision_id") != expected_revision_id:
                raise SnapshotNotFoundError(query_id)
            result = {
                "decision_id": decision["id"],
                "workspace_id": workspace_id,
                "revision_id": expected_revision_id,
                "query_id": query_id,
                "outcome": decision["outcome"],
                "rationale": decision["rationale"],
                "actor_id": decision["actor_id"],
                "created_at": decision["created_at"],
            }
            self._decision_receipts[idempotency_key] = (request_hash, result)
            return result

    def persist_query_result(
        self,
        workspace_id: str,
        revision_id: str,
        idempotency_key: str,
        request_hash: str,
        result_payload: dict[str, Any],
        uses_premise_ids: list[str],
    ) -> dict[str, Any]:
        with self._lock:
            prior = self.get_query_receipt(workspace_id, idempotency_key, request_hash)
            if prior is not None:
                return prior
            members = self._require_members(workspace_id, revision_id)
            known = {item.record.id for item in members}
            if any(item not in known for item in uses_premise_ids):
                raise SnapshotNotFoundError(revision_id)
            stored = dict(result_payload)
            stored.setdefault("query_id", f"query_{uuid4().hex}")
            self._query_receipts[idempotency_key] = (request_hash, stored)
            self._query_premises[stored["query_id"]] = list(uses_premise_ids)
            return stored

    def persist_quarantined_proposal(
        self,
        workspace_id: str,
        base_revision_id: str,
        idempotency_key: str,
        request_hash: str,
        proposal: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            prior = self.get_revision_receipt(workspace_id, idempotency_key, request_hash)
            if prior is not None:
                return prior
            self._require_members(workspace_id, base_revision_id)
            result = {
                "status": "QUARANTINED",
                "proposal_id": proposal["id"],
                "base_revision_id": base_revision_id,
                "reason": "INCONSISTENT_CANDIDATE",
            }
            self._revision_receipts[idempotency_key] = (request_hash, result)
            self.quarantined.append({**proposal, "base_revision_id": base_revision_id})
            return result

    def publish_revision(
        self,
        workspace_id: str,
        expected_revision_id: str,
        idempotency_key: str,
        request_hash: str,
        revision: dict[str, Any],
        added_assertions: list[dict[str, Any]],
        assertion_ids: list[str],
    ) -> dict[str, Any]:
        with self._lock:
            prior = self.get_revision_receipt(workspace_id, idempotency_key, request_hash)
            if prior is not None:
                return prior
            if workspace_id != WORKSPACE_ID or expected_revision_id not in self._members:
                raise SnapshotNotFoundError(expected_revision_id)
            if expected_revision_id != self.head:
                raise RevisionHeadConflictError(expected_revision_id, self.head)
            parent_members = {item.record.id: item for item in self._members[expected_revision_id]}
            for added in added_assertions:
                parent_members[added["id"]] = self._stored_from_added(added)
            if any(assertion_id not in parent_members for assertion_id in assertion_ids):
                raise SnapshotIntegrityError("published membership names an unknown assertion")
            members = tuple(parent_members[assertion_id] for assertion_id in assertion_ids)
            knowledge_hash = calculate_knowledge_hash([item.record for item in members])
            if knowledge_hash != revision["knowledge_hash"]:
                raise SnapshotIntegrityError("published knowledge hash does not match membership")
            parent_sequence = self._meta[expected_revision_id]["sequence"]
            self._members[revision["id"]] = members
            self._meta[revision["id"]] = {
                "revision_id": revision["id"],
                "parent_revision_id": expected_revision_id,
                "sequence": parent_sequence + 1,
                "knowledge_hash": knowledge_hash,
                "reason": revision["reason"],
                "acceptance": revision["acceptance"],
                "actor_id": revision["actor_id"],
                "created_at": revision["created_at"],
                "removed_assertion_ids": list(revision["removed_assertion_ids"]),
            }
            self.head = revision["id"]
            result = {
                "status": "COMMITTED",
                "revision_id": revision["id"],
                "parent_revision_id": expected_revision_id,
                "knowledge_hash": knowledge_hash,
                "client_refs": revision["client_refs"],
            }
            self._revision_receipts[idempotency_key] = (request_hash, result)
            return result

    def _require_members(self, workspace_id: str, revision_id: str) -> tuple[StoredAssertion, ...]:
        if workspace_id != WORKSPACE_ID or revision_id not in self._members:
            raise SnapshotNotFoundError(revision_id)
        return self._members[revision_id]

    def _receipt(
        self,
        table: dict[str, tuple[str, dict[str, Any]]],
        workspace_id: str,
        idempotency_key: str,
        request_hash: str,
    ) -> dict[str, Any] | None:
        if workspace_id != WORKSPACE_ID or idempotency_key not in table:
            return None
        previous_hash, result = table[idempotency_key]
        if previous_hash != request_hash:
            raise IdempotencyConflictError(idempotency_key)
        return result

    def _stored_from_added(self, added: dict[str, Any]) -> StoredAssertion:
        formula = parse_formula(json.loads(added["canonical_json"]), ATOM_IDS)
        digest = formula_hash(formula)
        if digest != added["formula_hash"]:
            raise SnapshotIntegrityError("added assertion hash does not match its formula")
        evidence = tuple(dict(item) for item in added["evidence"])
        return StoredAssertion(
            record=AssertionRecord(added["id"], formula, digest),
            actor_id=added["actor_id"],
            acceptance=added["acceptance"],
            created_at=added["created_at"],
            evidence=evidence,
        )
