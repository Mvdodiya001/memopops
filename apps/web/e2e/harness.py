"""Local API process for the browser check.

This uses the published query route and solver. It is not a FalkorDB seed:
the snapshot is held in memory because the database image and hosted endpoint
were unreachable from this machine.
"""

from __future__ import annotations

import json
import os

import uvicorn

from memopops.api import create_app
from memopops.formula import formula_hash, formula_to_json, parse_formula
from memopops.store import AssertionRecord, IdempotencyConflictError, Snapshot, calculate_knowledge_hash

WORKSPACE_ID = "workspace_demo"
REVISION_ID = "rev_001"
ATOMS = {"api_v2", "tests_pass", "release_ready", "docs_signed"}
FORMULAS = [
    ("as_api_v2", {"op": "atom", "id": "api_v2"}),
    ("as_tests_pass", {"op": "atom", "id": "tests_pass"}),
    (
        "as_ready_rule",
        {
            "op": "implies",
            "args": [
                {"op": "and", "args": [{"op": "atom", "id": "api_v2"}, {"op": "atom", "id": "tests_pass"}]},
                {"op": "atom", "id": "release_ready"},
            ],
        },
    ),
    (
        "as_failed_rule",
        {
            "op": "implies",
            "args": [
                {"op": "not", "arg": {"op": "atom", "id": "tests_pass"}},
                {"op": "not", "arg": {"op": "atom", "id": "release_ready"}},
            ],
        },
    ),
]


class MemorySnapshotStore:
    def __init__(self) -> None:
        assertions = []
        for assertion_id, formula_json in FORMULAS:
            formula = parse_formula(formula_json, ATOMS)
            assertions.append(AssertionRecord(assertion_id, formula, formula_hash(formula)))
        self.snapshot = Snapshot(
            workspace_id=WORKSPACE_ID,
            revision_id=REVISION_ID,
            knowledge_hash=calculate_knowledge_hash(assertions),
            atom_ids=frozenset(ATOMS),
            assertions=tuple(assertions),
        )
        self.saved: dict[str, tuple[str, dict]] = {}

    def ping(self) -> bool:
        return True

    def close(self) -> None:
        return None

    def load_snapshot(self, workspace_id: str, revision_id: str) -> Snapshot:
        if workspace_id != WORKSPACE_ID or revision_id != REVISION_ID:
            from memopops.store import SnapshotNotFoundError

            raise SnapshotNotFoundError(revision_id)
        return self.snapshot

    def current_head(self, workspace_id: str) -> str:
        return REVISION_ID

    def load_memory(self, workspace_id: str, revision_id: str) -> dict:
        snapshot = self.load_snapshot(workspace_id, revision_id)
        excerpt = "Synthetic fixture evidence for the browser check."
        assertions = []
        for item in snapshot.assertions:
            assertions.append(
                {
                    "id": item.id,
                    "formula": formula_to_json(item.formula),
                    "formula_hash": item.formula_hash,
                    "actor_id": "operator",
                    "acceptance": "trusted_fixture",
                    "created_at": "2026-10-17T09:42:00Z",
                    "evidence": [
                        {
                            "id": f"ev_{item.id}",
                            "uri": f"fixture://demo/{item.id}",
                            "excerpt": excerpt,
                            "observed_at": "2026-10-17T09:00:00Z",
                            "content_digest": __import__("hashlib").sha256(excerpt.encode("utf-8")).hexdigest(),
                        }
                    ],
                }
            )
        return {
            "workspace_id": workspace_id,
            "revision_id": snapshot.revision_id,
            "knowledge_hash": snapshot.knowledge_hash,
            "atom_ids": sorted(snapshot.atom_ids),
            "assertions": sorted(assertions, key=lambda item: item["id"]),
        }

    def list_revisions(self, workspace_id: str, before_sequence: int | None = None, limit: int = 50) -> list[dict]:
        self.load_snapshot(workspace_id, REVISION_ID)
        return [
            {
                "revision_id": REVISION_ID,
                "parent_revision_id": None,
                "sequence": 1,
                "knowledge_hash": self.snapshot.knowledge_hash,
                "reason": "Seed the release demo-42 snapshot.",
                "acceptance": "trusted_fixture",
                "actor_id": "operator",
                "created_at": "2026-10-17T09:42:00Z",
            }
        ]

    def get_query_result(self, workspace_id: str, query_id: str) -> dict | None:
        for _, result in self.saved.values():
            if result.get("query_id") == query_id:
                return result
        return None

    def get_query_receipt(self, workspace_id: str, idempotency_key: str, request_hash: str) -> dict | None:
        if idempotency_key not in self.saved:
            return None
        previous_hash, result = self.saved[idempotency_key]
        if previous_hash != request_hash:
            raise IdempotencyConflictError(idempotency_key)
        return result

    def persist_query_result(
        self,
        workspace_id: str,
        revision_id: str,
        idempotency_key: str,
        request_hash: str,
        result_payload: dict,
        uses_premise_ids: list[str] | None = None,
    ) -> dict:
        if idempotency_key in self.saved:
            previous_hash, result = self.saved[idempotency_key]
            if previous_hash != request_hash:
                raise IdempotencyConflictError(idempotency_key)
            return result
        self.saved[idempotency_key] = (request_hash, result_payload)
        return result_payload


def main() -> None:
    os.environ["MEMOPOPS_AUTH_TOKENS"] = json.dumps(
        {"local-reader-token": {"workspace_id": WORKSPACE_ID, "role": "reader"}}
    )
    uvicorn.run(create_app(MemorySnapshotStore()), host="127.0.0.1", port=8010)


if __name__ == "__main__":
    main()
