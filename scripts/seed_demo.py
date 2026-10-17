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


def verify_existing_seed_records(graph, formulas: list[dict[str, str]], revision_hash: str) -> None:
    """Refuse to merge the fixture into pre-existing records with different contents."""
    atom_ids = [item["id"] for item in ATOM_DEFINITIONS]
    atom_rows = graph.query(
        "MATCH (a:Atom) WHERE a.id IN $ids "
        "RETURN a.id, a.label, a.meaning, a.scope",
        {"ids": atom_ids},
    ).result_set
    expected_atoms = {item["id"]: item for item in ATOM_DEFINITIONS}
    for atom_id, label, meaning, scope in atom_rows:
        expected = expected_atoms[atom_id]
        if (label, meaning, scope) != (expected["label"], expected["meaning"], expected["scope"]):
            raise RuntimeError(f"Existing demo atom {atom_id} has different immutable meaning.")

    formula_rows = graph.query(
        "MATCH (f:Formula) WHERE f.hash IN $hashes RETURN f.hash, f.canonical_json",
        {"hashes": [item["formula_hash"] for item in formulas]},
    ).result_set
    expected_formulas = {item["formula_hash"]: item["canonical_json"] for item in formulas}
    for digest, canonical in formula_rows:
        if expected_formulas.get(digest) != canonical:
            raise RuntimeError("Existing demo formula hash has different canonical contents.")

    assertion_rows = graph.query(
        "MATCH (a:Assertion) WHERE a.id IN $ids "
        "OPTIONAL MATCH (a)-[:ENCODES]->(f:Formula) "
        "RETURN a.id, a.actor_id, a.acceptance, a.formula_hash, f.hash",
        {"ids": [item["assertion_id"] for item in formulas]},
    ).result_set
    expected_assertions = {item["assertion_id"]: item["formula_hash"] for item in formulas}
    found_assertions: dict[str, tuple[str, str, str, set[str]]] = {}
    for assertion_id, actor_id, acceptance, stored_hash, formula_digest in assertion_rows:
        existing = found_assertions.setdefault(
            assertion_id, (actor_id, acceptance, stored_hash, set())
        )
        previous_actor, previous_acceptance, previous_hash, linked_hashes = existing
        if (actor_id, acceptance, stored_hash) != (
            previous_actor, previous_acceptance, previous_hash
        ):
            raise RuntimeError(f"Existing demo assertion {assertion_id} has conflicting metadata.")
        if formula_digest is not None:
            linked_hashes.add(formula_digest)
    for assertion_id, (actor_id, acceptance, stored_hash, linked_hashes) in found_assertions.items():
        if (actor_id, acceptance) != ("seed", "trusted_fixture"):
            raise RuntimeError(f"Existing demo assertion {assertion_id} has different provenance.")
        if stored_hash != expected_assertions[assertion_id] or linked_hashes != {stored_hash}:
            raise RuntimeError(f"Existing demo assertion {assertion_id} has conflicting formula links.")

    expected_evidence = {
        item["evidence_id"]: (item["uri"], item["excerpt"], item["content_digest"])
        for item in formulas
    }
    evidence_rows = graph.query(
        "MATCH (e:Evidence) WHERE e.id IN $ids "
        "RETURN e.id, e.uri, e.excerpt, e.observed_at, e.content_digest",
        {"ids": list(expected_evidence)},
    ).result_set
    for evidence_id, uri, excerpt, observed_at, digest in evidence_rows:
        expected = expected_evidence[evidence_id]
        if (uri, excerpt, observed_at, digest) != (*expected[:2], "2026-10-17T00:00:00Z", expected[2]):
            raise RuntimeError(f"Existing demo evidence {evidence_id} has different immutable contents.")

    revision_rows = graph.query(
        "MATCH (r:Revision {id: $revision_id}) "
        "OPTIONAL MATCH (r)-[:INCLUDES]->(a:Assertion) "
        "RETURN r.knowledge_hash, a.id",
        {"revision_id": REVISION_ID},
    ).result_set
    if revision_rows:
        stored_hash = revision_rows[0][0]
        members = {row[1] for row in revision_rows if row[1] is not None}
        expected_members = set(expected_assertions)
        if stored_hash != revision_hash or members != expected_members:
            raise RuntimeError("Existing demo revision has a different manifest or membership.")


def main() -> None:
    load_local_env()
    store = FalkorSnapshotStore.from_env()
    graph = store._get_client().select_graph(graph_name_for_workspace(WORKSPACE_ID))

    head_rows = graph.query(
        "MATCH (w:Workspace {id: $workspace_id}) RETURN w.head_revision AS head_revision LIMIT 1",
        {"workspace_id": WORKSPACE_ID},
    ).result_set
    already_seeded = bool(head_rows)
    if already_seeded and head_rows[0][0] != REVISION_ID:
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
    verify_existing_seed_records(graph, formulas, revision_hash)
    if already_seeded:
        snapshot = store.load_snapshot(WORKSPACE_ID, REVISION_ID)
        expected_ids = {item[0] for item in ASSERTION_INPUTS}
        actual_ids = {item.id for item in snapshot.assertions}
        if snapshot.knowledge_hash != revision_hash or actual_ids != expected_ids:
            raise RuntimeError("Existing demo snapshot does not match the expected seed.")
        store.close()
        print("Demo workspace is already seeded and verified at rev_001; no changes made.")
        return

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
