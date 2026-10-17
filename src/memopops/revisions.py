"""Pure validation and consistency planning for immutable memory revisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
from typing import Callable
from uuid import uuid4

from memopops.formula import Atom, Binary, Formula, FormulaValidationError, Not, formula_hash, parse_formula
from memopops.solver import QueryStatus, classify
from memopops.store import AssertionRecord, Snapshot, calculate_knowledge_hash

MAX_MUTATIONS = 32
MAX_ACTIVE_ASSERTIONS = 256
MAX_ACTIVE_AST_NODES = 8_192
MAX_EVIDENCE_PER_ASSERTION = 4
MAX_URI_LENGTH = 2_048
MAX_EXCERPT_LENGTH = 2_000
MAX_REASON_LENGTH = 500


class MutationValidationError(ValueError):
    """The mutation batch violates the frozen revision contract."""


class RevisionConflictError(MutationValidationError):
    """The requested parent revision is not the snapshot being edited."""


class CandidateInconsistentError(MutationValidationError):
    """The complete proposed knowledge set is logically inconsistent."""


class CandidateIndeterminateError(RuntimeError):
    """Consistency could not be decided within the solver budget."""


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    id: str
    uri: str
    excerpt: str
    observed_at: str
    content_digest: str


@dataclass(frozen=True, slots=True)
class AddedAssertion:
    record: AssertionRecord
    client_ref: str
    acceptance: str
    evidence: tuple[EvidenceRecord, ...]


@dataclass(frozen=True, slots=True)
class RevisionCandidate:
    parent_revision_id: str
    revision_id: str
    acceptance: str
    reason: str
    removed_assertion_ids: tuple[str, ...]
    assertions: tuple[AssertionRecord, ...]
    added_assertions: tuple[AddedAssertion, ...]
    knowledge_hash: str
    client_refs: dict[str, str]


def _utc_timestamp(value: object) -> str:
    base_timestamp = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?"
    if not isinstance(value, str) or not re.fullmatch(
        rf"{base_timestamp}(?:Z|[+-]\d{{2}}:\d{{2}})", value
    ):
        if isinstance(value, str) and re.fullmatch(base_timestamp, value):
            raise MutationValidationError("evidence observed_at must include a timezone")
        raise MutationValidationError("evidence observed_at must be an RFC3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MutationValidationError("evidence observed_at must be an RFC3339 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MutationValidationError("evidence observed_at must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _formula_node_count(formula: Formula) -> int:
    stack: list[Formula] = [formula]
    count = 0
    while stack:
        node = stack.pop()
        count += 1
        if isinstance(node, Not):
            stack.append(node.arg)
        elif isinstance(node, Binary):
            stack.extend((node.left, node.right))
        elif not isinstance(node, Atom):
            raise TypeError(f"unsupported formula node: {type(node).__name__}")
    return count


def _parse_assertion(
    raw: object,
    atom_ids: frozenset[str],
    acceptance: str,
    id_factory: Callable[[], str],
) -> AddedAssertion:
    if not isinstance(raw, dict) or raw.keys() != {"client_ref", "formula", "evidence"}:
        raise MutationValidationError("assertion requires exactly client_ref, formula, and evidence")
    client_ref = raw["client_ref"]
    if not isinstance(client_ref, str) or not client_ref or len(client_ref) > 64:
        raise MutationValidationError("client_ref must be a nonempty string of at most 64 characters")
    try:
        formula = parse_formula(raw["formula"], atom_ids)
    except FormulaValidationError as exc:
        raise MutationValidationError(str(exc)) from exc

    raw_evidence = raw["evidence"]
    if not isinstance(raw_evidence, list) or not 1 <= len(raw_evidence) <= MAX_EVIDENCE_PER_ASSERTION:
        raise MutationValidationError(
            f"each assertion requires 1 to {MAX_EVIDENCE_PER_ASSERTION} evidence items"
        )
    evidence: list[EvidenceRecord] = []
    for item in raw_evidence:
        if not isinstance(item, dict) or item.keys() != {"uri", "excerpt", "observed_at"}:
            raise MutationValidationError("evidence requires exactly uri, excerpt, and observed_at")
        uri, excerpt = item["uri"], item["excerpt"]
        if not isinstance(uri, str) or not uri.strip() or len(uri) > MAX_URI_LENGTH:
            raise MutationValidationError("evidence uri must be nonempty and at most 2048 characters")
        if not isinstance(excerpt, str) or not excerpt.strip() or len(excerpt) > MAX_EXCERPT_LENGTH:
            raise MutationValidationError("evidence excerpt must be nonempty and at most 2000 characters")
        observed_at = _utc_timestamp(item["observed_at"])
        content_digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
        evidence.append(
            EvidenceRecord(
                id=f"ev_{id_factory()}",
                uri=uri,
                excerpt=excerpt,
                observed_at=observed_at,
                content_digest=content_digest,
            )
        )
    assertion_id = f"as_{id_factory()}"
    record = AssertionRecord(assertion_id, formula, formula_hash(formula))
    return AddedAssertion(record, client_ref, acceptance, tuple(evidence))


def build_revision_candidate(
    snapshot: Snapshot,
    *,
    expected_revision_id: str,
    mutations: object,
    reason: object,
    acceptance: object,
    timeout_ms: int = 3_000,
    id_factory: Callable[[], str] | None = None,
) -> RevisionCandidate:
    """Validate and solve a mutation batch without writing any graph data.

    A later persistence layer must publish this complete candidate atomically
    with an expected-head guard. Callers must check idempotency receipts before
    invoking this function because generated IDs are intentionally fresh.
    """
    if expected_revision_id != snapshot.revision_id:
        raise RevisionConflictError("expected revision does not match the loaded snapshot")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > MAX_REASON_LENGTH:
        raise MutationValidationError("a nonempty reason of at most 500 characters is required")
    if not isinstance(acceptance, str) or acceptance not in {"human_confirmed", "trusted_fixture"}:
        raise MutationValidationError("accepted mutations require human_confirmed or trusted_fixture")
    if not isinstance(mutations, list) or not 1 <= len(mutations) <= MAX_MUTATIONS:
        raise MutationValidationError(f"mutations must contain 1 to {MAX_MUTATIONS} items")

    make_id = id_factory or (lambda: uuid4().hex)
    active = {item.id: item for item in snapshot.assertions}
    active_ids = set(active)
    removed: set[str] = set()
    additions: list[AddedAssertion] = []
    client_refs: dict[str, str] = {}
    mutation_targets: set[str] = set()

    for mutation in mutations:
        if not isinstance(mutation, dict) or not isinstance(mutation.get("op"), str):
            raise MutationValidationError("each mutation must be an object with an op")
        op = mutation["op"]
        if op == "add":
            if mutation.keys() != {"op", "assertion"}:
                raise MutationValidationError("add requires exactly op and assertion")
            added = _parse_assertion(mutation["assertion"], snapshot.atom_ids, acceptance, make_id)
            client_ref = added.client_ref
            if client_ref in client_refs:
                raise MutationValidationError(f"duplicate client_ref: {client_ref}")
            client_refs[client_ref] = added.record.id
            additions.append(added)
            continue

        if op not in {"retract", "replace"}:
            raise MutationValidationError("mutation op must be add, retract, or replace")
        expected_keys = (
            {"op", "target_assertion_id"}
            if op == "retract"
            else {"op", "target_assertion_id", "assertion"}
        )
        if mutation.keys() != expected_keys:
            raise MutationValidationError(f"{op} mutation has unexpected or missing fields")
        target_id = mutation["target_assertion_id"]
        if not isinstance(target_id, str) or target_id not in active_ids:
            raise MutationValidationError("mutation target must belong to the expected revision")
        if target_id in mutation_targets:
            raise MutationValidationError("an assertion cannot be targeted more than once per batch")
        mutation_targets.add(target_id)
        removed.add(target_id)
        if op == "replace":
            added = _parse_assertion(mutation["assertion"], snapshot.atom_ids, acceptance, make_id)
            client_ref = added.client_ref
            if client_ref in client_refs:
                raise MutationValidationError(f"duplicate client_ref: {client_ref}")
            client_refs[client_ref] = added.record.id
            additions.append(added)

    for target_id in removed:
        active.pop(target_id)
    candidate_assertions = tuple(
        sorted((*active.values(), *(item.record for item in additions)), key=lambda item: item.id)
    )
    if len(candidate_assertions) > MAX_ACTIVE_ASSERTIONS:
        raise MutationValidationError(f"candidate exceeds {MAX_ACTIVE_ASSERTIONS} active assertions")
    total_nodes = sum(_formula_node_count(item.formula) for item in candidate_assertions)
    if total_nodes > MAX_ACTIVE_AST_NODES:
        raise MutationValidationError(f"candidate exceeds {MAX_ACTIVE_AST_NODES} active formula nodes")

    if candidate_assertions:
        query_atom = min(snapshot.atom_ids) if snapshot.atom_ids else None
        if query_atom is None:
            raise MutationValidationError("candidate formulas require a registered atom")
        consistency = classify(
            (item.formula for item in candidate_assertions),
            parse_formula({"op": "atom", "id": query_atom}, snapshot.atom_ids),
            timeout_ms=timeout_ms,
        )
        if consistency.result == QueryStatus.INCONSISTENT_MEMORY:
            raise CandidateInconsistentError("candidate revision is inconsistent and cannot be activated")
        if consistency.result == QueryStatus.SOLVER_UNKNOWN:
            raise CandidateIndeterminateError("candidate consistency could not be determined")

    return RevisionCandidate(
        parent_revision_id=snapshot.revision_id,
        revision_id=f"rev_{make_id()}",
        acceptance=acceptance,
        reason=reason.strip(),
        removed_assertion_ids=tuple(sorted(removed)),
        assertions=candidate_assertions,
        added_assertions=tuple(additions),
        knowledge_hash=calculate_knowledge_hash(candidate_assertions),
        client_refs=client_refs,
    )
