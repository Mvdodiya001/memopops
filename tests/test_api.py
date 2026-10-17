import json
import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from memopops.api import RequestBodyLimitMiddleware, create_app
from memopops.formula import formula_hash, parse_formula
from memopops.store import AssertionRecord, IdempotencyConflictError, Snapshot, calculate_knowledge_hash


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
        self.ready = True


    def ping(self):
        return self.ready

    def close(self):
        pass

    def load_snapshot(self, workspace_id, revision_id):
        if workspace_id != "demo" or revision_id != "rev_1":
            from memopops.store import SnapshotNotFoundError

            raise SnapshotNotFoundError(revision_id)
        return self.snapshot

    def current_head(self, workspace_id):
        return "rev_1"

    def persist_query_result(self, workspace, revision, key, request_hash, payload):
        if key in self.saved:
            previous_hash, result = self.saved[key]
            if previous_hash != request_hash:
                raise IdempotencyConflictError(key)
            return result
        result = {**payload, "query_id": "query_1"}
        self.saved[key] = (request_hash, result)
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
        json.dumps({"reader-token": {"workspace_id": "demo", "role": "reader"}}),
    )
    return SyncASGIClient(create_app(FakeStore()))


def request_body(query, key="query-1"):
    return {
        "revision_id": "rev_1",
        "idempotency_key": key,
        "query": query,
        "proof_mode": "solver",
    }


def test_liveness_is_separate_from_database_readiness(client):
    assert client.get("/api/v1/health/live").status_code == 200
    assert client.get("/api/v1/health/ready").json() == {"status": "ready"}


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
