import json

import pytest

from memopops.formula import formula_hash, parse_formula
from memopops.store import (
    AssertionRecord,
    FalkorSnapshotStore,
    IdempotencyConflictError,
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

    def query(self, query, params=None):
        params = params or {}
        if "CREATE (q:QueryResult" in query:
            self.write_queries.append(query)
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

    first = store.persist_query_result("workspace-1", "rev_1", "reader-1", "request-hash", payload)
    retry = store.persist_query_result("workspace-1", "rev_1", "reader-1", "request-hash", payload)

    assert first["query_id"] == retry["query_id"]
    assert first["result"] == retry["result"]
    assert len(graph.write_queries) == 2
    assert "CREATE (receipt:RequestReceipt" in graph.write_queries[0]

    with pytest.raises(IdempotencyConflictError):
        store.persist_query_result("workspace-1", "rev_1", "reader-1", "different-hash", payload)


def test_query_result_is_not_persisted_for_a_missing_revision():
    graph = ReceiptGraph(revision_exists=False)
    store = FalkorSnapshotStore(FakeClient(graph))

    with pytest.raises(SnapshotNotFoundError):
        store.persist_query_result("workspace-1", "missing", "reader-1", "request-hash", {"result": "UNKNOWN"})


def test_query_receipt_read_reuses_only_the_original_request():
    graph = ReceiptGraph()
    store = FalkorSnapshotStore(FakeClient(graph))
    saved = store.persist_query_result(
        "workspace-1", "rev_1", "reader-1", "request-hash", {"result": "UNKNOWN"}
    )

    assert store.get_query_receipt("workspace-1", "reader-1", "request-hash") == saved
    assert store.get_query_receipt("workspace-1", "missing", "request-hash") is None
    with pytest.raises(IdempotencyConflictError):
        store.get_query_receipt("workspace-1", "reader-1", "different-hash")
