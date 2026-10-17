from __future__ import annotations

import pytest
from proofcheck import check_certificate

from memopops.certificates import CertificateBudgetExceeded, generate_certificate
from memopops.formula import formula_hash, parse_formula
from memopops.store import AssertionRecord, Snapshot, calculate_knowledge_hash


def snapshot_for(raw_formula):
    formula = parse_formula(raw_formula, {"p", "q"})
    assertion = AssertionRecord("as_1", formula, formula_hash(formula))
    return Snapshot(
        workspace_id="workspace_1",
        revision_id="rev_1",
        knowledge_hash=calculate_knowledge_hash([assertion]),
        atom_ids=frozenset({"p", "q"}),
        assertions=(assertion,),
    )


def expected_context(snapshot, query):
    return {
        "workspace_id": snapshot.workspace_id,
        "revision_id": snapshot.revision_id,
        "semantics_version": "boolean-v1",
        "knowledge_hash": snapshot.knowledge_hash,
        "query_hash": formula_hash(query),
        "assertions": [
            {
                "id": assertion.id,
                "formula_hash": assertion.formula_hash,
                "evidence_ids": ["ev_1"],
            }
            for assertion in snapshot.assertions
        ],
    }


@pytest.mark.parametrize(
    ("raw_premise", "raw_query", "result", "witness"),
    [
        ({"op": "atom", "id": "p"}, {"op": "atom", "id": "p"}, "PROVED", {"p": True}),
        (
            {"op": "not", "arg": {"op": "atom", "id": "p"}},
            {"op": "atom", "id": "p"},
            "REFUTED",
            {"p": False},
        ),
    ],
)
def test_generated_certificates_pass_independent_context_bound_checker(
    raw_premise, raw_query, result, witness
):
    snapshot = snapshot_for(raw_premise)
    query = parse_formula(raw_query, snapshot.atom_ids)
    bundle = generate_certificate(snapshot, query, result, witness, {"as_1": ["ev_1"]})

    report = check_certificate(bundle, expected_context(snapshot, query))

    assert report.logical_valid
    assert report.context_binding == "MATCHED"
    assert report.support_assertion_ids == ("as_1",)


def test_certificate_budget_exhaustion_does_not_create_a_partial_proof():
    snapshot = snapshot_for({"op": "atom", "id": "p"})
    query = parse_formula({"op": "atom", "id": "p"}, snapshot.atom_ids)
    with pytest.raises(CertificateBudgetExceeded):
        generate_certificate(
            snapshot,
            query,
            "PROVED",
            {"p": True},
            {"as_1": ["ev_1"]},
            max_derived_clauses=0,
        )


def test_incorrect_solver_result_is_rejected_before_search():
    snapshot = snapshot_for({"op": "atom", "id": "p"})
    query = parse_formula({"op": "atom", "id": "q"}, snapshot.atom_ids)
    with pytest.raises(ValueError, match="does not support"):
        generate_certificate(
            snapshot,
            query,
            "PROVED",
            {"p": True, "q": False},
            {"as_1": ["ev_1"]},
        )
