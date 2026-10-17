"""Comparison baselines for the acceptance suite.

Naive notes cache a previous answer and do not check revisions. The solver-only
ablation uses the same Boolean classifier without a revision guard or
revision-keyed cache. It is an experimental harness, not a service mode.
"""

from __future__ import annotations

import json
from typing import Any

from memopops.formula import Formula, parse_formula
from memopops.solver import classify


class NaiveNotes:
    def __init__(self) -> None:
        self.notes: list[str] = []
        self.answers: dict[str, str] = {}

    def append_note(self, text: str) -> None:
        self.notes.append(text)

    def cache_answer(self, query_key: str, result: str) -> None:
        self.answers[query_key] = result

    def query(self, query_key: str) -> dict[str, Any]:
        if query_key not in self.answers:
            return {
                "result": "ABSTAIN",
                "labeled_current": False,
                "proof": "absent",
                "revision_guard": "absent",
            }
        return {
            "result": self.answers[query_key],
            "labeled_current": True,
            "proof": "absent",
            "revision_guard": "absent",
        }


class SolverOnlyAblation:
    def __init__(self, formulas: list[Formula], atom_ids: set[str]):
        self.formulas = list(formulas)
        self.atom_ids = set(atom_ids)
        self.cache: dict[str, dict[str, Any]] = {}
        self.invalid_accepted_revisions = 0

    def query(self, formula_json: dict[str, Any]) -> dict[str, Any]:
        key = json.dumps(formula_json, sort_keys=True, separators=(",", ":"))
        cached = self.cache.get(key)
        if cached is not None:
            return {**cached, "from_cache": True, "labeled_current": True}
        formula = parse_formula(formula_json, self.atom_ids)
        evaluation = classify(self.formulas, formula, timeout_ms=3_000)
        stored = {
            "result": evaluation.result.value,
            "from_cache": False,
            "labeled_current": True,
            "proof": "absent",
            "revision_guard": "absent",
        }
        self.cache[key] = stored
        return dict(stored)

    def write_without_guard(self, formulas: list[Formula]) -> None:
        self.formulas = list(formulas)
        self.invalid_accepted_revisions += 1
