from __future__ import annotations

import pytest

from memopops.formula import canonical_json, formula_hash, parse_formula
from scripts.seed_demo import ATOM_IDS, ASSERTION_INPUTS, verify_existing_seed_records


class Result:
    def __init__(self, rows):
        self.result_set = rows


class PreflightGraph:
    def __init__(self, *, atoms=None, formulas=None, assertions=None, evidence=None, revision=None):
        self.rows = {
            "MATCH (a:Atom)": atoms or [],
            "MATCH (f:Formula)": formulas or [],
            "MATCH (a:Assertion)": assertions or [],
            "MATCH (e:Evidence)": evidence or [],
            "MATCH (r:Revision": revision or [],
        }

    def query(self, query, params=None):
        for marker, rows in self.rows.items():
            if marker in query:
                return Result(rows)
        raise AssertionError(f"unexpected query: {query}")


def expected_formulas():
    result = []
    for assertion_id, formula_json, uri, excerpt in ASSERTION_INPUTS:
        formula = parse_formula(formula_json, ATOM_IDS)
        digest = formula_hash(formula)
        result.append(
            {
                "assertion_id": assertion_id,
                "formula_hash": digest,
                "canonical_json": canonical_json(formula),
                "evidence_id": f"ev_{assertion_id[3:]}",
                "uri": uri,
                "excerpt": excerpt,
                "content_digest": "digest",
            }
        )
    return result


def test_seed_preflight_accepts_empty_graph():
    verify_existing_seed_records(PreflightGraph(), expected_formulas(), "knowledge-hash")


def test_seed_preflight_refuses_atom_meaning_conflict_before_writes():
    graph = PreflightGraph(atoms=[["api_v2", "API v2", "changed meaning", "release demo-42"]])

    with pytest.raises(RuntimeError, match="different immutable meaning"):
        verify_existing_seed_records(graph, expected_formulas(), "knowledge-hash")


def test_seed_preflight_refuses_revision_manifest_conflict():
    graph = PreflightGraph(revision=[["other-hash", "as_api_v2"]])

    with pytest.raises(RuntimeError, match="different manifest or membership"):
        verify_existing_seed_records(graph, expected_formulas(), "knowledge-hash")


def test_seed_preflight_refuses_formula_hash_content_conflict():
    items = expected_formulas()
    graph = PreflightGraph(formulas=[[items[0]["formula_hash"], "different JSON"]])

    with pytest.raises(RuntimeError, match="canonical contents"):
        verify_existing_seed_records(graph, items, "knowledge-hash")


def test_seed_preflight_refuses_assertion_link_conflict():
    items = expected_formulas()
    graph = PreflightGraph(
        assertions=[[items[0]["assertion_id"], "seed", "trusted_fixture",
                     items[0]["formula_hash"], "wrong-hash"]]
    )

    with pytest.raises(RuntimeError, match="conflicting formula links"):
        verify_existing_seed_records(graph, items, "knowledge-hash")


def test_seed_preflight_refuses_evidence_content_conflict():
    item = expected_formulas()[0]
    graph = PreflightGraph(
        evidence=[[item["evidence_id"], "different URI", item["excerpt"],
                   "2026-10-17T00:00:00Z", item["content_digest"]]]
    )

    with pytest.raises(RuntimeError, match="different immutable contents"):
        verify_existing_seed_records(graph, expected_formulas(), "knowledge-hash")


def test_seed_preflight_refuses_untrusted_existing_assertion():
    item = expected_formulas()[0]
    graph = PreflightGraph(
        assertions=[[item["assertion_id"], "agent-1", "model_proposed",
                     item["formula_hash"], item["formula_hash"]]]
    )

    with pytest.raises(RuntimeError, match="different provenance"):
        verify_existing_seed_records(graph, expected_formulas(), "knowledge-hash")
