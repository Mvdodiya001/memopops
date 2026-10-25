import json
from types import SimpleNamespace

import pytest

from memopops.store import FalkorSnapshotStore, SnapshotNotFoundError, WorkspaceExistsError, calculate_knowledge_hash


class BootstrapGraph:
    def __init__(self):
        self.initial = None
        self.calls = []

    def query(self, query, params=None):
        self.calls.append((query, params))
        if 'MERGE (w:Workspace' in query:
            if self.initial is not None:
                return SimpleNamespace(result_set=[[0]])
            self.initial = (params['digest'], params['revision_id'])
            return SimpleNamespace(result_set=[[len(params['atoms'])]])
        if 'RETURN w.bootstrap_hash' in query:
            return SimpleNamespace(result_set=[list(self.initial)])
        raise AssertionError('Unexpected persistence request')


def test_workspace_store_normalizes_retries_and_does_not_overwrite_existing_content():
    graph = BootstrapGraph()
    selected = []
    client = SimpleNamespace(select_graph=lambda name: (selected.append(name) or graph))
    store = FalkorSnapshotStore(client)
    atoms = [{'id': key, 'label': key, 'meaning': 'Precise '+key, 'scope': 'v3'} for key in ('p', 'q')]
    original = store.initialize_workspace('private/workspace', atoms, 'actor_test')
    retry = store.initialize_workspace('private/workspace', list(reversed(atoms)), 'actor_test')
    assert retry == original
    assert original['knowledge_hash'] == calculate_knowledge_hash([])
    with pytest.raises(WorkspaceExistsError):
        store.initialize_workspace('private/workspace', atoms[:1], 'actor_test')
    query, parameters = graph.calls[0]
    assert 'private/workspace' not in query and 'private/workspace' not in selected[0]
    assert parameters['workspace_id'] == 'private/workspace'
    assert parameters['actor_id'] == 'actor_test'
    assert parameters['atoms'] == atoms
    assert 'WHERE w.initial_revision = $revision_id' in query
    assert graph.initial[1] == original['revision_id']


def test_history_store_orders_by_time_then_id_and_does_not_export_certificate_bodies():
    payload = {'query_id': 'question-2', 'revision_id': 'rev', 'query': {'op': 'atom', 'id': 'p'}, 'result': 'PROVED', 'created_at': '2026-10-25T00:00:00Z', 'certificate': {'large': 'not a summary'}}
    calls = []
    class Graph:
        def query(self, query, params=None):
            calls.append((query, params))
            return SimpleNamespace(result_set=[[json.dumps(payload)]])
    store = FalkorSnapshotStore(SimpleNamespace(select_graph=lambda name: Graph()))
    items = store.list_queries('team', limit=1)
    assert items[0]['query'] == payload['query'] and 'certificate' not in items[0]
    assert calls[0][1]['workspace_id'] == 'team' and calls[0][1]['limit'] == 1
    assert 'q.summary_json' in calls[0][0] and 'q.result_json' in calls[0][0]
    assert "ORDER BY coalesce(q.created_at, '') DESC, q.id DESC" in calls[0][0]
    store.get_query_result = lambda workspace, query_id: None
    with pytest.raises(SnapshotNotFoundError):
        store.list_queries('team', before='unknown')
