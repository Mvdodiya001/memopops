"""Idempotently seed the canonical synthetic workspace into FalkorDB."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from memopops.formula import formula_hash, parse_formula, canonical_json
from memopops.store import AssertionRecord, FalkorSnapshotStore, calculate_knowledge_hash, graph_name_for_workspace


WORKSPACE_ID = "workspace_demo"
REVISION_ID = "rev_001"
ATOM_DEFINITIONS = [
    {"id": "api_v2", "label": "API v2", "meaning": "The API v2 implementation is available in the release candidate.", "scope": "release demo-42"},
    {"id": "tests_pass", "label": "Tests pass", "meaning": "The recorded integration test suite passes for the release candidate.", "scope": "release demo-42"},
    {"id": "release_ready", "label": "Release ready", "meaning": "The release candidate satisfies the encoded readiness policy.", "scope": "release demo-42"},
    {"id": "docs_signed", "label": "Docs signed", "meaning": "The release documentation has been signed off.", "scope": "release demo-42"},
]
ATOM_IDS = {item["id"] for item in ATOM_DEFINITIONS}
ASSERTION_INPUTS = [
    ("as_api_v2", {"op": "atom", "id": "api_v2"}, "fixture://demo-42/api-v2", "Synthetic fixture: API v2 is available."),
    ("as_tests_pass", {"op": "atom", "id": "tests_pass"}, "fixture://demo-42/tests-pass", "Synthetic fixture: integration tests passed."),
    (
        "as_ready_rule",
        {"op": "implies", "args": [{"op": "and", "args": [{"op": "atom", "id": "api_v2"}, {"op": "atom", "id": "tests_pass"}]}, {"op": "atom", "id": "release_ready"}]},
        "fixture://demo-42/readiness-policy",
        "Synthetic fixture: API v2 and passing tests imply release readiness.",
    ),
    (
        "as_failed_rule",
        {"op": "implies", "args": [{"op": "not", "arg": {"op": "atom", "id": "tests_pass"}}, {"op": "not", "arg": {"op": "atom", "id": "release_ready"}}]},
        "fixture://demo-42/failed-tests-policy",
        "Synthetic fixture: failing tests block release readiness.",
    ),
]


def load_local_env() -> None:
    """Load ignored .env values for the operator CLI without printing them."""
    path = Path(".env")
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def main() -> None:
    load_local_env()
    store = FalkorSnapshotStore.from_env()
    graph = store._get_client().select_graph(graph_name_for_workspace(WORKSPACE_ID))

    head_rows = graph.query(
        "MATCH (w:Workspace {id: $workspace_id}) RETURN w.head_revision AS head_revision LIMIT 1",
        {"workspace_id": WORKSPACE_ID},
    ).result_set
    if head_rows:
        if head_rows[0][0] == REVISION_ID:
            print("Demo workspace is already seeded at rev_001; no changes made.")
            store.close()
            return
        raise RuntimeError("Demo workspace already has a different head; refusing to reset it.")

    formulas = []
    records = []
    for assertion_id, formula_json, uri, excerpt in ASSERTION_INPUTS:
        formula = parse_formula(formula_json, ATOM_IDS)
        digest = formula_hash(formula)
        formulas.append(
            {
                "assertion_id": assertion_id,
                "formula_hash": digest,
                "canonical_json": canonical_json(formula),
                "evidence_id": f"ev_{assertion_id[3:]}",
                "uri": uri,
                "excerpt": excerpt,
                "content_digest": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
            }
        )
        records.append(AssertionRecord(assertion_id, formula, digest))
    revision_hash = calculate_knowledge_hash(records)

    graph.query(
        "UNWIND $atoms AS item MERGE (a:Atom {id: item.id}) "
        "ON CREATE SET a.label = item.label, a.meaning = item.meaning, a.scope = item.scope "
        "RETURN count(a)",
        {"atoms": ATOM_DEFINITIONS},
    )
    graph.query(
        "UNWIND $items AS item "
        "MERGE (f:Formula {hash: item.formula_hash}) ON CREATE SET f.canonical_json = item.canonical_json "
        "MERGE (a:Assertion {id: item.assertion_id}) "
        "ON CREATE SET a.actor_id = 'seed', a.created_at = '2026-10-17T00:00:00Z', "
        "a.acceptance = 'trusted_fixture', a.formula_hash = item.formula_hash "
        "MERGE (a)-[:ENCODES]->(f) "
        "MERGE (e:Evidence {id: item.evidence_id}) "
        "ON CREATE SET e.uri = item.uri, e.excerpt = item.excerpt, "
        "e.observed_at = '2026-10-17T00:00:00Z', e.content_digest = item.content_digest "
        "MERGE (a)-[:SUPPORTED_BY]->(e) RETURN count(a)",
        {"items": formulas},
    )
    graph.query(
        "MERGE (r:Revision {id: $revision_id}) "
        "ON CREATE SET r.sequence = 1, r.knowledge_hash = $knowledge_hash, r.semantics_version = 'boolean-v1' "
        "WITH r UNWIND $assertion_ids AS assertion_id "
        "MATCH (a:Assertion {id: assertion_id}) MERGE (r)-[:INCLUDES]->(a) "
        "RETURN count(a)",
        {
            "revision_id": REVISION_ID,
            "knowledge_hash": revision_hash,
            "assertion_ids": [item[0] for item in ASSERTION_INPUTS],
        },
    )
    workspace = graph.query(
        "MERGE (w:Workspace {id: $workspace_id}) "
        "ON CREATE SET w.head_revision = $revision_id, w.sequence = 1 "
        "RETURN w.head_revision AS head_revision",
        {"workspace_id": WORKSPACE_ID, "revision_id": REVISION_ID},
    ).result_set
    store.close()
    if not workspace or workspace[0][0] != REVISION_ID:
        raise RuntimeError("Demo seed did not establish the requested initial head")
    print("Seeded synthetic demo workspace at rev_001 (four assertions, four registered atoms).")


if __name__ == "__main__":
    main()
