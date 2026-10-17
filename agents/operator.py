"""Trusted fixture actions. These are operator calls, not model tools."""

from __future__ import annotations

from typing import Any

from agents.client import MemoryClient


def submit_revision(
    client: MemoryClient,
    *,
    expected_revision: str,
    idempotency_key: str,
    reason: str,
    mutations: list[dict[str, Any]],
    acceptance: str = "trusted_fixture",
) -> tuple[int, dict[str, Any]]:
    return client.submit_revision(
        {
            "expected_revision": expected_revision,
            "idempotency_key": idempotency_key,
            "reason": reason,
            "acceptance": acceptance,
            "mutations": mutations,
        }
    )


def tests_failed_evidence() -> dict[str, str]:
    return {
        "uri": "fixture://demo-42/tests-failed",
        "excerpt": "Synthetic fixture: integration tests failed.",
        "observed_at": "2026-10-17T12:00:00Z",
    }


def inconsistent_failure_add() -> list[dict[str, Any]]:
    """Add NOT tests_pass beside the accepted passing report."""
    return [
        {
            "op": "add",
            "assertion": {
                "client_ref": "operator-conflicting-failure",
                "formula": {"op": "not", "arg": {"op": "atom", "id": "tests_pass"}},
                "evidence": [tests_failed_evidence()],
            },
        }
    ]


def replace_passing_tests() -> list[dict[str, Any]]:
    """Replace the passing report with an explicit failure."""
    return [
        {
            "op": "replace",
            "target_assertion_id": "as_tests_pass",
            "assertion": {
                "client_ref": "operator-tests-failed",
                "formula": {"op": "not", "arg": {"op": "atom", "id": "tests_pass"}},
                "evidence": [tests_failed_evidence()],
            },
        }
    ]
