import json
import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from memopops.api import RequestBodyLimitMiddleware, create_app
from memopops.formula import formula_hash, parse_formula
from memopops.store import (
    AssertionRecord,
    IdempotencyConflictError,
    Snapshot,
    SnapshotIntegrityError,
    RevisionHeadConflictError,
    calculate_knowledge_hash,
)
from memopops.solver import SolverQueueFullError


class FakeStore:
    def __init__(self):
        formula = parse_formula({"op": "atom", "id": "p"}, {"p", "q"})
        assertion = AssertionRecord("as_p", formula, formula_hash(formula))
        self.snapshot = Snapshot(
            workspace_id="demo",
            revision_id="rev_1",
            knowledge_hash=calculate_knowledge_hash([assertion]),
            atom_ids=frozenset({"p", "q"}),
            assertions=(assertion,),
        )
        self.saved = {}
        self.revision_saved = {}
        self.head = "rev_1"
        self.published = []
        self.quarantined = []
        self.ready = True
        self.query_dependencies = {}


    def ping(self):
        return self.ready

    def close(self):
        pass

    def load_snapshot(self, workspace_id, revision_id):
        if workspace_id != "demo" or revision_id != "rev_1":
            from memopops.store import SnapshotNotFoundError

            raise SnapshotNotFoundError(revision_id)
        return self.snapshot

    def load_memory(self, workspace_id, revision_id):
        if workspace_id != "demo" or revision_id != "rev_1":
            from memopops.store import SnapshotNotFoundError

            raise SnapshotNotFoundError(revision_id)
        return {
            "workspace_id": "demo",
            "revision_id": "rev_1",
            "knowledge_hash": self.snapshot.knowledge_hash,
            "atom_ids": ["p", "q"],
            "assertions": [{
                "id": "as_p",
                "formula": {"op": "atom", "id": "p"},
                "formula_hash": self.snapshot.assertions[0].formula_hash,
                "evidence": [{"id": "ev_p"}],
            }],
        }

    def list_revisions(self, workspace_id, *, before_sequence=None, limit=50):
        if workspace_id != "demo":
            return []
        return [{"revision_id": "rev_1", "sequence": 1}]

    def get_revision_impact(
        self, workspace_id, revision_id, *, before_query_id=None, limit=50
    ):
        if workspace_id != "demo" or revision_id != "rev_1":
            from memopops.store import SnapshotNotFoundError

            raise SnapshotNotFoundError(revision_id)
        return {
            "workspace_id": workspace_id,
            "revision_id": revision_id,
            "parent_revision_id": None,
            "changed_assertion_ids": [],
            "total_count": 0,
            "items": [],
            "next_cursor": None,
        }

    def list_quarantined_proposals(self, workspace_id, *, limit=50):
        if workspace_id != "demo":
            return []
        records = []
        for proposal in reversed(self.quarantined[-limit:]):
            records.append({
                "proposal_id": proposal["id"],
                "base_revision_id": proposal["base_revision_id"],
                "reason": proposal["reason"],
                "request_json": proposal["request_json"],
                "created_at": proposal["created_at"],
            })
        return records

    def current_head(self, workspace_id):
        return self.head

    def get_revision_receipt(self, workspace, key, request_hash):
        if key not in self.revision_saved:
            return None
        previous_hash, result = self.revision_saved[key]
        if previous_hash != request_hash:
            raise IdempotencyConflictError(key)
        return result

    def publish_revision(
        self, workspace, expected_revision, key, request_hash, revision, added_assertions, assertion_ids
    ):
        prior = self.get_revision_receipt(workspace, key, request_hash)
        if prior is not None:
            return prior
        if expected_revision != self.head:
            raise RevisionHeadConflictError(expected_revision, self.head)
        result = {
            "status": "COMMITTED",
            "revision_id": revision["id"],
            "parent_revision_id": expected_revision,
            "knowledge_hash": revision["knowledge_hash"],
            "client_refs": revision["client_refs"],
        }
        self.head = revision["id"]
        self.revision_saved[key] = (request_hash, result)
        self.published.append((revision, added_assertions, assertion_ids))
        return result

    def persist_quarantined_proposal(self, workspace, base_revision, key, request_hash, proposal):
        prior = self.get_revision_receipt(workspace, key, request_hash)
        if prior is not None:
            return prior
        result = {
            "status": "QUARANTINED",
            "proposal_id": proposal["id"],
            "base_revision_id": base_revision,
            "reason": "INCONSISTENT_CANDIDATE",
        }
        self.revision_saved[key] = (request_hash, result)
        self.quarantined.append({
            **proposal,
            "base_revision_id": base_revision,
            "reason": "INCONSISTENT_CANDIDATE",
        })
        return result

    def get_query_result(self, workspace, query_id):
        for _, result in self.saved.values():
            if result.get("query_id") == query_id:
                return result
        return None

    def get_query_receipt(self, workspace, key, request_hash):
        if key not in self.saved:
            return None
        previous_hash, result = self.saved[key]
        if previous_hash != request_hash:
            raise IdempotencyConflictError(key)
        return result

    def persist_query_result(
        self, workspace, revision, key, request_hash, payload, uses_premise_ids
    ):
        if key in self.saved:
            previous_hash, result = self.saved[key]
            if previous_hash != request_hash:
                raise IdempotencyConflictError(key)
            return result
        result = {**payload, "query_id": "query_1"}
        self.saved[key] = (request_hash, result)
        self.query_dependencies[key] = list(uses_premise_ids)
        return result


class SyncASGIClient:
    """Synchronous facade over httpx ASGITransport without deprecated TestClient."""

    def __init__(self, app):
        self._app = app

    def request(self, method, path, **kwargs):
        async def send():
            async with AsyncClient(
                transport=ASGITransport(app=self._app), base_url="http://testserver"
            ) as client:
                return await client.request(method, path, **kwargs)

        return asyncio.run(send())

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv(
        "MEMOPOPS_AUTH_TOKENS",
        json.dumps({
            "reader-token": {"workspace_id": "demo", "role": "reader"},
            "writer-token": {"workspace_id": "demo", "role": "writer"},
            "operator-token": {"workspace_id": "demo", "role": "operator"},
        }),
    )
    app = create_app(FakeStore())
    test_client = SyncASGIClient(app)
    yield test_client
    app.state.solver_executor.shutdown()


def request_body(query, key="query-1"):
    return {
        "revision_id": "rev_1",
        "idempotency_key": key,
        "query": query,
        "proof_mode": "solver",
    }


def test_workspace_discovery_is_authenticated_and_scoped_to_principal(client):
    listed = client.get(
        "/api/v1/workspaces", headers={"Authorization": "Bearer reader-token"}
    )
    workspace = client.get(
        "/api/v1/workspaces/demo", headers={"Authorization": "Bearer reader-token"}
    )
    hidden = client.get(
        "/api/v1/workspaces/other", headers={"Authorization": "Bearer reader-token"}
    )

    assert listed.status_code == 200
    assert listed.json() == {"workspaces": [{"workspace_id": "demo", "label": "demo"}]}
    assert workspace.status_code == 200
    assert workspace.json() == {
        "workspace_id": "demo",
        "label": "demo",
        "head_revision_id": "rev_1",
        "role": "reader",
        "capabilities": {"can_write_memory": False},
        "semantics_version": "boolean-v1",
    }
    assert hidden.status_code == 404


def test_workspace_discovery_requires_bearer_authentication(client):
    assert client.get("/api/v1/workspaces").status_code == 401
    assert client.get("/api/v1/workspaces/demo").status_code == 401


def test_workspace_discovery_reports_database_unavailability(client):
    def unavailable(_workspace_id):
        raise ConnectionError("database is offline")

    client._app.state.memory_store.current_head = unavailable
    headers = {"Authorization": "Bearer reader-token"}

    listed = client.get("/api/v1/workspaces", headers=headers)
    details = client.get("/api/v1/workspaces/demo", headers=headers)

    assert listed.status_code == details.status_code == 503
    assert listed.json() == details.json() == {"detail": "Workspace is unavailable"}


def test_workspace_discovery_hides_workspaces_without_a_head(client):
    client._app.state.memory_store.head = None

    listed = client.get("/api/v1/workspaces", headers={"Authorization": "Bearer reader-token"})
    details = client.get("/api/v1/workspaces/demo", headers={"Authorization": "Bearer reader-token"})

    assert listed.status_code == 200
    assert listed.json() == {"workspaces": []}
    assert details.status_code == 404


def revision_body(key="revision-1"):
    return {
        "expected_revision": "rev_1",
        "idempotency_key": key,
        "reason": "Record the passing check",
        "acceptance": "human_confirmed",
        "mutations": [{
            "op": "add",
            "assertion": {
                "client_ref": "passing-check",
                "formula": {"op": "atom", "id": "q"},
                "evidence": [{
                    "uri": "fixture://test/check",
                    "excerpt": "The check passed.",
                    "observed_at": "2026-10-17T10:00:00Z",
                }],
            },
        }],
    }


def test_liveness_is_separate_from_database_readiness(client):
    assert client.get("/api/v1/health/live").status_code == 200
    assert client.get("/api/v1/health/ready").json() == {"status": "ready"}


def test_memory_and_history_reads_are_workspace_scoped(client):
    headers = {"Authorization": "Bearer reader-token"}
    memory = client.get("/api/v1/workspaces/demo/memory", headers=headers)
    history = client.get("/api/v1/workspaces/demo/revisions", headers=headers)

    assert memory.status_code == 200
    assert memory.json()["revision_id"] == "rev_1"
    assert history.status_code == 200
    assert history.json() == {"items": [{"revision_id": "rev_1", "sequence": 1}], "next_cursor": None}
    assert client.get("/api/v1/workspaces/other/memory", headers=headers).status_code == 404
    assert client.get("/api/v1/workspaces/other/revisions", headers=headers).status_code == 404


def test_revision_impact_is_authenticated_and_workspace_scoped(client):
    headers = {"Authorization": "Bearer reader-token"}
    response = client.get(
        "/api/v1/workspaces/demo/impact?revision=rev_1&limit=10",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["total_count"] == 0
    assert client.get(
        "/api/v1/workspaces/demo/impact?revision=rev_1"
    ).status_code == 401
    assert client.get(
        "/api/v1/workspaces/other/impact?revision=rev_1",
        headers=headers,
    ).status_code == 404


def test_query_requires_auth_and_returns_revision_bound_result(client):
    path = "/api/v1/workspaces/demo/queries"
    payload = request_body({"op": "atom", "id": "p"})
    assert client.post(path, json=payload).status_code == 401

    response = client.post(path, json=payload, headers={"Authorization": "Bearer reader-token"})

    assert response.status_code == 200
    assert response.json()["result"] == "PROVED"
    assert response.json()["freshness"] == "CURRENT_AS_OF_READ"
    assert response.json()["proof_status"] == "NOT_REQUESTED"
    assert response.json()["witnesses_verified"] is False


def test_certificate_query_is_independently_checked_and_exportable(client):
    headers = {"Authorization": "Bearer reader-token"}
    payload = request_body({"op": "atom", "id": "p"})
    payload["proof_mode"] = "certificate"

    response = client.post("/api/v1/workspaces/demo/queries", json=payload, headers=headers)

    assert response.status_code == 200
    result = response.json()
    assert result["proof_status"] == "VERIFIED"
    assert result["witnesses_verified"] is True
    assert result["certificate_id"]
    assert result["support_assertion_ids"] == ["as_p"]
    assert "certificate" not in result
    assert client._app.state.memory_store.query_dependencies["query-1"] == ["as_p"]
    exported = client.get(
        f"/api/v1/workspaces/demo/queries/{result['query_id']}/certificate",
        headers=headers,
    )
    assert exported.status_code == 200
    assert exported.json()["knowledge_hash"] == result["knowledge_hash"]


def test_certificate_export_detects_stored_bundle_tampering(client):
    headers = {"Authorization": "Bearer reader-token"}
    payload = request_body({"op": "atom", "id": "p"})
    payload["proof_mode"] = "certificate"
    result = client.post(
        "/api/v1/workspaces/demo/queries", json=payload, headers=headers
    ).json()
    _, stored = client._app.state.memory_store.saved["query-1"]
    stored["certificate_id"] = "0" * 64

    exported = client.get(
        f"/api/v1/workspaces/demo/queries/{result['query_id']}/certificate",
        headers=headers,
    )

    assert exported.status_code == 500
    assert exported.json() == {"detail": "Stored certificate failed integrity verification"}


def test_certificate_is_default_query_mode(client):
    response = client.post(
        "/api/v1/workspaces/demo/queries",
        json={
            "revision_id": "rev_1",
            "idempotency_key": "default-certificate",
            "query": {"op": "atom", "id": "p"},
        },
        headers={"Authorization": "Bearer reader-token"},
    )
    assert response.status_code == 200
    assert response.json()["proof_status"] == "VERIFIED"


def test_solver_mode_uses_all_snapshot_assertions_as_conservative_dependencies(client):
    response = client.post(
        "/api/v1/workspaces/demo/queries",
        json=request_body({"op": "atom", "id": "p"}),
        headers={"Authorization": "Bearer reader-token"},
    )

    assert response.status_code == 200
    assert client._app.state.memory_store.query_dependencies["query-1"] == ["as_p"]


def test_query_rejects_cross_workspace_access_and_unregistered_atoms(client):
    headers = {"Authorization": "Bearer reader-token"}
    assert client.post("/api/v1/workspaces/other/queries", json=request_body({"op": "atom", "id": "p"}), headers=headers).status_code == 404
    response = client.post(
        "/api/v1/workspaces/demo/queries",
        json=request_body({"op": "atom", "id": "typo"}),
        headers=headers,
    )
    assert response.status_code == 422


def test_idempotency_key_is_bound_to_request_content(client):
    headers = {"Authorization": "Bearer reader-token"}
    path = "/api/v1/workspaces/demo/queries"
    assert client.post(path, json=request_body({"op": "atom", "id": "p"}), headers=headers).status_code == 200
    conflict = client.post(path, json=request_body({"op": "atom", "id": "q"}), headers=headers)
    assert conflict.status_code == 409


def test_request_schema_rejects_extra_fields(client):
    payload = request_body({"op": "atom", "id": "p"})
    payload["actor_id"] = "client-controlled"
    response = client.post(
        "/api/v1/workspaces/demo/queries",
        json=payload,
        headers={"Authorization": "Bearer reader-token"},
    )
    assert response.status_code == 422


def test_request_body_is_bounded_before_json_parsing(client):
    response = client.post(
        "/api/v1/workspaces/demo/queries",
        content=b" " * 65_537,
        headers={"Authorization": "Bearer reader-token", "Content-Type": "application/json"},
    )
    assert response.status_code == 413



def test_request_json_nesting_is_bounded_before_parsing(client):
    nested = "{\"op\":\"not\",\"arg\":" * 40
    nested += "{\"op\":\"atom\",\"id\":\"p\"}"
    nested += "}" * 40
    body = (
        '{"revision_id":"rev_1","idempotency_key":"nested",'
        f'"query":{nested},"proof_mode":"solver"}}'
    )
    response = client.post(
        "/api/v1/workspaces/demo/queries",
        content=body,
        headers={"Authorization": "Bearer reader-token", "Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "JSON nesting exceeds 32 levels"


def test_json_depth_scan_ignores_brackets_inside_strings():
    assert RequestBodyLimitMiddleware._exceeds_json_depth(b'{"text":"[[[[[[not nesting]]]]]]"}') is False


def test_snapshot_integrity_failure_is_not_reported_as_database_unavailable(client):
    client._app.state.memory_store.load_snapshot = lambda *_: (_ for _ in ()).throw(
        SnapshotIntegrityError("private integrity detail")
    )
    response = client.post(
        "/api/v1/workspaces/demo/queries",
        json=request_body({"op": "atom", "id": "p"}),
        headers={"Authorization": "Bearer reader-token"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Stored memory failed integrity verification"}
    assert "private integrity detail" not in response.text


def test_database_unavailability_returns_503_without_fallback_memory(client):
    client._app.state.memory_store.load_snapshot = lambda *_: (_ for _ in ()).throw(
        ConnectionError("database is offline")
    )

    response = client.post(
        "/api/v1/workspaces/demo/queries",
        json=request_body({"op": "atom", "id": "p"}),
        headers={"Authorization": "Bearer reader-token"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Memory snapshot is unavailable"}
    assert client._app.state.memory_store.saved == {}


def test_query_that_finishes_after_head_advances_is_historical(client):
    from types import SimpleNamespace

    from memopops.solver import classify

    store = client._app.state.memory_store

    class AdvancingSolver:
        def submit(self, premises, query, *, timeout_ms):
            store.head = "rev_2"
            return SimpleNamespace(
                result=lambda timeout: classify(premises, query, timeout_ms=timeout_ms)
            )

        def shutdown(self):
            pass

    client._app.state.solver_executor.shutdown()
    client._app.state.solver_executor = AdvancingSolver()
    response = client.post(
        "/api/v1/workspaces/demo/queries",
        json=request_body({"op": "atom", "id": "p"}),
        headers={"Authorization": "Bearer reader-token"},
    )

    assert response.status_code == 200
    assert response.json()["revision_id"] == "rev_1"
    assert response.json()["head_revision_observed"] == "rev_2"
    assert response.json()["freshness"] == "HISTORICAL"


def test_query_returns_429_when_solver_queue_is_full(client):
    class FullSolverQueue:
        def submit(self, *_args, **_kwargs):
            raise SolverQueueFullError("full")

        def shutdown(self):
            pass

    client._app.state.solver_executor.shutdown()
    client._app.state.solver_executor = FullSolverQueue()
    response = client.post(
        "/api/v1/workspaces/demo/queries",
        json=request_body({"op": "atom", "id": "p"}),
        headers={"Authorization": "Bearer reader-token"},
    )

    assert response.status_code == 429
    assert response.json() == {"detail": "Solver queue is full"}


def test_idempotent_retry_returns_saved_result_without_using_solver(client):
    headers = {"Authorization": "Bearer reader-token"}
    path = "/api/v1/workspaces/demo/queries"
    payload = request_body({"op": "atom", "id": "p"})
    original = client.post(path, json=payload, headers=headers)
    client._app.state.solver_executor.shutdown()

    class FullSolverQueue:
        def submit(self, *_args, **_kwargs):
            raise SolverQueueFullError("full")

        def shutdown(self):
            pass

    client._app.state.solver_executor = FullSolverQueue()
    retry = client.post(path, json=payload, headers=headers)

    assert retry.status_code == 200
    assert retry.json() == original.json()


def test_persisted_query_result_can_be_read_again_by_workspace_client(client):
    headers = {"Authorization": "Bearer reader-token"}
    created = client.post(
        "/api/v1/workspaces/demo/queries",
        json=request_body({"op": "atom", "id": "p"}),
        headers=headers,
    ).json()

    restored = client.get(
        f"/api/v1/workspaces/demo/queries/{created['query_id']}", headers=headers
    )

    assert restored.status_code == 200
    assert restored.json() == created
    assert client.get(
        "/api/v1/workspaces/other/queries/query_1", headers=headers
    ).status_code == 404
    assert client.get(
        "/api/v1/workspaces/demo/queries/missing", headers=headers
    ).status_code == 404


def test_revision_mutation_requires_writer_and_commits_one_candidate(client):
    path = "/api/v1/workspaces/demo/revisions"
    body = revision_body()
    reader = client.post(path, json=body, headers={"Authorization": "Bearer reader-token"})
    assert reader.status_code == 403
    agent_writer = client.post(path, json=body, headers={"Authorization": "Bearer writer-token"})
    assert agent_writer.status_code == 403

    response = client.post(path, json=body, headers={"Authorization": "Bearer operator-token"})

    assert response.status_code == 201
    assert response.json()["status"] == "COMMITTED"
    assert response.json()["parent_revision_id"] == "rev_1"
    assert response.json()["client_refs"] == {"passing-check": client._app.state.memory_store.published[0][1][0]["id"]}
    revision, additions, assertion_ids = client._app.state.memory_store.published[0]
    assert revision["actor_id"].startswith("actor_")
    assert additions[0]["evidence"][0]["content_digest"]
    assert set(assertion_ids) == {"as_p", additions[0]["id"]}


def test_revision_retry_is_receipt_first_and_wrong_key_reuse_conflicts(client):
    path = "/api/v1/workspaces/demo/revisions"
    headers = {"Authorization": "Bearer operator-token"}
    body = revision_body("once")

    first = client.post(path, json=body, headers=headers)
    retry = client.post(path, json=body, headers=headers)
    changed = revision_body("once")
    changed["reason"] = "Different request"
    conflict = client.post(path, json=changed, headers=headers)

    assert first.status_code == retry.status_code == 201
    assert retry.json() == first.json()
    assert conflict.status_code == 409
    assert len(client._app.state.memory_store.published) == 1


def test_revision_route_rejects_trusted_fixture_from_writer(client):
    body = revision_body()
    body["acceptance"] = "trusted_fixture"
    response = client.post(
        "/api/v1/workspaces/demo/revisions",
        json=body,
        headers={"Authorization": "Bearer writer-token"},
    )
    assert response.status_code == 403


def test_inconsistent_revision_is_quarantined_and_retry_is_receipt_first(client):
    body = revision_body("quarantine-once")
    body["mutations"][0]["assertion"]["formula"] = {
        "op": "not",
        "arg": {"op": "atom", "id": "p"},
    }
    headers = {"Authorization": "Bearer operator-token"}
    path = "/api/v1/workspaces/demo/revisions"

    first = client.post(path, json=body, headers=headers)
    retry = client.post(path, json=body, headers=headers)

    assert first.status_code == retry.status_code == 200
    assert first.json()["status"] == "QUARANTINED"
    assert retry.json() == first.json()
    store = client._app.state.memory_store
    assert store.head == "rev_1"
    assert len(store.published) == 0
    assert len(store.quarantined) == 1


def test_quarantined_proposals_are_listed_with_workspace_scope_and_sanitized_request(client):
    body = revision_body("quarantine-list")
    body["mutations"][0]["assertion"]["formula"] = {
        "op": "not",
        "arg": {"op": "atom", "id": "p"},
    }
    created = client.post(
        "/api/v1/workspaces/demo/revisions",
        json=body,
        headers={"Authorization": "Bearer operator-token"},
    )
    listed = client.get(
        "/api/v1/workspaces/demo/proposals?status=QUARANTINED&limit=10",
        headers={"Authorization": "Bearer reader-token"},
    )
    hidden = client.get(
        "/api/v1/workspaces/other/proposals",
        headers={"Authorization": "Bearer reader-token"},
    )

    assert created.status_code == 200
    assert listed.status_code == 200
    proposals = listed.json()["proposals"]
    assert len(proposals) == 1
    assert proposals[0]["proposal_id"] == created.json()["proposal_id"]
    assert proposals[0]["base_revision_id"] == "rev_1"
    assert proposals[0]["status"] == "QUARANTINED"
    assert proposals[0]["submitted_request"]["reason"] == body["reason"]
    assert proposals[0]["submitted_request"]["mutations"] == body["mutations"]
    assert "actor_id" not in proposals[0]["submitted_request"]
    assert hidden.status_code == 404


def test_proposal_listing_requires_auth_and_bounds_limit(client):
    assert client.get("/api/v1/workspaces/demo/proposals").status_code == 401
    invalid_limit = client.get(
        "/api/v1/workspaces/demo/proposals?limit=51",
        headers={"Authorization": "Bearer reader-token"},
    )
    invalid_status = client.get(
        "/api/v1/workspaces/demo/proposals?status=PENDING_REVIEW",
        headers={"Authorization": "Bearer reader-token"},
    )
    assert invalid_limit.status_code == invalid_status.status_code == 422
