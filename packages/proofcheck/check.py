"""Validate a resolution certificate without solving it again."""

from __future__ import annotations

from dataclasses import dataclass

from proofcheck.encode import InitialClause, definition_clause_literals, reconstruct
from proofcheck.formula import (
    ATOM_ID,
    CERTIFICATE_VERSION,
    SEMANTICS_VERSION,
    Formula,
    FormulaRejected,
    atoms_of,
    evaluate_formula,
    formula_hash,
    knowledge_hash,
    node_count,
    parse_formula,
    require_id,
)
from proofcheck.limits import (
    MAX_ASSERTIONS,
    MAX_AST_NODES,
    MAX_ATOMS,
    MAX_DERIVED_CLAUSES,
    MAX_INITIAL_CLAUSES,
    MAX_LITERALS_PER_CLAUSE,
    MAX_VARIABLE,
)

BUNDLE_KEYS = frozenset(
    {
        "certificate_version",
        "semantics_version",
        "workspace_id",
        "revision_id",
        "knowledge_hash",
        "query_hash",
        "result",
        "assertions",
        "query",
        "atom_variables",
        "definitions",
        "roots",
        "query_root",
        "knowledge_witness",
        "clauses",
        "empty_clause_id",
        "support_assertion_ids",
    }
)
CONTEXT_KEYS = frozenset(
    {
        "workspace_id",
        "revision_id",
        "semantics_version",
        "knowledge_hash",
        "query_hash",
        "assertions",
    }
)


@dataclass(frozen=True)
class CheckError:
    code: str
    message: str
    step_id: int | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"code": self.code, "message": self.message}
        if self.step_id is not None:
            payload["step_id"] = self.step_id
        return payload


@dataclass(frozen=True)
class CheckReport:
    logical_valid: bool
    context_binding: str
    errors: tuple[CheckError, ...]
    support_assertion_ids: tuple[str, ...]
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "logical_valid": self.logical_valid,
            "context_binding": self.context_binding,
            "errors": [error.to_dict() for error in self.errors],
            "support_assertion_ids": list(self.support_assertion_ids),
            "message": self.message,
        }


def check_certificate(bundle: object, expected_context: object = None) -> CheckReport:
    math: list[CheckError] = []
    context_errors: list[CheckError] = []
    support: tuple[str, ...] = ()
    parsed: _Parsed | None = None
    try:
        parsed = _parse_bundle(bundle, math)
    except FormulaRejected as rejected:
        math.append(CheckError(rejected.code, str(rejected)))
    if parsed is not None:
        support = _verify_math(parsed, math)
    _compare_context(parsed, bundle, expected_context, context_errors)
    binding = _binding(expected_context, context_errors)
    errors = tuple(math + context_errors)
    valid = not math
    return CheckReport(
        logical_valid=valid,
        context_binding=binding,
        errors=errors,
        support_assertion_ids=support,
        message=_message(valid, binding),
    )


def check_witness_pair(
    assertions: object,
    query: object,
    witness_true: object,
    witness_false: object,
) -> CheckReport:
    """Evaluate two total models of K that disagree on Q. This is not a refutation certificate."""
    errors: list[CheckError] = []
    try:
        parsed_assertions = _parse_assertion_list(assertions)
        parsed_query = parse_formula(query)
        _reject_size(parsed_assertions, parsed_query)
        atom_ids = _atom_ids(parsed_assertions, parsed_query)
        true_assignment = _assignment(witness_true, atom_ids, "query_true")
        false_assignment = _assignment(witness_false, atom_ids, "query_false")
        for assertion_id, formula in parsed_assertions:
            if not evaluate_formula(formula, true_assignment):
                errors.append(CheckError("witness_invalid", f"query_true does not satisfy {assertion_id}."))
            if not evaluate_formula(formula, false_assignment):
                errors.append(CheckError("witness_invalid", f"query_false does not satisfy {assertion_id}."))
        if not evaluate_formula(parsed_query, true_assignment):
            errors.append(CheckError("witness_invalid", "query_true does not satisfy the query."))
        if evaluate_formula(parsed_query, false_assignment):
            errors.append(CheckError("witness_invalid", "query_false satisfies the query."))
    except FormulaRejected as rejected:
        errors.append(CheckError(rejected.code, str(rejected)))
    valid = not errors
    message = (
        "Both witnesses satisfy the snapshot and disagree on the query. Provenance unverified."
        if valid
        else "Witness check failed. Provenance unverified."
    )
    return CheckReport(valid, "UNVERIFIED", tuple(errors), (), message)


@dataclass(frozen=True)
class _Clause:
    clause_id: int
    literals: tuple[int, ...]
    origin: str
    definition_variable: int | None
    assertion_id: str | None
    parents: tuple[int, int] | None
    pivot: int | None


@dataclass(frozen=True)
class _Parsed:
    workspace_id: str
    revision_id: str
    knowledge_hash_declared: str
    query_hash_declared: str
    result: str
    assertions: tuple[tuple[str, Formula, tuple[str, ...]], ...]
    query: Formula
    atom_variables: tuple[tuple[str, int], ...]
    definitions: tuple[tuple[int, str, tuple[int, ...], str], ...]
    roots: tuple[tuple[str, int], ...]
    query_root: int
    witness: dict[str, bool]
    clauses: tuple[_Clause, ...]
    empty_clause_id: int
    claimed_support: tuple[str, ...]
    computed_knowledge_hash: str
    computed_query_hash: str


def _parse_bundle(bundle: object, math: list[CheckError]) -> _Parsed | None:
    if not isinstance(bundle, dict):
        raise FormulaRejected("malformed", "Certificate must be a JSON object.")
    extra = set(bundle) - BUNDLE_KEYS
    if extra:
        math.append(CheckError("malformed", "Certificate contains unknown properties."))
    missing = BUNDLE_KEYS - set(bundle)
    if missing:
        math.append(CheckError("malformed", "Certificate is missing required properties."))
        return None
    if bundle.get("certificate_version") != CERTIFICATE_VERSION:
        math.append(CheckError("unsupported_version", "certificate_version must be resolution-v1."))
    if bundle.get("semantics_version") != SEMANTICS_VERSION:
        math.append(CheckError("unsupported_version", "semantics_version must be boolean-v1."))
    result = bundle.get("result")
    if result not in {"PROVED", "REFUTED"}:
        math.append(CheckError("malformed", "Certificate result must be PROVED or REFUTED."))
        return None
    workspace_id = require_id(bundle.get("workspace_id"), "workspace_id")
    revision_id = require_id(bundle.get("revision_id"), "revision_id")
    declared_knowledge = _hash_string(bundle.get("knowledge_hash"), "knowledge_hash")
    declared_query = _hash_string(bundle.get("query_hash"), "query_hash")
    assertions = _parse_assertion_records(bundle.get("assertions"))
    query = parse_formula(bundle.get("query"))
    _reject_size(tuple((item[0], item[1]) for item in assertions), query)
    atom_variables = _parse_atom_variables(bundle.get("atom_variables"))
    definitions = _parse_definitions(bundle.get("definitions"))
    roots = _parse_roots(bundle.get("roots"))
    query_root = _positive_int(bundle.get("query_root"), "query_root")
    witness = _assignment(bundle.get("knowledge_witness"), {atom for atom, _ in atom_variables}, "knowledge_witness")
    clauses = _parse_clauses(bundle.get("clauses"))
    empty_clause_id = _positive_int(bundle.get("empty_clause_id"), "empty_clause_id")
    claimed_support = _string_list(bundle.get("support_assertion_ids"), "support_assertion_ids")
    computed_knowledge = knowledge_hash([(assertion_id, formula_hash(formula)) for assertion_id, formula, _ in assertions])
    computed_query = formula_hash(query)
    return _Parsed(
        workspace_id=workspace_id,
        revision_id=revision_id,
        knowledge_hash_declared=declared_knowledge,
        query_hash_declared=declared_query,
        result=result,
        assertions=assertions,
        query=query,
        atom_variables=atom_variables,
        definitions=definitions,
        roots=roots,
        query_root=query_root,
        witness=witness,
        clauses=clauses,
        empty_clause_id=empty_clause_id,
        claimed_support=claimed_support,
        computed_knowledge_hash=computed_knowledge,
        computed_query_hash=computed_query,
    )


def _verify_math(parsed: _Parsed, math: list[CheckError]) -> tuple[str, ...]:
    if parsed.knowledge_hash_declared != parsed.computed_knowledge_hash:
        math.append(CheckError("hash_mismatch", "knowledge_hash does not match the assertion formulas."))
    if parsed.query_hash_declared != parsed.computed_query_hash:
        math.append(CheckError("hash_mismatch", "query_hash does not match the query formula."))
    _check_atom_map(parsed, math)
    _check_definition_order(parsed, math)
    try:
        expected = reconstruct(
            [(assertion_id, formula) for assertion_id, formula, _ in parsed.assertions],
            parsed.query,
            parsed.result,
        )
    except FormulaRejected as rejected:
        math.append(CheckError(rejected.code, str(rejected)))
        return ()
    _check_reconstruction(parsed, expected, math)
    _check_witness(parsed, math)
    initials_ok = _check_initial_clauses(parsed, expected.clauses, math)
    if not initials_ok:
        return ()
    return _check_resolution(parsed, math)


def _check_atom_map(parsed: _Parsed, math: list[CheckError]) -> None:
    expected_atoms = sorted(_atom_ids(tuple((item[0], item[1]) for item in parsed.assertions), parsed.query))
    actual_atoms = [atom_id for atom_id, _ in parsed.atom_variables]
    actual_variables = [variable for _, variable in parsed.atom_variables]
    if actual_atoms != expected_atoms or actual_variables != list(range(1, len(expected_atoms) + 1)):
        math.append(CheckError("atom_map", "Atom variables must be sorted atom ids assigned 1..n."))
    if len(actual_atoms) != len(set(actual_atoms)):
        math.append(CheckError("duplicate_variable", "Atom variables contain a duplicate atom."))


def _check_definition_order(parsed: _Parsed, math: list[CheckError]) -> None:
    known = {variable for _, variable in parsed.atom_variables}
    seen: set[int] = set()
    for variable, op, operands, _digest in parsed.definitions:
        if variable in known or variable in seen:
            math.append(CheckError("duplicate_variable", f"Definition variable {variable} is duplicated."))
        if op not in {"not", "and", "or", "implies", "iff"}:
            math.append(CheckError("malformed", f"Definition {variable} has an unsupported operator."))
        expected_arity = 1 if op == "not" else 2
        if len(operands) != expected_arity:
            math.append(CheckError("dangling_operand", f"Definition {variable} has the wrong number of operands."))
        for operand in operands:
            if operand not in known:
                math.append(CheckError("dangling_operand", f"Definition {variable} references an undefined operand."))
        seen.add(variable)
        known.add(variable)


def _check_reconstruction(parsed: _Parsed, expected: object, math: list[CheckError]) -> None:
    if parsed.atom_variables != expected.atom_variables:
        math.append(CheckError("atom_map", "Atom map does not match the formulas."))
    if parsed.query_root != expected.query_root:
        math.append(CheckError("definition_mismatch", "query_root does not match the query formula."))
    if parsed.roots != expected.roots:
        math.append(CheckError("definition_mismatch", "Assertion roots do not match the formulas."))
    actual_defs = parsed.definitions
    expected_defs = tuple(
        (item.variable, item.op, item.operands, item.formula_hash) for item in expected.definitions
    )
    if len(actual_defs) != len(expected_defs):
        math.append(CheckError("definition_mismatch", "Definition count does not match the formulas."))
        return
    for actual, wanted in zip(actual_defs, expected_defs, strict=True):
        if actual[:3] != wanted[:3]:
            math.append(CheckError("definition_mismatch", f"Definition {wanted[0]} does not match the formula structure."))
        elif actual[3] != wanted[3]:
            math.append(CheckError("hash_mismatch", f"Definition {wanted[0]} formula_hash does not match its formula."))
        wanted_clauses = definition_clause_literals(wanted[1], wanted[0], wanted[2])
        if not wanted_clauses and actual[:3] == wanted[:3]:
            math.append(CheckError("definition_mismatch", f"Definition {wanted[0]} produced no clauses."))


def _check_witness(parsed: _Parsed, math: list[CheckError]) -> None:
    expected_atoms = {atom_id for atom_id, _ in parsed.atom_variables}
    if set(parsed.witness) != expected_atoms:
        math.append(CheckError("witness_invalid", "Knowledge witness must assign exactly the snapshot atoms."))
        return
    try:
        for assertion_id, formula, _evidence in parsed.assertions:
            if not evaluate_formula(formula, parsed.witness):
                math.append(CheckError("witness_invalid", f"Knowledge witness does not satisfy {assertion_id}."))
        query_value = evaluate_formula(parsed.query, parsed.witness)
    except FormulaRejected as rejected:
        math.append(CheckError(rejected.code, str(rejected)))
        return
    if parsed.result == "PROVED" and not query_value:
        math.append(CheckError("witness_invalid", "Knowledge witness does not satisfy a PROVED query."))
    if parsed.result == "REFUTED" and query_value:
        math.append(CheckError("witness_invalid", "Knowledge witness satisfies a REFUTED query."))


def _check_initial_clauses(
    parsed: _Parsed,
    expected: tuple[InitialClause, ...],
    math: list[CheckError],
) -> bool:
    if len(expected) > MAX_INITIAL_CLAUSES:
        math.append(CheckError("limit_exceeded", "Initial clause list exceeds the certificate bound."))
        return False
    if len(parsed.clauses) < len(expected):
        math.append(CheckError("initial_clause_mismatch", "Certificate is missing initial clauses."))
        return False
    for index, wanted in enumerate(expected, start=1):
        actual = parsed.clauses[index - 1]
        if actual.origin != wanted.origin or actual.literals != wanted.literals:
            math.append(CheckError("initial_clause_mismatch", f"Initial clause {index} does not match the formulas.", index))
            return False
        if wanted.origin == "definition" and actual.definition_variable != wanted.definition_variable:
            math.append(CheckError("initial_clause_mismatch", f"Initial clause {index} has the wrong definition.", index))
            return False
        if wanted.origin == "premise" and actual.assertion_id != wanted.assertion_id:
            math.append(CheckError("initial_clause_mismatch", f"Initial clause {index} has the wrong assertion.", index))
            return False
        if wanted.origin == "query_assumption" and (actual.assertion_id or actual.definition_variable or actual.parents):
            math.append(CheckError("initial_clause_mismatch", f"Query assumption {index} carries extra provenance.", index))
            return False
    derived = parsed.clauses[len(expected) :]
    if len(derived) > MAX_DERIVED_CLAUSES:
        math.append(CheckError("limit_exceeded", "Derived clause list exceeds the certificate bound."))
        return False
    if any(clause.origin != "resolution" for clause in derived):
        math.append(CheckError("extra_clause", "A non-resolution clause appears after the initial list."))
        return False
    return True


def _check_resolution(parsed: _Parsed, math: list[CheckError]) -> tuple[str, ...]:
    by_id = {clause.clause_id: clause for clause in parsed.clauses}
    for clause in parsed.clauses:
        if clause.origin != "resolution":
            continue
        if clause.parents is None or clause.pivot is None:
            math.append(CheckError("bad_resolvent", f"Clause {clause.clause_id} is missing resolution data.", clause.clause_id))
            continue
        left_id, right_id = clause.parents
        if left_id == right_id or left_id >= clause.clause_id or right_id >= clause.clause_id:
            math.append(CheckError("forward_parent", f"Clause {clause.clause_id} cites a parent that does not precede it.", clause.clause_id))
            continue
        if left_id not in by_id or right_id not in by_id:
            math.append(CheckError("forward_parent", f"Clause {clause.clause_id} cites a missing parent.", clause.clause_id))
            continue
        _check_resolvent(by_id[left_id].literals, by_id[right_id].literals, clause, math)
    empty = [clause for clause in parsed.clauses if not clause.literals]
    if len(empty) != 1 or empty[0].clause_id != parsed.empty_clause_id or empty[0].origin != "resolution":
        math.append(CheckError("missing_empty", "Certificate must derive exactly one empty clause at empty_clause_id."))
        return ()
    return _support(parsed, by_id, math)


def _check_resolvent(
    left: tuple[int, ...],
    right: tuple[int, ...],
    child: _Clause,
    math: list[CheckError],
) -> None:
    left_set = set(left)
    right_set = set(right)
    pairs = sorted({abs(literal) for literal in left_set if -literal in right_set})
    pivot = child.pivot
    assert pivot is not None
    if pivot not in pairs:
        math.append(CheckError("wrong_pivot", f"Clause {child.clause_id} pivot is not a complementary pair.", child.clause_id))
        return
    if len(pairs) != 1:
        math.append(CheckError("extra_complement", f"Clause {child.clause_id} parents have more than one complementary pair.", child.clause_id))
        return
    if pivot in left_set and -pivot in right_set:
        resolvent_set = (left_set - {pivot}) | (right_set - {-pivot})
    else:
        resolvent_set = (left_set - {-pivot}) | (right_set - {pivot})
    resolvent = tuple(sorted(resolvent_set))
    if any(-literal in resolvent for literal in resolvent if literal > 0):
        math.append(CheckError("tautological_resolvent", f"Clause {child.clause_id} resolvent is tautological.", child.clause_id))
        return
    if resolvent != child.literals:
        math.append(CheckError("bad_resolvent", f"Clause {child.clause_id} is not the resolvent of its parents.", child.clause_id))


def _support(parsed: _Parsed, by_id: dict[int, _Clause], math: list[CheckError]) -> tuple[str, ...]:
    seen: set[int] = set()
    stack = [parsed.empty_clause_id]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        if current not in by_id:
            math.append(CheckError("missing_empty", "Empty clause is not in the certificate."))
            return ()
        seen.add(current)
        clause = by_id[current]
        if clause.origin == "resolution" and clause.parents is not None:
            stack.extend(clause.parents)
    computed = tuple(
        sorted({by_id[clause_id].assertion_id for clause_id in seen if by_id[clause_id].origin == "premise"})
    )
    computed_ids = tuple(assertion_id for assertion_id in computed if assertion_id is not None)
    if tuple(sorted(parsed.claimed_support)) != computed_ids or len(parsed.claimed_support) != len(set(parsed.claimed_support)):
        math.append(CheckError("support_mismatch", "support_assertion_ids do not match the empty clause ancestors."))
    return computed_ids


def _compare_context(
    parsed: _Parsed | None,
    bundle: object,
    expected_context: object,
    context_errors: list[CheckError],
) -> None:
    if expected_context is None:
        return
    if not isinstance(expected_context, dict):
        context_errors.append(CheckError("context_mismatch", "Trusted context must be a JSON object."))
        return
    missing = CONTEXT_KEYS - set(expected_context)
    if missing:
        context_errors.append(CheckError("context_mismatch", "Trusted context is missing required properties."))
        return
    if not isinstance(bundle, dict):
        context_errors.append(CheckError("context_mismatch", "Trusted context cannot match a malformed certificate."))
        return
    comparisons = (
        ("workspace_id", parsed.workspace_id if parsed else None),
        ("revision_id", parsed.revision_id if parsed else None),
        ("semantics_version", SEMANTICS_VERSION if parsed else None),
        ("knowledge_hash", parsed.computed_knowledge_hash if parsed else None),
        ("query_hash", parsed.computed_query_hash if parsed else None),
    )
    for key, actual in comparisons:
        if actual is None or expected_context.get(key) != actual or bundle.get(key) != actual:
            context_errors.append(CheckError("context_mismatch", f"Trusted context {key} does not match the snapshot."))
    if parsed is None:
        return
    context_assertions = expected_context.get("assertions")
    if not isinstance(context_assertions, list):
        context_errors.append(CheckError("context_mismatch", "Trusted context assertions must be a list."))
        return
    expected_by_id: dict[str, tuple[str, tuple[str, ...]]] = {}
    for item in context_assertions:
        if not isinstance(item, dict) or set(item) != {"id", "formula_hash", "evidence_ids"}:
            context_errors.append(CheckError("context_mismatch", "Trusted context assertion shape is invalid."))
            return
        try:
            assertion_id = require_id(item.get("id"), "context assertion id")
            digest = _hash_string(item.get("formula_hash"), "context formula_hash")
            evidence_ids = tuple(sorted(_string_list(item.get("evidence_ids"), "context evidence_ids")))
        except FormulaRejected as rejected:
            context_errors.append(CheckError("context_mismatch", str(rejected)))
            return
        if assertion_id in expected_by_id:
            context_errors.append(CheckError("context_mismatch", "Trusted context repeats an assertion id."))
            return
        expected_by_id[assertion_id] = (digest, evidence_ids)
    actual_by_id = {
        assertion_id: (formula_hash(formula), tuple(sorted(evidence_ids)))
        for assertion_id, formula, evidence_ids in parsed.assertions
    }
    if set(expected_by_id) != set(actual_by_id):
        context_errors.append(CheckError("context_mismatch", "Trusted context assertion ids do not match the certificate."))
        return
    for assertion_id, (digest, evidence_ids) in expected_by_id.items():
        actual_digest, actual_evidence = actual_by_id[assertion_id]
        if digest != actual_digest or evidence_ids != actual_evidence:
            context_errors.append(CheckError("context_mismatch", f"Trusted context does not match assertion {assertion_id}."))


def _binding(expected_context: object, context_errors: list[CheckError]) -> str:
    if expected_context is None:
        return "UNVERIFIED"
    if context_errors:
        return "MISMATCH"
    return "MATCHED"


def _message(valid: bool, binding: str) -> str:
    math_text = "Mathematics check passed" if valid else "Certificate is not valid"
    if binding == "UNVERIFIED":
        return f"{math_text}. Provenance unverified. This report covers only the mathematics of the supplied snapshot."
    if binding == "MATCHED":
        return f"{math_text}, and the trusted context matches this snapshot."
    return f"{math_text}, and the trusted context does not match this snapshot."


def _parse_assertion_list(value: object) -> tuple[tuple[str, Formula], ...]:
    records = _parse_assertion_records(value)
    return tuple((assertion_id, formula) for assertion_id, formula, _evidence in records)


def _parse_assertion_records(value: object) -> tuple[tuple[str, Formula, tuple[str, ...]], ...]:
    if not isinstance(value, list):
        raise FormulaRejected("malformed", "assertions must be a list.")
    if len(value) > MAX_ASSERTIONS:
        raise FormulaRejected("limit_exceeded", "Assertion list exceeds the snapshot bound.")
    parsed: list[tuple[str, Formula, tuple[str, ...]]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {"id", "formula", "evidence_ids"}:
            raise FormulaRejected("malformed", "Each assertion requires id, formula, and evidence_ids.")
        assertion_id = require_id(item.get("id"), "assertion id")
        if assertion_id in seen:
            raise FormulaRejected("malformed", f"Duplicate assertion id {assertion_id}.")
        seen.add(assertion_id)
        formula = parse_formula(item.get("formula"))
        evidence_ids = tuple(_string_list(item.get("evidence_ids"), "evidence_ids"))
        parsed.append((assertion_id, formula, evidence_ids))
    parsed.sort(key=lambda item: item[0])
    return tuple(parsed)


def _reject_size(assertions: tuple[tuple[str, Formula], ...], query: Formula) -> None:
    total = node_count(query) + sum(node_count(formula) for _, formula in assertions)
    atoms = _atom_ids(assertions, query)
    if len(assertions) > MAX_ASSERTIONS or len(atoms) > MAX_ATOMS or total > MAX_AST_NODES:
        raise FormulaRejected("limit_exceeded", "Snapshot exceeds an AST bound.")


def _atom_ids(assertions: tuple[tuple[str, Formula], ...], query: Formula) -> set[str]:
    found: set[str] = set(atoms_of(query))
    for _, formula in assertions:
        found.update(atoms_of(formula))
    return found


def _parse_atom_variables(value: object) -> tuple[tuple[str, int], ...]:
    if not isinstance(value, list) or len(value) > MAX_ATOMS:
        raise FormulaRejected("malformed", "atom_variables must be a list.")
    parsed: list[tuple[str, int]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"atom_id", "variable"}:
            raise FormulaRejected("atom_map", "Each atom variable requires atom_id and variable.")
        atom_id = require_id(item.get("atom_id"), "atom_id")
        if ATOM_ID.fullmatch(atom_id) is None:
            raise FormulaRejected("undefined_atom", f"Atom {atom_id} is not canonical.")
        parsed.append((atom_id, _positive_int(item.get("variable"), "atom variable")))
    return tuple(parsed)


def _parse_definitions(value: object) -> tuple[tuple[int, str, tuple[int, ...], str], ...]:
    if not isinstance(value, list):
        raise FormulaRejected("malformed", "definitions must be a list.")
    parsed: list[tuple[int, str, tuple[int, ...], str]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"variable", "op", "operands", "formula_hash"}:
            raise FormulaRejected("malformed", "Each definition requires variable, op, operands, and formula_hash.")
        variable = _positive_int(item.get("variable"), "definition variable")
        op = item.get("op")
        if not isinstance(op, str):
            raise FormulaRejected("malformed", "Definition operator must be a string.")
        operands_value = item.get("operands")
        if not isinstance(operands_value, list) or not 1 <= len(operands_value) <= 2:
            raise FormulaRejected("dangling_operand", "Definition operands are malformed.")
        operands = tuple(_positive_int(operand, "operand") for operand in operands_value)
        parsed.append((variable, op, operands, _hash_string(item.get("formula_hash"), "formula_hash")))
    return tuple(parsed)


def _parse_roots(value: object) -> tuple[tuple[str, int], ...]:
    if not isinstance(value, list):
        raise FormulaRejected("malformed", "roots must be a list.")
    parsed: list[tuple[str, int]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"assertion_id", "variable"}:
            raise FormulaRejected("malformed", "Each root requires assertion_id and variable.")
        parsed.append((require_id(item.get("assertion_id"), "root assertion_id"), _positive_int(item.get("variable"), "root variable")))
    return tuple(parsed)


def _parse_clauses(value: object) -> tuple[_Clause, ...]:
    if not isinstance(value, list) or not value:
        raise FormulaRejected("malformed", "clauses must be a non-empty list.")
    if len(value) > MAX_INITIAL_CLAUSES + MAX_DERIVED_CLAUSES:
        raise FormulaRejected("limit_exceeded", "Clause list exceeds the certificate bound.")
    parsed: list[_Clause] = []
    for expected_id, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise FormulaRejected("malformed", "Each clause must be an object.")
        origin = item.get("origin")
        allowed = _clause_keys(origin)
        if not isinstance(origin, str) or set(item) != allowed:
            raise FormulaRejected("malformed", f"Clause {expected_id} properties do not match its origin.")
        clause_id = _positive_int(item.get("id"), "clause id")
        if clause_id != expected_id:
            raise FormulaRejected("clause_identity", "Clause ids must be contiguous starting at 1.")
        literals = _literals(item.get("literals"), expected_id)
        definition_variable = None
        assertion_id = None
        parents = None
        pivot = None
        if origin == "definition":
            definition_variable = _positive_int(item.get("definition_variable"), "definition_variable")
        elif origin == "premise":
            assertion_id = require_id(item.get("assertion_id"), "clause assertion_id")
        elif origin == "resolution":
            parent_value = item.get("parents")
            if not isinstance(parent_value, list) or len(parent_value) != 2:
                raise FormulaRejected("forward_parent", f"Clause {expected_id} must cite two parents.")
            parents = (
                _positive_int(parent_value[0], "parent"),
                _positive_int(parent_value[1], "parent"),
            )
            pivot = _positive_int(item.get("pivot"), "pivot")
        elif origin != "query_assumption":
            raise FormulaRejected("malformed", f"Clause {expected_id} has an unknown origin.")
        parsed.append(
            _Clause(clause_id, literals, origin, definition_variable, assertion_id, parents, pivot)
        )
    return tuple(parsed)


def _clause_keys(origin: object) -> set[str]:
    if origin == "definition":
        return {"id", "literals", "origin", "definition_variable"}
    if origin == "premise":
        return {"id", "literals", "origin", "assertion_id"}
    if origin == "query_assumption":
        return {"id", "literals", "origin"}
    if origin == "resolution":
        return {"id", "literals", "origin", "parents", "pivot"}
    return set()


def _literals(value: object, clause_id: int) -> tuple[int, ...]:
    if not isinstance(value, list) or len(value) > MAX_LITERALS_PER_CLAUSE:
        raise FormulaRejected("malformed", f"Clause {clause_id} literals are malformed.")
    literals = tuple(_nonzero_int(item, "literal") for item in value)
    if tuple(sorted(set(literals))) != literals:
        raise FormulaRejected("malformed", f"Clause {clause_id} literals must be sorted and duplicate-free.")
    if any(-literal in literals for literal in literals if literal > 0):
        raise FormulaRejected("tautological_resolvent", f"Clause {clause_id} is tautological.")
    return literals


def _assignment(value: object, expected_atoms: set[str], label: str) -> dict[str, bool]:
    if not isinstance(value, dict):
        raise FormulaRejected("witness_invalid", f"{label} must be an object.")
    assignment: dict[str, bool] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise FormulaRejected("witness_invalid", f"{label} keys must be atom ids.")
        if type(item) is not bool:
            raise FormulaRejected("witness_invalid", f"{label} value for {key} must be boolean.")
        assignment[key] = item
    if set(assignment) != expected_atoms:
        raise FormulaRejected("witness_invalid", f"{label} must assign exactly the original atoms.")
    return assignment


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise FormulaRejected("malformed", f"{label} must be a list.")
    return [require_id(item, label) for item in value]


def _hash_string(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise FormulaRejected("hash_mismatch", f"{label} must be a lowercase sha256 hex digest.")
    return value


def _positive_int(value: object, label: str) -> int:
    number = _nonzero_int(value, label)
    if number <= 0 or number > MAX_VARIABLE:
        raise FormulaRejected("limit_exceeded", f"{label} is outside the variable bound.")
    return number


def _nonzero_int(value: object, label: str) -> int:
    if type(value) is not int or value == 0 or abs(value) > MAX_VARIABLE:
        raise FormulaRejected("limit_exceeded", f"{label} is not a bounded nonzero integer.")
    return value
