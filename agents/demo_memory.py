"""Synthetic release-demo assertions shared by the lab snapshot and baselines.

These formulas match scripts/seed_demo.py. The lab copy is an in-memory
snapshot for tests and scripted replay. It is not a FalkorDB seed.
"""

from __future__ import annotations

import hashlib

from memopops.formula import formula_hash, parse_formula
from memopops.store import AssertionRecord, calculate_knowledge_hash


WORKSPACE_ID = "workspace_demo"
REVISION_ID = "rev_001"
ATOM_IDS = frozenset({"api_v2", "tests_pass", "release_ready", "docs_signed"})
CREATED_AT = "2026-10-17T00:00:00Z"

ASSERTION_INPUTS = (
    (
        "as_api_v2",
        {"op": "atom", "id": "api_v2"},
        "fixture://demo-42/api-v2",
        "Synthetic fixture: API v2 is available.",
    ),
    (
        "as_tests_pass",
        {"op": "atom", "id": "tests_pass"},
        "fixture://demo-42/tests-pass",
        "Synthetic fixture: integration tests passed.",
    ),
    (
        "as_ready_rule",
        {
            "op": "implies",
            "args": [
                {
                    "op": "and",
                    "args": [
                        {"op": "atom", "id": "api_v2"},
                        {"op": "atom", "id": "tests_pass"},
                    ],
                },
                {"op": "atom", "id": "release_ready"},
            ],
        },
        "fixture://demo-42/readiness-policy",
        "Synthetic fixture: API v2 and passing tests imply release readiness.",
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
        "fixture://demo-42/failed-tests-policy",
        "Synthetic fixture: failing tests block release readiness.",
    ),
)


def evidence_for(assertion_id: str, uri: str, excerpt: str) -> dict[str, str]:
    return {
        "id": f"ev_{assertion_id[3:]}",
        "uri": uri,
        "excerpt": excerpt,
        "observed_at": CREATED_AT,
        "content_digest": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
    }


def demo_assertions() -> tuple[AssertionRecord, ...]:
    records = []
    for assertion_id, formula_json, _uri, _excerpt in ASSERTION_INPUTS:
        formula = parse_formula(formula_json, ATOM_IDS)
        records.append(AssertionRecord(assertion_id, formula, formula_hash(formula)))
    return tuple(records)


def demo_knowledge_hash() -> str:
    return calculate_knowledge_hash(demo_assertions())
