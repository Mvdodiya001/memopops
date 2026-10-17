from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bundles import (  # noqa: E402
    atom,
    chain_proved_bundle,
    cloned,
    context_for,
    demo_r1_proved_bundle,
    demo_r2_refuted_bundle,
    implies_query_bundle,
    refuted_not_p_bundle,
)
from proofcheck import check_certificate, check_witness_pair, evaluate_formula, formula_hash  # noqa: E402


def codes(report) -> set[str]:
    return {error.code for error in report.errors}


class HashEnvelopeTests(unittest.TestCase):
    def test_atom_hash_matches_independent_sha256(self) -> None:
        formula = {"op": "atom", "id": "p"}
        envelope = {"formula": {"id": "p", "op": "atom"}, "semantics_version": "boolean-v1"}
        payload = json.dumps(envelope, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()
        digest = hashlib.sha256(payload).hexdigest()
        self.assertEqual(digest, "92512bd5f0b42fa7261dce9261f0693cc1602d21db0ffc7145ece2c566771ba8")
        self.assertEqual(formula_hash(formula), digest)
        self.assertEqual(formula_hash({"id": "p", "op": "atom"}), digest)

    def test_key_order_does_not_change_formula_hash(self) -> None:
        left = {"op": "implies", "args": [atom("p"), atom("q")]}
        right = {"args": [{"id": "p", "op": "atom"}, {"id": "q", "op": "atom"}], "op": "implies"}
        self.assertEqual(formula_hash(left), formula_hash(right))


class CertificateTests(unittest.TestCase):
    def test_shared_implies_formula_proves_itself(self) -> None:
        bundle = implies_query_bundle()
        report = check_certificate(bundle, context_for(bundle))
        self.assertTrue(report.logical_valid, report.to_dict())
        self.assertEqual(report.context_binding, "MATCHED")
        self.assertEqual(report.support_assertion_ids, ("a_rule",))

    def test_chain_proves_r(self) -> None:
        bundle = chain_proved_bundle()
        report = check_certificate(bundle)
        self.assertTrue(report.logical_valid, report.to_dict())
        self.assertEqual(report.context_binding, "UNVERIFIED")
        self.assertIn("Provenance unverified", report.message)
        self.assertEqual(report.support_assertion_ids, ("a_p", "a_pq", "a_qr"))

    def test_not_p_is_refuted(self) -> None:
        report = check_certificate(refuted_not_p_bundle(), context_for(refuted_not_p_bundle()))
        self.assertTrue(report.logical_valid, report.to_dict())
        self.assertEqual(report.context_binding, "MATCHED")
        self.assertEqual(report.support_assertion_ids, ("a_p",))

    def test_demo_revision_one_proves_release(self) -> None:
        bundle = demo_r1_proved_bundle()
        report = check_certificate(bundle, context_for(bundle))
        self.assertTrue(report.logical_valid, report.to_dict())
        self.assertEqual(report.context_binding, "MATCHED")
        self.assertEqual(report.support_assertion_ids, ("as_api_v2", "as_ready_rule", "as_tests_pass"))

    def test_demo_revision_two_refutes_release(self) -> None:
        bundle = demo_r2_refuted_bundle()
        report = check_certificate(bundle, context_for(bundle))
        self.assertTrue(report.logical_valid, report.to_dict())
        self.assertEqual(report.support_assertion_ids, ("as_block_rule", "as_tests_fail"))

    def test_relabeled_workspace_stays_mathematically_valid(self) -> None:
        bundle = cloned(chain_proved_bundle())
        bundle["workspace_id"] = "workspace_other"
        report = check_certificate(bundle)
        self.assertTrue(report.logical_valid, report.to_dict())
        self.assertEqual(report.context_binding, "UNVERIFIED")

    def test_context_revision_mismatch_does_not_erase_valid_math(self) -> None:
        bundle = chain_proved_bundle()
        context = context_for(bundle)
        context["revision_id"] = "rev_other"
        report = check_certificate(bundle, context)
        self.assertTrue(report.logical_valid, report.to_dict())
        self.assertEqual(report.context_binding, "MISMATCH")
        self.assertIn("context_mismatch", codes(report))

    def test_context_embedded_in_bundle_is_not_trusted(self) -> None:
        bundle = chain_proved_bundle()
        bundle["expected_context"] = context_for(cloned(bundle))
        report = check_certificate(bundle)
        self.assertIn("malformed", codes(report))
        self.assertFalse(report.logical_valid)

    def test_parent_order_does_not_change_a_valid_step(self) -> None:
        bundle = cloned(implies_query_bundle())
        bundle["clauses"][5]["parents"] = [5, 4]
        report = check_certificate(bundle, context_for(bundle))
        self.assertTrue(report.logical_valid, report.to_dict())

    def test_wrong_pivot_is_rejected(self) -> None:
        bundle = cloned(implies_query_bundle())
        bundle["clauses"][5]["pivot"] = 1
        report = check_certificate(bundle)
        self.assertFalse(report.logical_valid)
        self.assertIn("wrong_pivot", codes(report))

    def test_forward_parent_is_rejected(self) -> None:
        bundle = cloned(implies_query_bundle())
        bundle["clauses"][5]["parents"] = [4, 7]
        report = check_certificate(bundle)
        self.assertFalse(report.logical_valid)
        self.assertIn("forward_parent", codes(report))

    def test_bad_resolvent_is_rejected(self) -> None:
        bundle = cloned(chain_proved_bundle())
        bundle["clauses"][10]["literals"] = [-4]
        report = check_certificate(bundle)
        self.assertFalse(report.logical_valid)
        self.assertIn("bad_resolvent", codes(report))

    def test_extra_premise_is_rejected(self) -> None:
        bundle = cloned(implies_query_bundle())
        bundle["clauses"].append(
            {"id": 7, "literals": [1], "origin": "premise", "assertion_id": "a_rule"}
        )
        report = check_certificate(bundle)
        self.assertFalse(report.logical_valid)
        self.assertIn("extra_clause", codes(report))

    def test_changed_premise_literal_is_rejected(self) -> None:
        bundle = cloned(chain_proved_bundle())
        bundle["clauses"][6]["literals"] = [-1]
        report = check_certificate(bundle)
        self.assertFalse(report.logical_valid)
        self.assertIn("initial_clause_mismatch", codes(report))

    def test_changed_query_is_rejected(self) -> None:
        bundle = cloned(chain_proved_bundle())
        bundle["query"] = atom("q")
        bundle["query_hash"] = formula_hash(bundle["query"])
        report = check_certificate(bundle)
        self.assertFalse(report.logical_valid)

    def test_missing_premise_root_is_rejected(self) -> None:
        bundle = cloned(chain_proved_bundle())
        del bundle["clauses"][6]
        for index, clause in enumerate(bundle["clauses"], start=1):
            clause["id"] = index
        report = check_certificate(bundle)
        self.assertFalse(report.logical_valid)
        self.assertTrue(codes(report) & {"initial_clause_mismatch", "bad_resolvent", "forward_parent", "missing_empty", "clause_identity"})

    def test_invalid_witness_is_rejected(self) -> None:
        bundle = cloned(demo_r1_proved_bundle())
        bundle["knowledge_witness"] = {"api_v2": False, "release_ready": True, "tests_pass": True}
        report = check_certificate(bundle, context_for(demo_r1_proved_bundle()))
        self.assertFalse(report.logical_valid)
        self.assertIn("witness_invalid", codes(report))

    def test_omitted_witness_atom_is_rejected(self) -> None:
        bundle = cloned(chain_proved_bundle())
        del bundle["knowledge_witness"]["r"]
        report = check_certificate(bundle)
        self.assertFalse(report.logical_valid)
        self.assertIn("witness_invalid", codes(report))

    def test_support_must_match_ancestors(self) -> None:
        bundle = cloned(demo_r1_proved_bundle())
        bundle["support_assertion_ids"] = ["as_api_v2", "as_block_rule", "as_ready_rule", "as_tests_pass"]
        report = check_certificate(bundle)
        self.assertFalse(report.logical_valid)
        self.assertIn("support_mismatch", codes(report))
        self.assertEqual(report.support_assertion_ids, ("as_api_v2", "as_ready_rule", "as_tests_pass"))

    def test_depth_limit(self) -> None:
        formula: dict[str, object] = atom("p")
        for _ in range(16):
            formula = {"op": "not", "arg": formula}
        bundle = cloned(refuted_not_p_bundle())
        bundle["query"] = formula
        report = check_certificate(bundle)
        self.assertFalse(report.logical_valid)
        self.assertIn("limit_exceeded", codes(report))

    def test_undefined_atom_is_rejected(self) -> None:
        bundle = cloned(implies_query_bundle())
        bundle["query"] = {"op": "atom", "id": "NoSuch"}
        report = check_certificate(bundle)
        self.assertFalse(report.logical_valid)
        self.assertTrue(codes(report) & {"undefined_atom", "malformed"})

    def test_context_hash_ignores_a_matching_lie(self) -> None:
        bundle = cloned(chain_proved_bundle())
        context = context_for(bundle)
        bundle["knowledge_hash"] = "0" * 64
        context["knowledge_hash"] = "0" * 64
        report = check_certificate(bundle, context)
        self.assertFalse(report.logical_valid)
        self.assertEqual(report.context_binding, "MISMATCH")
        self.assertIn("hash_mismatch", codes(report))


class UnknownWitnessTests(unittest.TestCase):
    def test_docs_signed_has_two_models(self) -> None:
        formulas = {
            "deployed": atom("api_v2"),
            "tests": atom("tests_pass"),
            "ready": atom("release_ready"),
        }
        assertions = [
            {"id": "as_api_v2", "formula": formulas["deployed"], "evidence_ids": ["ev_api"]},
            {
                "id": "as_block_rule",
                "formula": {
                    "op": "implies",
                    "args": [
                        {"op": "not", "arg": formulas["tests"]},
                        {"op": "not", "arg": formulas["ready"]},
                    ],
                },
                "evidence_ids": ["ev_block"],
            },
            {
                "id": "as_ready_rule",
                "formula": {
                    "op": "implies",
                    "args": [
                        {"op": "and", "args": [formulas["deployed"], formulas["tests"]]},
                        formulas["ready"],
                    ],
                },
                "evidence_ids": ["ev_ready"],
            },
            {"id": "as_tests_pass", "formula": formulas["tests"], "evidence_ids": ["ev_tests"]},
        ]
        base = {"api_v2": True, "docs_signed": True, "release_ready": True, "tests_pass": True}
        negative = dict(base)
        negative["docs_signed"] = False
        report = check_witness_pair(assertions, atom("docs_signed"), base, negative)
        self.assertTrue(report.logical_valid, report.to_dict())
        self.assertEqual(report.context_binding, "UNVERIFIED")
        self.assertIn("Provenance unverified", report.message)

    def test_same_query_value_is_not_unknown(self) -> None:
        assertion = [{"id": "a_p", "formula": atom("p"), "evidence_ids": ["ev_p"]}]
        witness = {"p": True, "d": True}
        report = check_witness_pair(assertion, atom("d"), witness, dict(witness))
        self.assertFalse(report.logical_valid)

    def test_evaluator_rejects_closed_world_default(self) -> None:
        with self.assertRaises(Exception):
            evaluate_formula(atom("p"), {})


class MutationIsolationTests(unittest.TestCase):
    def test_checker_does_not_mutate_input(self) -> None:
        bundle = chain_proved_bundle()
        original = copy.deepcopy(bundle)
        check_certificate(bundle, context_for(bundle))
        self.assertEqual(bundle, original)


if __name__ == "__main__":
    unittest.main()
