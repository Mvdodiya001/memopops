from __future__ import annotations

import itertools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "proofcheck" / "src"))

from proofcheck.encode import definition_clause_literals, reconstruct  # noqa: E402
from proofcheck.formula import parse_formula  # noqa: E402


def reference_eval(formula: dict, assignment: dict[str, bool]) -> bool:
    op = formula["op"]
    if op == "atom":
        return assignment[formula["id"]]
    if op == "not":
        return not reference_eval(formula["arg"], assignment)
    left = reference_eval(formula["args"][0], assignment)
    right = reference_eval(formula["args"][1], assignment)
    if op == "and":
        return left and right
    if op == "or":
        return left or right
    if op == "implies":
        return (not left) or right
    if op == "iff":
        return left is right
    raise AssertionError(op)


def clause_holds(clause: tuple[int, ...], env: dict[int, bool]) -> bool:
    return any(env[literal] if literal > 0 else not env[-literal] for literal in clause)


class TemplateTests(unittest.TestCase):
    def test_local_templates_match_boolean_operators(self) -> None:
        checked = 0
        for left in (False, True):
            for extension in (False, True):
                clauses = definition_clause_literals("not", 2, (1,))
                env = {1: left, 2: extension}
                self.assertEqual(all(clause_holds(clause, env) for clause in clauses), extension is (not left))
                checked += 1
        for op, expected in (
            ("and", lambda left, right: left and right),
            ("or", lambda left, right: left or right),
            ("implies", lambda left, right: (not left) or right),
            ("iff", lambda left, right: left is right),
        ):
            for left, right, extension in itertools.product((False, True), repeat=3):
                clauses = definition_clause_literals(op, 3, (1, 2))
                env = {1: left, 2: right, 3: extension}
                self.assertEqual(
                    all(clause_holds(clause, env) for clause in clauses),
                    extension is expected(left, right),
                    (op, left, right, extension),
                )
                checked += 1
        self.assertEqual(checked, 36)

    def test_identical_operands_drop_tautologies(self) -> None:
        clauses = definition_clause_literals("iff", 2, (1, 1))
        self.assertEqual(clauses, [(1, 2), (-1, 2)])


class ExtensionTests(unittest.TestCase):
    def test_root_assertion_matches_independent_evaluator(self) -> None:
        formula = {
            "op": "implies",
            "args": [
                {"op": "and", "args": [{"op": "atom", "id": "p"}, {"op": "atom", "id": "q"}]},
                {"op": "atom", "id": "r"},
            ],
        }
        query = {"op": "atom", "id": "p"}
        parsed_assertions = [("a_rule", parse_formula(formula))]
        built = reconstruct(parsed_assertions, parse_formula(query), "PROVED")
        definition_ids = [item.variable for item in built.definitions]
        definition_clauses = [clause.literals for clause in built.clauses if clause.origin == "definition"]
        root = next(variable for assertion_id, variable in built.roots if assertion_id == "a_rule")
        checked = 0
        for values in itertools.product((False, True), repeat=3):
            assignment = dict(zip(("p", "q", "r"), values, strict=True))
            wanted = reference_eval(formula, assignment)
            self.assertEqual(self._extends(definition_clauses, definition_ids, built.atom_variables, assignment, root), wanted)
            checked += 1
        self.assertEqual(checked, 8)

    def test_shared_subformula_is_one_definition(self) -> None:
        repeated = {"op": "and", "args": [{"op": "atom", "id": "p"}, {"op": "atom", "id": "q"}]}
        formula = {"op": "implies", "args": [repeated, repeated]}
        built = reconstruct([("a_rule", parse_formula(formula))], parse_formula({"op": "atom", "id": "p"}), "PROVED")
        self.assertEqual(len(built.definitions), 2)
        self.assertEqual(built.roots, (("a_rule", built.definitions[-1].variable),))

    def _extends(self, clauses, definition_ids, atom_variables, assignment, root) -> bool:
        atom_env = {variable: assignment[atom_id] for atom_id, variable in atom_variables}
        for mask in range(1 << len(definition_ids)):
            env = dict(atom_env)
            for index, variable in enumerate(definition_ids):
                env[variable] = bool(mask & (1 << index))
            if env.get(root) is not True:
                continue
            if all(clause_holds(clause, env) for clause in clauses):
                return True
        return False


if __name__ == "__main__":
    unittest.main()
