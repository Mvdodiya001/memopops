from __future__ import annotations

import hashlib

import pytest

from memopops.formula import formula_hash, parse_formula
from memopops.revisions import (
    CandidateIndeterminateError,
    CandidateInconsistentError,
    MutationValidationError,
    RevisionConflictError,
    build_revision_candidate,
)
from memopops.solver import QueryEvaluation, QueryStatus
from memopops.store import AssertionRecord, Snapshot, calculate_knowledge_hash


def atom(atom_id):
    return {"op": "atom", "id": atom_id}


def evidence(excerpt="tests passed"):
    return [{
        "uri": "fixture://test/evidence",
        "excerpt": excerpt,
        "observed_at": "2026-10-17T10:00:00+05:30",
    }]


def make_snapshot():
    formula = parse_formula(atom("p"), {"p", "q"})
    assertion = AssertionRecord("as_p", formula, formula_hash(formula))
    return Snapshot(
        workspace_id="demo",
        revision_id="rev_1",
        knowledge_hash=calculate_knowledge_hash([assertion]),
        atom_ids=frozenset({"p", "q"}),
        assertions=(assertion,),
    )


def test_add_builds_hashed_immutable_records_and_utc_evidence():
    ids = iter(["evidence-1", "assertion-1", "revision-2"])
    candidate = build_revision_candidate(
        make_snapshot(),
        expected_revision_id="rev_1",
        reason="Record the release test outcome",
        acceptance="human_confirmed",
        mutations=[{
            "op": "add",
            "assertion": {"client_ref": "new-fact", "formula": atom("q"), "evidence": evidence()},
        }],
        id_factory=lambda: next(ids),
    )

    added = candidate.added_assertions[0]
    assert added.record.id == "as_assertion-1"
    assert added.evidence[0].id == "ev_evidence-1"
    assert added.evidence[0].observed_at == "2026-10-17T04:30:00.000000Z"
    assert added.evidence[0].content_digest == hashlib.sha256(b"tests passed").hexdigest()
    assert candidate.revision_id == "rev_revision-2"
    assert candidate.parent_revision_id == "rev_1"
    assert candidate.client_refs == {"new-fact": "as_assertion-1"}
    assert candidate.knowledge_hash == calculate_knowledge_hash(candidate.assertions)


def test_replacement_is_atomic_candidate_and_can_retract_old_polarity():
    ids = iter(["evidence-1", "assertion-1", "revision-2"])
    candidate = build_revision_candidate(
        make_snapshot(),
        expected_revision_id="rev_1",
        reason="Correct the test report",
        acceptance="human_confirmed",
        mutations=[{
            "op": "replace",
            "target_assertion_id": "as_p",
            "assertion": {
                "client_ref": "corrected",
                "formula": {"op": "not", "arg": atom("p")},
                "evidence": evidence("tests failed"),
            },
        }],
        id_factory=lambda: next(ids),
    )

    assert candidate.removed_assertion_ids == ("as_p",)
    assert len(candidate.assertions) == 1
    assert candidate.assertions[0].id == "as_assertion-1"


def test_conflicting_addition_is_rejected_without_changing_snapshot():
    original = make_snapshot()
    with pytest.raises(CandidateInconsistentError):
        build_revision_candidate(
            original,
            expected_revision_id="rev_1",
            reason="Test contradictory evidence",
            acceptance="human_confirmed",
            mutations=[{
                "op": "add",
                "assertion": {
                    "client_ref": "negative-p",
                    "formula": {"op": "not", "arg": atom("p")},
                    "evidence": evidence("p is false"),
                },
            }],
        )
    assert original.assertions[0].id == "as_p"


def test_retracting_last_assertion_produces_empty_consistent_snapshot():
    candidate = build_revision_candidate(
        make_snapshot(),
        expected_revision_id="rev_1",
        reason="Withdraw the invalid report",
        acceptance="human_confirmed",
        mutations=[{"op": "retract", "target_assertion_id": "as_p"}],
    )
    assert candidate.assertions == ()
    assert candidate.removed_assertion_ids == ("as_p",)
    assert candidate.knowledge_hash == calculate_knowledge_hash([])


def test_stale_revision_unknown_target_and_duplicate_target_are_rejected():
    common = {"reason": "Correct fact", "acceptance": "human_confirmed"}
    with pytest.raises(RevisionConflictError):
        build_revision_candidate(
            make_snapshot(),
            expected_revision_id="old",
            mutations=[{"op": "retract", "target_assertion_id": "as_p"}],
            **common,
        )
    with pytest.raises(MutationValidationError, match="belong to the expected revision"):
        build_revision_candidate(
            make_snapshot(),
            expected_revision_id="rev_1",
            mutations=[{"op": "retract", "target_assertion_id": "missing"}],
            **common,
        )
    with pytest.raises(MutationValidationError, match="more than once"):
        build_revision_candidate(
            make_snapshot(),
            expected_revision_id="rev_1",
            mutations=[
                {"op": "retract", "target_assertion_id": "as_p"},
                {"op": "retract", "target_assertion_id": "as_p"},
            ],
            **common,
        )


def test_untrusted_acceptance_and_timezone_free_evidence_are_rejected():
    mutation = {
        "op": "add",
        "assertion": {"client_ref": "x", "formula": atom("q"), "evidence": evidence()},
    }
    with pytest.raises(MutationValidationError, match="human_confirmed or trusted_fixture"):
        build_revision_candidate(
            make_snapshot(),
            expected_revision_id="rev_1",
            reason="reason",
            acceptance="model_proposed",
            mutations=[mutation],
        )
    mutation["assertion"]["evidence"] = [{
        "uri": "fixture://x",
        "excerpt": "evidence",
        "observed_at": "2026-10-17T10:00:00",
    }]
    with pytest.raises(MutationValidationError, match="include a timezone"):
        build_revision_candidate(
            make_snapshot(),
            expected_revision_id="rev_1",
            reason="reason",
            acceptance="human_confirmed",
            mutations=[mutation],
        )


def test_non_rfc3339_timestamp_is_rejected():
    mutation = {
        "op": "add",
        "assertion": {
            "client_ref": "timestamp",
            "formula": atom("q"),
            "evidence": [{
                "uri": "fixture://x",
                "excerpt": "evidence",
                "observed_at": "2026-W42-6T10:00:00Z",
            }],
        },
    }
    with pytest.raises(MutationValidationError, match="RFC3339"):
        build_revision_candidate(
            make_snapshot(),
            expected_revision_id="rev_1",
            reason="Validate timestamp",
            acceptance="human_confirmed",
            mutations=[mutation],
        )


def test_solver_unknown_never_activates_candidate(monkeypatch):
    import memopops.revisions as revisions

    monkeypatch.setattr(
        revisions,
        "classify",
        lambda *_args, **_kwargs: QueryEvaluation(
            QueryStatus.SOLVER_UNKNOWN,
            witnesses={"consistent": None, "query_true": None, "query_false": None},
            reason_unknown="budget_exhausted",
        ),
    )
    mutation = {
        "op": "add",
        "assertion": {"client_ref": "new", "formula": atom("q"), "evidence": evidence()},
    }
    with pytest.raises(CandidateIndeterminateError):
        build_revision_candidate(
            make_snapshot(),
            expected_revision_id="rev_1",
            reason="Solver budget test",
            acceptance="human_confirmed",
            mutations=[mutation],
        )


def test_duplicate_client_references_are_rejected():
    mutation = {
        "op": "add",
        "assertion": {"client_ref": "same", "formula": atom("q"), "evidence": evidence()},
    }
    with pytest.raises(MutationValidationError, match="duplicate client_ref"):
        build_revision_candidate(
            make_snapshot(),
            expected_revision_id="rev_1",
            reason="Add two references",
            acceptance="human_confirmed",
            mutations=[mutation, mutation],
        )


def test_candidate_enforces_total_active_ast_node_limit():
    def balanced_or(depth):
        if depth == 0:
            return atom("p")
        return {"op": "or", "args": [balanced_or(depth - 1), balanced_or(depth - 1)]}

    formula = parse_formula(balanced_or(5), {"p"})
    record = AssertionRecord("as_0", formula, formula_hash(formula))
    assertions = tuple(
        AssertionRecord(f"as_{index:03}", formula, record.formula_hash)
        for index in range(130)
    )
    snapshot = Snapshot(
        workspace_id="demo",
        revision_id="rev_big",
        knowledge_hash=calculate_knowledge_hash(assertions),
        atom_ids=frozenset({"p"}),
        assertions=assertions,
    )
    mutation = {
        "op": "add",
        "assertion": {"client_ref": "overflow", "formula": balanced_or(5), "evidence": evidence()},
    }

    with pytest.raises(MutationValidationError, match="active formula nodes"):
        build_revision_candidate(
            snapshot,
            expected_revision_id="rev_big",
            reason="Exercise formula budget",
            acceptance="human_confirmed",
            mutations=[mutation],
        )


def test_candidate_enforces_active_assertion_limit():
    formula = parse_formula(atom("p"), {"p", "q"})
    assertions = tuple(
        AssertionRecord(f"as_{index:03}", formula, formula_hash(formula))
        for index in range(256)
    )
    snapshot = Snapshot(
        workspace_id="demo",
        revision_id="rev_full",
        knowledge_hash=calculate_knowledge_hash(assertions),
        atom_ids=frozenset({"p", "q"}),
        assertions=assertions,
    )
    mutation = {
        "op": "add",
        "assertion": {"client_ref": "overflow", "formula": atom("q"), "evidence": evidence()},
    }

    with pytest.raises(MutationValidationError, match="active assertions"):
        build_revision_candidate(
            snapshot,
            expected_revision_id="rev_full",
            reason="Exercise assertion budget",
            acceptance="human_confirmed",
            mutations=[mutation],
        )
