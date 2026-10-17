"""Bounded, complete-snapshot Boolean classification using an isolated Z3 context."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from enum import StrEnum
from threading import BoundedSemaphore, Lock
from time import monotonic
from typing import Iterable

import z3

from memopops.formula import Atom, Binary, Formula, Not, formula_atoms


class QueryStatus(StrEnum):
    PROVED = "PROVED"
    REFUTED = "REFUTED"
    UNKNOWN = "UNKNOWN"
    INCONSISTENT_MEMORY = "INCONSISTENT_MEMORY"
    SOLVER_UNKNOWN = "SOLVER_UNKNOWN"


@dataclass(frozen=True, slots=True)
class QueryEvaluation:
    result: QueryStatus
    witnesses: dict[str, dict[str, bool] | None]
    reason_unknown: str | None = None
    solver_version: str = z3.get_version_string()
    elapsed_ms: int = 0


def _translate(formula: Formula, variables: dict[str, z3.BoolRef]) -> z3.BoolRef:
    if isinstance(formula, Atom):
        return variables[formula.id]
    if isinstance(formula, Not):
        return z3.Not(_translate(formula.arg, variables))
    if isinstance(formula, Binary):
        left = _translate(formula.left, variables)
        right = _translate(formula.right, variables)
        if formula.op == "and":
            return z3.And(left, right)
        if formula.op == "or":
            return z3.Or(left, right)
        if formula.op == "implies":
            return z3.Implies(left, right)
        if formula.op == "iff":
            return left == right
    raise TypeError(f"unsupported formula node: {type(formula).__name__}")


def _witness(model: z3.ModelRef, atom_ids: Iterable[str], variables: dict[str, z3.BoolRef]) -> dict[str, bool]:
    return {
        atom_id: z3.is_true(model.eval(variables[atom_id], model_completion=True))
        for atom_id in sorted(atom_ids)
    }


def classify(
    snapshot: Iterable[Formula], query: Formula, *, timeout_ms: int = 3_000
) -> QueryEvaluation:
    """Classify query over every accepted formula, never a retrieval subset.

    A fresh context and solver are created for each call. The timeout is a single
    wall-clock budget shared across consistency and both query polarity checks.
    Input nodes must already have passed ``parse_formula``'s structural validation.
    """
    if timeout_ms <= 0:
        raise ValueError("timeout_ms must be positive")

    started = monotonic()
    deadline = started + timeout_ms / 1_000
    premises = tuple(snapshot)
    atom_ids = set().union(*(formula_atoms(item) for item in premises), formula_atoms(query))
    context = z3.Context()
    variables = {atom_id: z3.Bool(atom_id, ctx=context) for atom_id in sorted(atom_ids)}
    solver = z3.Solver(ctx=context)
    solver.add(*(_translate(item, variables) for item in premises))
    budget_exhausted = False

    def check() -> z3.CheckSatResult:
        nonlocal budget_exhausted
        remaining_ms = int((deadline - monotonic()) * 1_000)
        if remaining_ms <= 0:
            budget_exhausted = True
            return z3.unknown
        solver.set(timeout=max(1, remaining_ms))
        return solver.check()

    def unknown_reason() -> str:
        return "wall_budget_exhausted" if budget_exhausted else solver.reason_unknown()

    def result(
        status: QueryStatus,
        *,
        knowledge: dict[str, bool] | None = None,
        query_true: dict[str, bool] | None = None,
        query_false: dict[str, bool] | None = None,
        reason: str | None = None,
    ) -> QueryEvaluation:
        return QueryEvaluation(
            result=status,
            witnesses={
                "knowledge": knowledge,
                "query_true": query_true,
                "query_false": query_false,
            },
            reason_unknown=reason,
            elapsed_ms=max(0, int((monotonic() - started) * 1_000)),
        )

    base = check()
    if base == z3.unsat:
        return result(QueryStatus.INCONSISTENT_MEMORY)
    if base == z3.unknown:
        return result(QueryStatus.SOLVER_UNKNOWN, reason=unknown_reason())
    knowledge_model = solver.model()
    knowledge_witness = _witness(knowledge_model, atom_ids, variables)

    query_expr = _translate(query, variables)
    solver.push()
    solver.add(z3.Not(query_expr))
    false_check = check()
    if false_check == z3.unknown:
        reason = unknown_reason()
        solver.pop()
        return result(QueryStatus.SOLVER_UNKNOWN, knowledge=knowledge_witness, reason=reason)
    false_witness = _witness(solver.model(), atom_ids, variables) if false_check == z3.sat else None
    solver.pop()
    if false_check == z3.unsat:
        return result(QueryStatus.PROVED, knowledge=knowledge_witness, query_true=knowledge_witness)

    solver.push()
    solver.add(query_expr)
    true_check = check()
    if true_check == z3.unknown:
        reason = unknown_reason()
        solver.pop()
        return result(QueryStatus.SOLVER_UNKNOWN, knowledge=knowledge_witness, query_false=false_witness, reason=reason)
    true_witness = _witness(solver.model(), atom_ids, variables) if true_check == z3.sat else None
    solver.pop()
    if true_check == z3.unsat:
        return result(QueryStatus.REFUTED, knowledge=knowledge_witness, query_false=false_witness)
    return result(
        QueryStatus.UNKNOWN,
        knowledge=knowledge_witness,
        query_true=true_witness,
        query_false=false_witness,
    )


class SolverQueueFullError(RuntimeError):
    """Raised when all solver workers and bounded waiting slots are occupied."""


class BoundedSolverExecutor:
    """Limit solver concurrency and queued work per API process."""

    def __init__(self, *, workers: int = 2, queue_capacity: int = 16):
        if workers < 1 or queue_capacity < 0:
            raise ValueError("workers must be positive and queue capacity nonnegative")
        self._executor = ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="memopops-solver"
        )
        self._capacity = BoundedSemaphore(workers + queue_capacity)
        self._lock = Lock()
        self._closed = False

    def submit(
        self, premises: Iterable[Formula], query: Formula, *, timeout_ms: int
    ) -> Future[QueryEvaluation]:
        with self._lock:
            if self._closed:
                raise RuntimeError("solver executor is shut down")
            if not self._capacity.acquire(blocking=False):
                raise SolverQueueFullError("solver queue is full")
            try:
                future = self._executor.submit(
                    classify, tuple(premises), query, timeout_ms=timeout_ms
                )
            except BaseException:
                self._capacity.release()
                raise
        future.add_done_callback(lambda _future: self._capacity.release())
        return future

    def shutdown(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._executor.shutdown(wait=True, cancel_futures=True)
