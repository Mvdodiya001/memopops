"""Deterministic release-demo scripts. These are replay, not live model output."""

from __future__ import annotations

from typing import Any


RELEASE_QUERY = {"op": "atom", "id": "release_ready"}


class ScriptedReleaseReader:
    """Inspect, query release readiness, and record the matching decision."""

    def __init__(self, prior_decision: dict[str, Any] | None = None):
        self.prior_decision = prior_decision
        self._next = "inspect"

    def next_action(self, observation: dict[str, Any]) -> dict[str, Any]:
        stage = self._next
        if stage == "inspect":
            self._next = "after_inspect"
            return {"type": "tool", "name": "inspect_memory", "arguments": {}}
        if stage == "after_inspect":
            head = observation["head_revision_id"]
            prior = self.prior_decision
            if prior and prior["revision_id"] != head:
                self._next = "query"
                return {
                    "type": "tool",
                    "name": "record_decision",
                    "arguments": {
                        "expected_revision_id": prior["revision_id"],
                        "query_id": prior["query_id"],
                        "choice": prior["choice"],
                    },
                }
            self._next = "decide"
            return _query_release(head)
        if stage == "query":
            self._next = "decide"
            head = observation.get("head_revision_id") or observation.get("revision_id")
            return _query_release(str(head))
        if stage == "decide":
            self._next = "stop"
            result = observation["result"]
            choice = {"PROVED": "ship", "REFUTED": "hold"}.get(result, "abstain")
            return {
                "type": "tool",
                "name": "record_decision",
                "arguments": {
                    "expected_revision_id": observation["revision_id"],
                    "query_id": observation["query_id"],
                    "choice": choice,
                },
            }
        return {"type": "stop"}


class ScriptedFailureWriter:
    """Propose an explicit test-failure assertion. The service decides acceptance."""

    def __init__(self):
        self._next = "inspect"

    def next_action(self, observation: dict[str, Any]) -> dict[str, Any]:
        if self._next == "inspect":
            self._next = "propose"
            return {"type": "tool", "name": "inspect_memory", "arguments": {}}
        if self._next == "propose":
            self._next = "stop"
            return {
                "type": "tool",
                "name": "propose_assertion",
                "arguments": {
                    "expected_revision_id": observation["head_revision_id"],
                    "atom_id": "tests_pass",
                    "formula": {"op": "not", "arg": {"op": "atom", "id": "tests_pass"}},
                    "reason": "Writer reports that the integration tests failed.",
                    "client_ref": "writer-tests-failed",
                    "evidence": {
                        "uri": "fixture://demo-42/writer-tests-failed",
                        "excerpt": "Synthetic writer report: integration tests failed.",
                        "observed_at": "2026-10-17T12:00:00Z",
                    },
                },
            }
        return {"type": "stop"}


def _query_release(revision_id: str) -> dict[str, Any]:
    return {
        "type": "tool",
        "name": "query_conclusion",
        "arguments": {
            "revision_id": revision_id,
            "query": RELEASE_QUERY,
            "proof_mode": "certificate",
        },
    }
