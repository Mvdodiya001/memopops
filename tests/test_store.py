import hashlib
import json

import pytest

from memopops.formula import formula_hash, parse_formula
from memopops.store import (
    AssertionRecord,
    FalkorSnapshotStore,
    IdempotencyConflictError,
    RevisionHeadConflictError,
    SnapshotIntegrityError,
    SnapshotNotFoundError,
    calculate_knowledge_hash,
    graph_name_for_workspace,
)


ATOM_P = {"op": "atom", "id": "p"}
NOT_P = {"op": "not", "arg": ATOM_P}


class Result:
    def __init__(self, rows):
        self.result_set = rows


class FakeGraph:
    def __init__(self, expected_hash, canonical=None, stored_formula_hash=None):
        self.expected_hash = expected_hash
        self.canonical = canonical or json.dumps(ATOM_P, separators=(",", ":"), sort_keys=True)
        self.stored_formula_hash = stored_formula_hash or formula_hash(parse_formula(ATOM_P, {"p"}))
        self.calls = []

    def query(self, query, params=None):
        self.calls.append((query, params))
        if "RETURN r.id AS revision_id" in query:
            return Result([["rev_1", self.expected_hash]])
        if "RETURN atom.id AS atom_id" in query:
            return Result([["p"]])
        if "RETURN a.id AS assertion_id" in query:
            return Result([["as_1", self.canonical, self.stored_formula_hash]])
        raise AssertionError("unexpected graph query")


class FakeClient:
    def __init__(self, graph):
        self.graph = graph
        self.selected = None

    def select_graph(self, name):
        self.selected = name
        return self.graph


def test_graph_name_does_not_embed_external_workspace_identifier() -> None:
    name = graph_name_for_workspace("workspace/private/customer-42")
    assert name.startswith("mempops_")
    assert "customer" not in name
    assert len(name) == len("mempops_") + 40


def test_snapshot_read_loads_all_members_and_checks_hashes() -> None:
    formula = parse_formula(ATOM_P, {"p"})
    assertion = AssertionRecord("as_1", formula, formula_hash(formula))
    knowledge_hash = calculate_knowledge_hash([assertion])
    graph = FakeGraph(knowledge_hash)
    client = FakeClient(graph)

    snapshot = FalkorSnapshotStore(client).load_snapshot("workspace-1", "rev_1")

    assert snapshot.revision_id == "rev_1"
    assert snapshot.atom_ids == frozenset({"p"})
    assert len(snapshot.assertions) == 1
    assert client.selected == graph_name_for_workspace("workspace-1")
    assert len(graph.calls) == 3


@pytest.mark.parametrize(
    "canonical, stored_hash, expected_hash",
    [
        (json.dumps(NOT_P, separators=(",", ":"), sort_keys=True), None, "bad-revision-hash"),
        (json.dumps(ATOM_P, indent=2), None, None),
        (None, "wrong-formula-hash", None),
    ],
)
def test_snapshot_rejects_tampered_or_noncanonical_storage(canonical, stored_hash, expected_hash) -> None:
    formula = parse_formula(ATOM_P, {"p"})
    good_record = AssertionRecord("as_1", formula, formula_hash(formula))
    if expected_hash is None:
        expected_hash = calculate_knowledge_hash([good_record])
    graph = FakeGraph(expected_hash, canonical=canonical, stored_formula_hash=stored_hash)

    with pytest.raises(SnapshotIntegrityError):
        FalkorSnapshotStore(FakeClient(graph)).load_snapshot("workspace-1", "rev_1")


class ReceiptGraph:
    def __init__(self, revision_exists=True):
        self.revision_exists = revision_exists
        self.receipts = {}
        self.write_queries = []
        self.write_params = []

    def query(self, query, params=None):
        params = params or {}
        if "CREATE (q:QueryResult" in query:
            self.write_queries.append(query)
            self.write_params.append(params)
            if not self.revision_exists or params["key"] in self.receipts:
                return Result([])
            self.receipts[params["key"]] = (params["request_hash"], params["result_json"])
            return Result([[params["query_id"]]])
        if "MATCH (receipt:RequestReceipt" in query:
            receipt = self.receipts.get(params["key"])
            return Result([list(receipt)] if receipt else [])
        raise AssertionError("unexpected graph query")


def test_query_result_and_idempotency_receipt_are_one_atomic_write():
    graph = ReceiptGraph()
    store = FalkorSnapshotStore(FakeClient(graph))
    payload = {"result": "UNKNOWN", "query_hash": "abc"}

    first = store.persist_query_result("workspace-1", "rev_1", "reader-1", "request-hash", payload, ["as_1"])
    retry = store.persist_query_result("workspace-1", "rev_1", "reader-1", "request-hash", payload, ["as_1"])

    assert first["query_id"] == retry["query_id"]
    assert first["result"] == retry["result"]
    assert len(graph.write_queries) == 2
    assert "CREATE (receipt:RequestReceipt" in graph.write_queries[0]
    assert "CREATE (q)-[:USES_PREMISE]->(a)" in graph.write_queries[0]
    assert "size(used_assertions) = size($uses_premise_ids)" in graph.write_queries[0]
    assert graph.write_params[0]["uses_premise_ids"] == ["as_1"]
    assert graph.receipts["reader-1"][0] == "request-hash"

    with pytest.raises(IdempotencyConflictError):
        store.persist_query_result("workspace-1", "rev_1", "reader-1", "different-hash", payload, ["as_1"])


def test_query_result_is_not_persisted_for_a_missing_revision():
    graph = ReceiptGraph(revision_exists=False)
    store = FalkorSnapshotStore(FakeClient(graph))

    with pytest.raises(SnapshotNotFoundError):
        store.persist_query_result("workspace-1", "missing", "reader-1", "request-hash", {"result": "UNKNOWN"}, [])


def test_query_receipt_read_reuses_only_the_original_request():
    graph = ReceiptGraph()
    store = FalkorSnapshotStore(FakeClient(graph))
    saved = store.persist_query_result(
        "workspace-1", "rev_1", "reader-1", "request-hash", {"result": "UNKNOWN"}, []
    )

    assert store.get_query_receipt("workspace-1", "reader-1", "request-hash") == saved
    assert store.get_query_receipt("workspace-1", "missing", "request-hash") is None
    with pytest.raises(IdempotencyConflictError):
        store.get_query_receipt("workspace-1", "reader-1", "different-hash")


class QueryReadGraph:
    def __init__(self, workspace_id="workspace-1", result=None):
        self.workspace_id = workspace_id
        self.result = result
        self.params = None

    def query(self, query, params=None):
        assert "MATCH (q:QueryResult" in query
        self.params = params
        if params["workspace_id"] != self.workspace_id or self.result is None:
            return Result([])
        return Result([[json.dumps(self.result)]])


class ImpactGraph:
    def __init__(self, parent="rev_0", changed=None, items=None):
        self.parent = parent
        self.changed = ["as_removed"] if changed is None else changed
        self.items = items or [
            ["query_a", json.dumps({
                "query_hash": "hash-a",
                "result": "PROVED",
                "proof_status": "VERIFIED",
                "support_assertion_ids": ["as_removed"],
                "certificate": {"private": "not exposed"},
            }), ["as_removed"]],
        ]
        self.calls = []

    def query(self, query, params=None):
        params = params or {}
        self.calls.append((query, params))
        assert "MATCH (w:Workspace {id: $workspace_id})" in query
        if "RETURN r.parent_revision_id AS parent_revision_id" in query:
            return Result([[self.parent, self.changed]])
        if "RETURN count(DISTINCT q)" in query:
            return Result([[3]])
        if "RETURN q.id AS query_id" in query:
            return Result(self.items)
        raise AssertionError("unexpected graph query")


def test_revision_impact_is_parent_scoped_historical_and_paginated():
    graph = ImpactGraph()
    store = FalkorSnapshotStore(FakeClient(graph))

    impact = store.get_revision_impact(
        "workspace-1", "rev_1", before_query_id="query_0", limit=1
    )

    assert impact == {
        "workspace_id": "workspace-1",
        "revision_id": "rev_1",
        "parent_revision_id": "rev_0",
        "changed_assertion_ids": ["as_removed"],
        "total_count": 3,
        "items": [{
            "query_id": "query_a",
            "revision_id": "rev_0",
            "query_hash": "hash-a",
            "result": "PROVED",
            "proof_status": "VERIFIED",
            "dependency_basis": "CHECKED_SUPPORT",
            "support_assertion_ids": ["as_removed"],
            "changed_assertion_ids": ["as_removed"],
            "freshness": "HISTORICAL",
        }],
        "next_cursor": "query_a",
    }
    assert len(graph.calls) == 3
    assert all(call[1]["workspace_id"] == "workspace-1" for call in graph.calls)
    assert graph.calls[1][1]["changed_assertion_ids"] == ["as_removed"]
    assert graph.calls[2][1]["before_query_id"] == "query_0"


def test_revision_without_parent_or_removed_assertions_has_no_impact_queries():
    graph = ImpactGraph(parent=None, changed=[])
    result = FalkorSnapshotStore(FakeClient(graph)).get_revision_impact("workspace-1", "rev_1")

    assert result["total_count"] == 0
    assert result["items"] == []
    assert len(graph.calls) == 1


def test_revision_impact_marks_solver_only_dependency_as_conservative():
    graph = ImpactGraph(
        items=[[
            "query_solver",
            json.dumps({
                "query_hash": "hash-solver",
                "result": "UNKNOWN",
                "proof_status": "NOT_REQUESTED",
                "support_assertion_ids": [],
            }),
            ["as_removed"],
        ]]
    )

    result = FalkorSnapshotStore(FakeClient(graph)).get_revision_impact("workspace-1", "rev_1")

    assert result["items"][0]["dependency_basis"] == "FULL_SNAPSHOT"
    assert result["items"][0]["support_assertion_ids"] == []


def test_revision_impact_rejects_missing_revision():
    graph = ImpactGraph()
    graph.query = lambda *_args, **_kwargs: Result([])

    with pytest.raises(SnapshotNotFoundError):
        FalkorSnapshotStore(FakeClient(graph)).get_revision_impact("workspace-1", "missing")


def test_query_result_lookup_is_scoped_to_authorized_workspace():
    expected = {"query_id": "q-1", "result": "PROVED"}
    graph = QueryReadGraph(result=expected)
    store = FalkorSnapshotStore(FakeClient(graph))

    assert store.get_query_result("workspace-1", "q-1") == expected
    assert store.get_query_result("workspace-2", "q-1") is None


class RevisionWriteGraph:
    def __init__(self, head="rev_1"):
        self.head = head
        self.receipts = {}
        self.write_queries = []

    def query(self, query, params=None):
        params = params or {}
        if "RETURN revision.id AS revision_id" in query:
            self.write_queries.append((query, params))
            if self.head != params["expected_revision_id"] or params["key"] in self.receipts:
                return Result([])
            self.head = params["revision_id"]
            self.receipts[params["key"]] = (params["request_hash"], params["result_json"])
            return Result([[self.head]])
        if "RETURN receipt.payload_hash AS payload_hash" in query:
            receipt = self.receipts.get(params["key"])
            return Result([list(receipt)] if receipt else [])
        if "RETURN w.head_revision AS head_revision" in query:
            return Result([[self.head]])
        raise AssertionError("unexpected graph query")


def revision_inputs():
    return (
        {
            "id": "rev_2",
            "knowledge_hash": "hash-2",
            "reason": "Correction",
            "acceptance": "human_confirmed",
            "actor_id": "actor_1",
            "removed_assertion_ids": ["as_old"],
            "client_refs": {"replacement": "as_new"},
            "created_at": "2026-10-17T00:00:00.000000Z",
        },
        [{
            "id": "as_new",
            "canonical_json": '{"id":"q","op":"atom"}',
            "formula_hash": "formula-hash",
            "actor_id": "actor_1",
            "acceptance": "human_confirmed",
            "created_at": "2026-10-17T00:00:00.000000Z",
            "evidence": [{
                "id": "ev_new",
                "uri": "fixture://q",
                "excerpt": "q is supported",
                "observed_at": "2026-10-17T00:00:00.000000Z",
                "content_digest": "digest",
            }],
        }],
        ["as_new"],
    )


def test_revision_and_receipt_are_published_in_one_guarded_graph_query():
    graph = RevisionWriteGraph()
    store = FalkorSnapshotStore(FakeClient(graph))
    revision, additions, assertion_ids = revision_inputs()

    result = store.publish_revision(
        "workspace-1", "rev_1", "writer-1", "request-hash", revision, additions, assertion_ids
    )

    assert result == {
        "status": "COMMITTED",
        "revision_id": "rev_2",
        "parent_revision_id": "rev_1",
        "knowledge_hash": "hash-2",
        "client_refs": {"replacement": "as_new"},
    }
    query, params = graph.write_queries[0]
    assert len(graph.write_queries) == 1
    assert "WHERE w.head_revision = $expected_revision_id" in query
    assert "CREATE (revision:Revision" in query
    assert "CREATE (e:Evidence" in query
    assert "CREATE (receipt:RequestReceipt" in query
    assert params["assertion_ids"] == ["as_new"]
    assert graph.head == "rev_2"


def test_revision_retry_returns_original_receipt_and_rejects_key_reuse():
    graph = RevisionWriteGraph()
    store = FalkorSnapshotStore(FakeClient(graph))
    revision, additions, assertion_ids = revision_inputs()
    first = store.publish_revision(
        "workspace-1", "rev_1", "writer-1", "request-hash", revision, additions, assertion_ids
    )

    retry = store.publish_revision(
        "workspace-1", "rev_1", "writer-1", "request-hash", revision, additions, assertion_ids
    )
    assert retry == first
    assert len(graph.write_queries) == 2
    with pytest.raises(IdempotencyConflictError):
        store.publish_revision(
            "workspace-1", "rev_1", "writer-1", "different-hash", revision, additions, assertion_ids
        )


def test_stale_revision_head_does_not_publish_any_candidate_nodes():
    graph = RevisionWriteGraph(head="rev_2")
    store = FalkorSnapshotStore(FakeClient(graph))
    revision, additions, assertion_ids = revision_inputs()

    with pytest.raises(RevisionHeadConflictError) as error:
        store.publish_revision(
            "workspace-1", "rev_1", "writer-2", "request-hash", revision, additions, assertion_ids
        )

    assert error.value.expected == "rev_1"
    assert error.value.actual == "rev_2"
    assert graph.head == "rev_2"


class ProposalGraph:
    def __init__(self):
        self.receipts = {}
        self.write_queries = []

    def query(self, query, params=None):
        params = params or {}
        if "RETURN proposal.id AS proposal_id" in query:
            self.write_queries.append(query)
            if params["key"] in self.receipts:
                return Result([])
            self.receipts[params["key"]] = (params["request_hash"], params["result_json"])
            return Result([[params["proposal_id"]]])
        if "RETURN receipt.payload_hash AS payload_hash" in query:
            receipt = self.receipts.get(params["key"])
            return Result([list(receipt)] if receipt else [])
        raise AssertionError("unexpected graph query")


def test_quarantined_proposal_and_receipt_are_persisted_without_head_write():
    graph = ProposalGraph()
    store = FalkorSnapshotStore(FakeClient(graph))
    proposal = {
        "id": "proposal_1",
        "acceptance": "human_confirmed",
        "actor_id": "actor_1",
        "request_json": '{"mutations":[]}',
        "created_at": "2026-10-17T00:00:00.000000Z",
    }

    result = store.persist_quarantined_proposal(
        "workspace-1", "rev_1", "writer-1", "request-hash", proposal
    )
    retry = store.persist_quarantined_proposal(
        "workspace-1", "rev_1", "writer-1", "request-hash", proposal
    )

    assert result["status"] == "QUARANTINED"
    assert result["proposal_id"] == "proposal_1"
    assert retry == result
    assert len(graph.write_queries) == 2
    assert "CREATE (proposal:Proposal" in graph.write_queries[0]
    assert "CREATE (receipt:RequestReceipt" in graph.write_queries[0]
    assert "SET w.head_revision" not in graph.write_queries[0]


class MemoryGraph(FakeGraph):
    def __init__(self, expected_hash, evidence_digest):
        super().__init__(expected_hash)
        self.evidence_digest = evidence_digest

    def query(self, query, params=None):
        if "a.actor_id AS actor_id" in query:
            return Result([[
                "as_1",
                "actor_writer",
                "human_confirmed",
                "2026-10-17T00:00:00Z",
                [{
                    "id": "ev_1",
                    "uri": "fixture://p",
                    "excerpt": "P was confirmed.",
                    "observed_at": "2026-10-17T00:00:00Z",
                    "content_digest": self.evidence_digest,
                }],
            ]])
        return super().query(query, params)


def test_memory_read_returns_hash_verified_provenance_and_evidence():
    formula = parse_formula(ATOM_P, {"p"})
    assertion = AssertionRecord("as_1", formula, formula_hash(formula))
    digest = hashlib.sha256(b"P was confirmed.").hexdigest()
    graph = MemoryGraph(calculate_knowledge_hash([assertion]), digest)
    store = FalkorSnapshotStore(FakeClient(graph))

    memory = store.load_memory("workspace-1", "rev_1")

    assert memory["revision_id"] == "rev_1"
    assert memory["assertions"][0]["actor_id"] == "actor_writer"
    assert memory["assertions"][0]["formula"] == ATOM_P
    assert memory["assertions"][0]["evidence"][0]["content_digest"] == digest


def test_memory_read_rejects_tampered_evidence_digest():
    formula = parse_formula(ATOM_P, {"p"})
    assertion = AssertionRecord("as_1", formula, formula_hash(formula))
    graph = MemoryGraph(calculate_knowledge_hash([assertion]), "wrong-digest")

    with pytest.raises(SnapshotIntegrityError, match="evidence digest mismatch"):
        FalkorSnapshotStore(FakeClient(graph)).load_memory("workspace-1", "rev_1")


class RevisionHistoryGraph:
    def __init__(self):
        self.params = None

    def query(self, query, params=None):
        self.params = params
        assert "ORDER BY sequence DESC LIMIT $limit" in query
        return Result([
            ["rev_3", "rev_2", 3, "hash-3", "Correct", "human_confirmed", "actor", "t3"],
            ["rev_2", "rev_1", 2, "hash-2", "Update", "human_confirmed", "actor", "t2"],
        ])


def test_revision_history_is_paged_in_stable_descending_order():
    graph = RevisionHistoryGraph()
    store = FalkorSnapshotStore(FakeClient(graph))

    history = store.list_revisions("workspace-1", before_sequence=4, limit=2)

    assert [item["sequence"] for item in history] == [3, 2]
    assert graph.params == {
        "workspace_id": "workspace-1",
        "before_sequence": 4,
        "limit": 2,
    }
