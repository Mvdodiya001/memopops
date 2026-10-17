"""FalkorDB-backed immutable revision snapshot reads."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from uuid import uuid4
from typing import Any, Callable, Protocol

from memopops.formula import (
    Formula,
    FormulaValidationError,
    SEMANTICS_VERSION,
    canonical_json,
    formula_hash,
    parse_formula,
    formula_to_json,
)


class SnapshotNotFoundError(LookupError):
    """The requested revision is not present in the authorized workspace graph."""


class SnapshotIntegrityError(RuntimeError):
    """Stored graph contents do not match their immutable revision manifest."""


class IdempotencyConflictError(RuntimeError):
    """An idempotency key was previously used with a different request body."""


class RevisionHeadConflictError(RuntimeError):
    """The workspace head changed before an immutable revision could be published."""

    def __init__(self, expected: str, actual: str | None):
        self.expected = expected
        self.actual = actual
        super().__init__(f"expected revision {expected}, found {actual}")


@dataclass(frozen=True, slots=True)
class AssertionRecord:
    id: str
    formula: Formula
    formula_hash: str


@dataclass(frozen=True, slots=True)
class Snapshot:
    workspace_id: str
    revision_id: str
    knowledge_hash: str
    atom_ids: frozenset[str]
    assertions: tuple[AssertionRecord, ...]

    @property
    def formulas(self) -> tuple[Formula, ...]:
        return tuple(assertion.formula for assertion in self.assertions)


class GraphLike(Protocol):
    def query(self, query: str, params: dict[str, Any] | None = None) -> Any: ...


def calculate_knowledge_hash(assertions: tuple[AssertionRecord, ...] | list[AssertionRecord]) -> str:
    """Hash the full sorted revision membership and semantics version."""
    entries = [[item.id, item.formula_hash] for item in sorted(assertions, key=lambda item: item.id)]
    encoded = json.dumps(
        {"semantics_version": SEMANTICS_VERSION, "assertions": entries},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def graph_name_for_workspace(workspace_id: str) -> str:
    """Derive a safe, non-reversible Falkor graph name from a server-authorized ID."""
    digest = hashlib.sha256(workspace_id.encode("utf-8")).hexdigest()
    return f"mempops_{digest[:40]}"


class FalkorSnapshotStore:
    """Reads a complete revision from FalkorDB and verifies every stored hash."""

    def __init__(self, client: Any = None, client_factory: Callable[[], Any] | None = None):
        self._client = client
        self._client_factory = client_factory

    def _get_client(self) -> Any:
        if self._client is None:
            if self._client_factory is None:
                raise RuntimeError("FalkorDB client is not configured")
            self._client = self._client_factory()
        return self._client

    @classmethod
    def from_env(cls) -> "FalkorSnapshotStore":
        """Create the official client from environment configuration; never log secrets."""
        from falkordb import FalkorDB

        host = os.getenv("FALKORDB_HOST", "localhost")
        port = int(os.getenv("FALKORDB_PORT", "6379"))
        username = os.getenv("FALKORDB_USERNAME") or None
        password = os.getenv("FALKORDB_PASSWORD") or None
        ssl = os.getenv("FALKORDB_SSL", "false").strip().lower() in {"1", "true", "yes"}
        def make_client() -> Any:
            return FalkorDB(
                host=host,
                port=port,
                username=username,
                password=password,
                ssl=ssl,
                socket_connect_timeout=3,
                socket_timeout=5,
                client_name="memopops-api",
            )

        return cls(client_factory=make_client)

    def ping(self) -> bool:
        return bool(self._get_client().connection.ping())

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    def current_head(self, workspace_id: str) -> str | None:
        graph = self._get_client().select_graph(graph_name_for_workspace(workspace_id))
        rows = graph.query("MATCH (w:Workspace) RETURN w.head_revision AS head_revision LIMIT 1").result_set
        return rows[0][0] if rows else None

    def get_query_result(self, workspace_id: str, query_id: str) -> dict[str, Any] | None:
        """Read a previously persisted result, scoped to its workspace graph."""
        graph = self._get_client().select_graph(graph_name_for_workspace(workspace_id))
        rows = graph.query(
            "MATCH (q:QueryResult {id: $query_id, workspace_id: $workspace_id}) "
            "RETURN q.result_json AS result_json",
            {"query_id": query_id, "workspace_id": workspace_id},
        ).result_set
        return json.loads(rows[0][0]) if rows else None

    def get_query_receipt(
        self, workspace_id: str, idempotency_key: str, request_hash: str
    ) -> dict[str, Any] | None:
        """Return the prior result for an identical retry, or reject key reuse."""
        graph = self._get_client().select_graph(graph_name_for_workspace(workspace_id))
        rows = graph.query(
            "MATCH (receipt:RequestReceipt {key: $key}) "
            "RETURN receipt.payload_hash AS payload_hash, receipt.result_json AS result_json",
            {"key": idempotency_key},
        ).result_set
        if not rows:
            return None
        stored_hash, stored_result = rows[0]
        if stored_hash != request_hash:
            raise IdempotencyConflictError(idempotency_key)
        return json.loads(stored_result)

    def get_revision_receipt(
        self, workspace_id: str, idempotency_key: str, request_hash: str
    ) -> dict[str, Any] | None:
        """Return a committed revision receipt for an identical retry."""
        return self.get_query_receipt(workspace_id, idempotency_key, request_hash)

    def get_decision_receipt(
        self, workspace_id: str, idempotency_key: str, request_hash: str
    ) -> dict[str, Any] | None:
        """Return a prior decision for an identical actor-scoped retry."""
        return self.get_query_receipt(workspace_id, idempotency_key, request_hash)

    def persist_decision(
        self,
        workspace_id: str,
        expected_revision_id: str,
        query_id: str,
        idempotency_key: str,
        request_hash: str,
        decision: dict[str, Any],
    ) -> dict[str, Any]:
        """Atomically bind a decision receipt to the current revision and its query."""
        graph = self._get_client().select_graph(graph_name_for_workspace(workspace_id))
        result = {
            "decision_id": decision["id"],
            "workspace_id": workspace_id,
            "revision_id": expected_revision_id,
            "query_id": query_id,
            "outcome": decision["outcome"],
            "rationale": decision["rationale"],
            "actor_id": decision["actor_id"],
            "created_at": decision["created_at"],
        }
        result_json = json.dumps(
            result, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        )
        created = graph.query(
            "MATCH (w:Workspace {id: $workspace_id}) "
            "MATCH (r:Revision {id: $revision_id}) "
            "MATCH (q:QueryResult {id: $query_id, workspace_id: $workspace_id, revision_id: $revision_id}) "
            "WHERE w.head_revision = $revision_id "
            "OPTIONAL MATCH (prior:RequestReceipt {key: $key}) "
            "WITH w, r, q, prior WHERE prior IS NULL "
            "CREATE (d:Decision {id: $decision_id, workspace_id: $workspace_id, "
            "revision_id: $revision_id, query_id: $query_id, actor_id: $actor_id, "
            "outcome: $outcome, rationale: $rationale, created_at: $created_at}) "
            "CREATE (d)-[:AT_REVISION]->(r) CREATE (d)-[:BASED_ON]->(q) "
            "CREATE (receipt:RequestReceipt {key: $key, payload_hash: $request_hash, "
            "result_id: $decision_id, result_json: $result_json}) "
            "CREATE (receipt)-[:REFERS_TO]->(d) RETURN d.id AS decision_id",
            {
                "workspace_id": workspace_id,
                "revision_id": expected_revision_id,
                "query_id": query_id,
                "key": idempotency_key,
                "decision_id": decision["id"],
                "actor_id": decision["actor_id"],
                "outcome": decision["outcome"],
                "rationale": decision["rationale"],
                "created_at": decision["created_at"],
                "request_hash": request_hash,
                "result_json": result_json,
            },
        ).result_set
        if created:
            return result

        prior = self.get_decision_receipt(workspace_id, idempotency_key, request_hash)
        if prior is not None:
            return prior
        actual_revision = self.current_head(workspace_id)
        if actual_revision != expected_revision_id:
            raise RevisionHeadConflictError(expected_revision_id, actual_revision)
        if self.get_query_result(workspace_id, query_id) is None:
            raise SnapshotNotFoundError(query_id)
        raise SnapshotNotFoundError(expected_revision_id)

    def publish_revision(
        self,
        workspace_id: str,
        expected_revision_id: str,
        idempotency_key: str,
        request_hash: str,
        revision: dict[str, Any],
        added_assertions: list[dict[str, Any]],
        assertion_ids: list[str],
    ) -> dict[str, Any]:
        """Publish a revision, membership, new evidence and receipt in one graph query.

        FalkorDB executes a graph query as one command. The expected-head predicate
        is part of that same command as all writes, so concurrent stale candidates
        cannot both advance the workspace head.
        """
        graph = self._get_client().select_graph(graph_name_for_workspace(workspace_id))
        result = {
            "status": "COMMITTED",
            "revision_id": revision["id"],
            "parent_revision_id": expected_revision_id,
            "knowledge_hash": revision["knowledge_hash"],
            "client_refs": revision["client_refs"],
        }
        result_json = json.dumps(
            result, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        )
        created = graph.query(
            "MATCH (w:Workspace {id: $workspace_id}) "
            "MATCH (parent:Revision {id: $expected_revision_id}) "
            "WHERE w.head_revision = $expected_revision_id "
            "OPTIONAL MATCH (prior:RequestReceipt {key: $key}) "
            "WITH w, parent, prior WHERE prior IS NULL "
            "CREATE (revision:Revision {id: $revision_id, parent_revision_id: $expected_revision_id, "
            "sequence: w.sequence + 1, knowledge_hash: $knowledge_hash, semantics_version: $semantics_version, "
            "reason: $reason, acceptance: $acceptance, actor_id: $actor_id, "
            "removed_assertion_ids: $removed_assertion_ids, created_at: $created_at}) "
            "FOREACH (item IN $added_assertions | "
            "MERGE (f:Formula {hash: item.formula_hash}) "
            "ON CREATE SET f.canonical_json = item.canonical_json "
            "CREATE (a:Assertion {id: item.id, actor_id: item.actor_id, acceptance: item.acceptance, "
            "formula_hash: item.formula_hash, created_at: item.created_at}) "
            "CREATE (a)-[:ENCODES]->(f) "
            "FOREACH (evidence IN item.evidence | "
            "CREATE (e:Evidence {id: evidence.id, uri: evidence.uri, excerpt: evidence.excerpt, "
            "observed_at: evidence.observed_at, content_digest: evidence.content_digest}) "
            "CREATE (a)-[:SUPPORTED_BY]->(e))) "
            "WITH w, revision "
            "OPTIONAL MATCH (active:Assertion) WHERE active.id IN $assertion_ids "
            "WITH w, revision, collect(active) AS active_assertions "
            "WHERE size(active_assertions) = size($assertion_ids) "
            "FOREACH (active IN active_assertions | CREATE (revision)-[:INCLUDES]->(active)) "
            "SET w.head_revision = revision.id, w.sequence = revision.sequence "
            "CREATE (receipt:RequestReceipt {key: $key, payload_hash: $request_hash, "
            "result_id: revision.id, result_json: $result_json}) "
            "CREATE (receipt)-[:REFERS_TO]->(revision) "
            "RETURN revision.id AS revision_id",
            {
                "workspace_id": workspace_id,
                "expected_revision_id": expected_revision_id,
                "key": idempotency_key,
                "request_hash": request_hash,
                "revision_id": revision["id"],
                "knowledge_hash": revision["knowledge_hash"],
                "semantics_version": SEMANTICS_VERSION,
                "reason": revision["reason"],
                "acceptance": revision["acceptance"],
                "actor_id": revision["actor_id"],
                "removed_assertion_ids": revision["removed_assertion_ids"],
                "created_at": revision["created_at"],
                "added_assertions": added_assertions,
                "assertion_ids": assertion_ids,
                "result_json": result_json,
            },
        ).result_set
        if created:
            return result

        prior = self.get_revision_receipt(workspace_id, idempotency_key, request_hash)
        if prior is not None:
            return prior
        raise RevisionHeadConflictError(expected_revision_id, self.current_head(workspace_id))

    def persist_quarantined_proposal(
        self,
        workspace_id: str,
        base_revision_id: str,
        idempotency_key: str,
        request_hash: str,
        proposal: dict[str, Any],
    ) -> dict[str, Any]:
        """Preserve a validated but inconsistent proposal without activating it."""
        graph = self._get_client().select_graph(graph_name_for_workspace(workspace_id))
        result = {
            "status": "QUARANTINED",
            "proposal_id": proposal["id"],
            "base_revision_id": base_revision_id,
            "reason": "INCONSISTENT_CANDIDATE",
        }
        result_json = json.dumps(
            result, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        )
        created = graph.query(
            "MATCH (base:Revision {id: $base_revision_id}) "
            "OPTIONAL MATCH (prior:RequestReceipt {key: $key}) "
            "WITH base, prior WHERE prior IS NULL "
            "CREATE (proposal:Proposal {id: $proposal_id, workspace_id: $workspace_id, "
            "base_revision_id: $base_revision_id, status: 'QUARANTINED', "
            "reason: 'INCONSISTENT_CANDIDATE', acceptance: $acceptance, actor_id: $actor_id, "
            "request_json: $request_json, created_at: $created_at}) "
            "CREATE (proposal)-[:BASED_ON]->(base) "
            "CREATE (receipt:RequestReceipt {key: $key, payload_hash: $request_hash, "
            "result_id: $proposal_id, result_json: $result_json}) "
            "CREATE (receipt)-[:REFERS_TO]->(proposal) "
            "RETURN proposal.id AS proposal_id",
            {
                "base_revision_id": base_revision_id,
                "key": idempotency_key,
                "proposal_id": proposal["id"],
                "workspace_id": workspace_id,
                "acceptance": proposal["acceptance"],
                "actor_id": proposal["actor_id"],
                "request_json": proposal["request_json"],
                "created_at": proposal["created_at"],
                "request_hash": request_hash,
                "result_json": result_json,
            },
        ).result_set
        if created:
            return result

        prior = self.get_revision_receipt(workspace_id, idempotency_key, request_hash)
        if prior is not None:
            return prior
        raise SnapshotNotFoundError(base_revision_id)

    def list_quarantined_proposals(
        self, workspace_id: str, *, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Read a bounded list of sanitized quarantine records from one workspace graph."""
        if not 1 <= limit <= 50:
            raise ValueError("proposal limit must be between 1 and 50")
        graph = self._get_client().select_graph(graph_name_for_workspace(workspace_id))
        rows = graph.query(
            "MATCH (proposal:Proposal {workspace_id: $workspace_id, status: 'QUARANTINED'}) "
            "RETURN proposal.id AS proposal_id, proposal.base_revision_id AS base_revision_id, "
            "proposal.reason AS reason, proposal.request_json AS request_json, "
            "proposal.created_at AS created_at "
            "ORDER BY proposal.created_at DESC, proposal.id DESC LIMIT $limit",
            {"workspace_id": workspace_id, "limit": limit},
        ).result_set
        return [
            {
                "proposal_id": row[0],
                "base_revision_id": row[1],
                "reason": row[2],
                "request_json": row[3],
                "created_at": row[4],
            }
            for row in rows
        ]

    def persist_query_result(
        self,
        workspace_id: str,
        revision_id: str,
        idempotency_key: str,
        request_hash: str,
        result_payload: dict[str, Any],
        uses_premise_ids: list[str],
    ) -> dict[str, Any]:
        """Atomically persist a query result, its support edges, and retry receipt."""
        graph = self._get_client().select_graph(graph_name_for_workspace(workspace_id))
        query_id = str(uuid4())
        result_payload = {**result_payload, "query_id": query_id}
        serialized = json.dumps(
            result_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        )
        created = graph.query(
            "MATCH (r:Revision {id: $revision_id}) "
            "OPTIONAL MATCH (r)-[:INCLUDES]->(active:Assertion) "
            "WITH r, collect(active) AS active_assertions "
            "WITH r, [a IN active_assertions WHERE a IS NOT NULL AND a.id IN $uses_premise_ids] AS used_assertions "
            "OPTIONAL MATCH (prior:RequestReceipt {key: $key}) "
            "WITH r, used_assertions, prior "
            "WHERE r IS NOT NULL AND prior IS NULL AND size(used_assertions) = size($uses_premise_ids) "
            "CREATE (q:QueryResult {id: $query_id, workspace_id: $workspace_id, "
            "revision_id: $revision_id, request_hash: $request_hash, result_json: $result_json}) "
            "CREATE (q)-[:AT_REVISION]->(r) "
            "FOREACH (a IN used_assertions | CREATE (q)-[:USES_PREMISE]->(a)) "
            "CREATE (receipt:RequestReceipt {key: $key, payload_hash: $request_hash, "
            "result_id: $query_id, result_json: $result_json}) "
            "CREATE (receipt)-[:REFERS_TO]->(q) "
            "RETURN q.id AS query_id",
            {
                "revision_id": revision_id,
                "key": idempotency_key,
                "query_id": query_id,
                "workspace_id": workspace_id,
                "request_hash": request_hash,
                "result_json": serialized,
                "uses_premise_ids": uses_premise_ids,
            },
        ).result_set
        if created:
            return result_payload

        prior_rows = graph.query(
            "MATCH (receipt:RequestReceipt {key: $key}) "
            "RETURN receipt.payload_hash AS payload_hash, receipt.result_json AS result_json",
            {"key": idempotency_key},
        ).result_set
        if not prior_rows:
            raise SnapshotNotFoundError(revision_id)
        stored_hash, stored_result = prior_rows[0]
        if stored_hash != request_hash:
            raise IdempotencyConflictError(idempotency_key)
        return json.loads(stored_result)

    def get_revision_impact(
        self,
        workspace_id: str,
        revision_id: str,
        *,
        before_query_id: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List parent-revision query results that used assertions removed by this revision."""
        graph = self._get_client().select_graph(graph_name_for_workspace(workspace_id))
        revision_rows = graph.query(
            "MATCH (w:Workspace {id: $workspace_id}) "
            "MATCH (r:Revision {id: $revision_id}) "
            "RETURN r.parent_revision_id AS parent_revision_id, "
            "coalesce(r.removed_assertion_ids, []) AS changed_assertion_ids LIMIT 1",
            {"workspace_id": workspace_id, "revision_id": revision_id},
        ).result_set
        if not revision_rows:
            raise SnapshotNotFoundError(revision_id)
        parent_revision_id, raw_changed_ids = revision_rows[0]
        changed_ids = sorted(set(raw_changed_ids or []))
        if parent_revision_id is None or not changed_ids:
            return {
                "workspace_id": workspace_id,
                "revision_id": revision_id,
                "parent_revision_id": parent_revision_id,
                "changed_assertion_ids": changed_ids,
                "total_count": 0,
                "items": [],
                "next_cursor": None,
            }

        params = {
            "workspace_id": workspace_id,
            "parent_revision_id": parent_revision_id,
            "changed_assertion_ids": changed_ids,
        }
        count_rows = graph.query(
            "MATCH (w:Workspace {id: $workspace_id}) "
            "MATCH (r:Revision {id: $parent_revision_id}) "
            "MATCH (q:QueryResult {workspace_id: $workspace_id, revision_id: $parent_revision_id}) "
            "MATCH (q)-[:USES_PREMISE]->(a:Assertion) "
            "WHERE a.id IN $changed_assertion_ids "
            "RETURN count(DISTINCT q) AS total_count",
            params,
        ).result_set
        total_count = int(count_rows[0][0]) if count_rows else 0
        item_rows = graph.query(
            "MATCH (w:Workspace {id: $workspace_id}) "
            "MATCH (r:Revision {id: $parent_revision_id}) "
            "MATCH (q:QueryResult {workspace_id: $workspace_id, revision_id: $parent_revision_id}) "
            "MATCH (q)-[:USES_PREMISE]->(a:Assertion) "
            "WHERE a.id IN $changed_assertion_ids "
            "AND ($before_query_id IS NULL OR q.id > $before_query_id) "
            "RETURN q.id AS query_id, q.result_json AS result_json, "
            "collect(DISTINCT a.id) AS changed_ids "
            "ORDER BY query_id LIMIT $limit",
            {**params, "before_query_id": before_query_id, "limit": limit},
        ).result_set
        items = []
        for query_id, result_json, affected_ids in item_rows:
            payload = json.loads(result_json)
            items.append(
                {
                    "query_id": query_id,
                    "revision_id": parent_revision_id,
                    "query_hash": payload.get("query_hash"),
                    "result": payload.get("result"),
                    "proof_status": payload.get("proof_status"),
                    "dependency_basis": (
                        "CHECKED_SUPPORT"
                        if payload.get("proof_status") == "VERIFIED"
                        else "FULL_SNAPSHOT"
                    ),
                    "support_assertion_ids": payload.get("support_assertion_ids", []),
                    "changed_assertion_ids": sorted(affected_ids or []),
                    "freshness": "HISTORICAL",
                }
            )
        return {
            "workspace_id": workspace_id,
            "revision_id": revision_id,
            "parent_revision_id": parent_revision_id,
            "changed_assertion_ids": changed_ids,
            "total_count": total_count,
            "items": items,
            "next_cursor": items[-1]["query_id"] if len(items) == limit else None,
        }

    def load_snapshot(self, workspace_id: str, revision_id: str) -> Snapshot:
        graph = self._get_client().select_graph(graph_name_for_workspace(workspace_id))
        revision_rows = graph.query(
            "MATCH (r:Revision {id: $revision_id}) "
            "RETURN r.id AS revision_id, r.knowledge_hash AS knowledge_hash",
            {"revision_id": revision_id},
        ).result_set
        if not revision_rows:
            raise SnapshotNotFoundError(revision_id)
        stored_revision_id, expected_hash = revision_rows[0]

        atom_rows = graph.query("MATCH (atom:Atom) RETURN atom.id AS atom_id ORDER BY atom.id").result_set
        atom_ids = frozenset(row[0] for row in atom_rows)
        assertion_rows = graph.query(
            "MATCH (r:Revision {id: $revision_id})-[:INCLUDES]->(a:Assertion)-[:ENCODES]->(f:Formula) "
            "RETURN a.id AS assertion_id, f.canonical_json AS canonical_json, f.hash AS formula_hash "
            "ORDER BY a.id",
            {"revision_id": revision_id},
        ).result_set

        assertions: list[AssertionRecord] = []
        for assertion_id, canonical, stored_formula_hash in assertion_rows:
            try:
                formula = parse_formula(json.loads(canonical), atom_ids)
            except (TypeError, json.JSONDecodeError, FormulaValidationError) as exc:
                raise SnapshotIntegrityError(f"invalid formula stored for assertion {assertion_id}") from exc
            if canonical_json(formula) != canonical:
                raise SnapshotIntegrityError(f"non-canonical formula stored for assertion {assertion_id}")
            computed_formula_hash = formula_hash(formula)
            if computed_formula_hash != stored_formula_hash:
                raise SnapshotIntegrityError(f"formula hash mismatch for assertion {assertion_id}")
            assertions.append(AssertionRecord(assertion_id, formula, computed_formula_hash))

        computed_knowledge_hash = calculate_knowledge_hash(assertions)
        if computed_knowledge_hash != expected_hash:
            raise SnapshotIntegrityError(f"knowledge hash mismatch for revision {revision_id}")
        return Snapshot(
            workspace_id=workspace_id,
            revision_id=stored_revision_id,
            knowledge_hash=computed_knowledge_hash,
            atom_ids=atom_ids,
            assertions=tuple(assertions),
        )

    def load_memory(self, workspace_id: str, revision_id: str) -> dict[str, Any]:
        """Return a hash-verified revision with assertion provenance and evidence."""
        snapshot = self.load_snapshot(workspace_id, revision_id)
        graph = self._get_client().select_graph(graph_name_for_workspace(workspace_id))
        rows = graph.query(
            "MATCH (w:Workspace {id: $workspace_id}) "
            "MATCH (r:Revision {id: $revision_id})-[:INCLUDES]->(a:Assertion)-[:ENCODES]->(f:Formula) "
            "OPTIONAL MATCH (a)-[:SUPPORTED_BY]->(e:Evidence) "
            "RETURN a.id AS assertion_id, a.actor_id AS actor_id, a.acceptance AS acceptance, "
            "a.created_at AS created_at, collect({id:e.id, uri:e.uri, excerpt:e.excerpt, "
            "observed_at:e.observed_at, content_digest:e.content_digest}) AS evidence "
            "ORDER BY assertion_id",
            {"workspace_id": workspace_id, "revision_id": revision_id},
        ).result_set
        assertion_by_id = {item.id: item for item in snapshot.assertions}
        found: dict[str, dict[str, Any]] = {}
        for assertion_id, actor_id, acceptance, created_at, evidence_items in rows:
            assertion = assertion_by_id.get(assertion_id)
            if assertion is None or assertion_id in found:
                raise SnapshotIntegrityError("revision provenance contains an unknown or duplicate assertion")
            if not isinstance(actor_id, str) or not actor_id or not isinstance(acceptance, str) or not acceptance:
                raise SnapshotIntegrityError(f"missing provenance for assertion {assertion_id}")
            if not isinstance(created_at, str) or not created_at:
                raise SnapshotIntegrityError(f"missing creation time for assertion {assertion_id}")
            evidence: list[dict[str, str]] = []
            for item in evidence_items or []:
                if not item or item.get("id") is None:
                    continue
                excerpt = item.get("excerpt")
                digest = item.get("content_digest")
                evidence_fields = {
                    key: item.get(key)
                    for key in ("id", "uri", "observed_at", "content_digest")
                }
                if (
                    not isinstance(excerpt, str)
                    or not excerpt
                    or not isinstance(digest, str)
                    or any(not isinstance(value, str) or not value for value in evidence_fields.values())
                ):
                    raise SnapshotIntegrityError(f"invalid evidence for assertion {assertion_id}")
                if hashlib.sha256(excerpt.encode("utf-8")).hexdigest() != digest:
                    raise SnapshotIntegrityError(f"evidence digest mismatch for assertion {assertion_id}")
                evidence.append({**evidence_fields, "excerpt": excerpt})
            if not evidence:
                raise SnapshotIntegrityError(f"missing evidence for assertion {assertion_id}")
            found[assertion_id] = {
                "id": assertion_id,
                "formula": formula_to_json(assertion.formula),
                "formula_hash": assertion.formula_hash,
                "actor_id": actor_id,
                "acceptance": acceptance,
                "created_at": created_at,
                "evidence": evidence,
            }
        if set(found) != set(assertion_by_id):
            raise SnapshotIntegrityError("revision provenance membership does not match its snapshot")
        return {
            "workspace_id": workspace_id,
            "revision_id": snapshot.revision_id,
            "knowledge_hash": snapshot.knowledge_hash,
            "atom_ids": sorted(snapshot.atom_ids),
            "assertions": [found[key] for key in sorted(found)],
        }

    def list_revisions(
        self, workspace_id: str, *, before_sequence: int | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """List immutable revisions in descending sequence order."""
        graph = self._get_client().select_graph(graph_name_for_workspace(workspace_id))
        rows = graph.query(
            "MATCH (w:Workspace {id: $workspace_id}) MATCH (r:Revision) "
            "WHERE $before_sequence IS NULL OR r.sequence < $before_sequence "
            "RETURN r.id AS revision_id, r.parent_revision_id AS parent_revision_id, "
            "r.sequence AS sequence, r.knowledge_hash AS knowledge_hash, r.reason AS reason, "
            "r.acceptance AS acceptance, r.actor_id AS actor_id, r.created_at AS created_at "
            "ORDER BY sequence DESC LIMIT $limit",
            {"workspace_id": workspace_id, "before_sequence": before_sequence, "limit": limit},
        ).result_set
        return [
            {
                "revision_id": row[0],
                "parent_revision_id": row[1],
                "sequence": row[2],
                "knowledge_hash": row[3],
                "reason": row[4],
                "acceptance": row[5],
                "actor_id": row[6],
                "created_at": row[7],
            }
            for row in rows
        ]
