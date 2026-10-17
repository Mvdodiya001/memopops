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
)


class SnapshotNotFoundError(LookupError):
    """The requested revision is not present in the authorized workspace graph."""


class SnapshotIntegrityError(RuntimeError):
    """Stored graph contents do not match their immutable revision manifest."""


class IdempotencyConflictError(RuntimeError):
    """An idempotency key was previously used with a different request body."""


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

    def persist_query_result(
        self,
        workspace_id: str,
        revision_id: str,
        idempotency_key: str,
        request_hash: str,
        result_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Atomically persist a query result and its retry receipt in one graph write."""
        graph = self._get_client().select_graph(graph_name_for_workspace(workspace_id))
        query_id = str(uuid4())
        result_payload = {**result_payload, "query_id": query_id}
        serialized = json.dumps(
            result_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        )
        created = graph.query(
            "MATCH (r:Revision {id: $revision_id}) "
            "OPTIONAL MATCH (prior:RequestReceipt {key: $key}) "
            "WITH r, prior WHERE r IS NOT NULL AND prior IS NULL "
            "CREATE (q:QueryResult {id: $query_id, workspace_id: $workspace_id, "
            "revision_id: $revision_id, request_hash: $request_hash, result_json: $result_json}) "
            "CREATE (q)-[:AT_REVISION]->(r) "
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
