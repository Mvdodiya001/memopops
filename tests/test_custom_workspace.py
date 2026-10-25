import json

from agents.client import MemoryClient
from agents.transport import AsgiTransport
from evaluation.lab_store import LabSnapshotStore
from memopops.api import create_app


def test_custom_workspace_full_lifecycle_and_paginated_question_history(monkeypatch):
    workspace = 'project_orion'
    monkeypatch.setenv('MEMOPOPS_AUTH_TOKENS', json.dumps({'operator': {'workspace_id': workspace, 'role': 'operator'}, 'reader': {'workspace_id': workspace, 'role': 'reader'}}))
    store = LabSnapshotStore(workspace_id=workspace, empty=True)
    app = create_app(store)
    transport = AsgiTransport(app)
    operator = MemoryClient(transport, 'operator', workspace)
    reader = MemoryClient(transport, 'reader', workspace)
    atoms = [{'id': key, 'label': label, 'meaning': meaning, 'scope': 'Orion version 3'} for key, label, meaning in [('p', 'Tests pass', 'All required Orion version 3 tests passed'), ('q', 'Approved', 'Orion version 3 is approved under the recorded policy')]]
    try:
        assert operator.workspace()[0] == 404
        status, initialized = transport.request('POST', f'/api/v1/workspaces/{workspace}/initialize', {'atoms': atoms}, 'operator')
        assert status == 201
        head = initialized['revision_id']
        assert reader.memory(head)[1]['assertions'] == []
        assert reader.memory(head)[1]['atoms'] == atoms
        def question(key):
            status, body = reader.submit_query({'revision_id': store.head, 'idempotency_key': key, 'query': {'op': 'atom', 'id': 'q'}, 'proof_mode': 'certificate'})
            assert status == 200, body
            return body
        assert question('empty')['result'] == 'UNKNOWN'
        evidence = [{'uri': 'fixture://orion/tests', 'excerpt': 'Synthetic observation for the lifecycle test', 'observed_at': '2026-10-25T00:00:00Z'}]
        def assertion(formula, ref): return {'client_ref': ref, 'formula': formula, 'evidence': evidence}
        def change(mutations, key):
            return operator.submit_revision({'expected_revision': store.head, 'idempotency_key': key, 'reason': 'Reviewed project evidence', 'acceptance': 'human_confirmed', 'mutations': mutations})
        p = {'op': 'atom', 'id': 'p'}
        not_p = {'op': 'not', 'arg': p}
        status, accepted = change([{'op': 'add', 'assertion': assertion(p, 'observation')}, {'op': 'add', 'assertion': assertion({'op': 'iff', 'args': [p, {'op': 'atom', 'id': 'q'}]}, 'policy')}], 'initial-facts')
        assert status == 201
        original_claim = accepted['client_refs']['observation']
        proved = question('proved')
        assert proved['result'] == 'PROVED' and proved['proof_status'] == 'VERIFIED'
        before_conflict = store.head
        status, conflict = change([{'op': 'add', 'assertion': assertion(not_p, 'contradiction')}], 'conflicting-add')
        assert status == 200 and conflict['status'] == 'QUARANTINED' and store.head == before_conflict
        status, corrected = change([{'op': 'replace', 'target_assertion_id': original_claim, 'assertion': assertion(not_p, 'correction')}], 'replace-fact')
        assert status == 201
        refuted = question('refuted')
        assert refuted['result'] == 'REFUTED' and refuted['proof_status'] == 'VERIFIED'
        assert reader.memory(before_conflict)[1]['assertions'][0]['evidence']
        assert change([{'op': 'retract', 'target_assertion_id': corrected['client_refs']['correction']}], 'retract-fact')[0] == 201
        unknown = question('retracted')
        assert unknown['result'] == 'UNKNOWN' and unknown['witnesses_verified']
        path = f'/api/v1/workspaces/{workspace}/queries?limit=2'
        status, first = transport.request('GET', path, None, 'reader')
        assert status == 200 and len(first['items']) == 2
        assert first['items'][0]['query_id'] == unknown['query_id']
        assert first['items'][0]['query'] == {'op': 'atom', 'id': 'q'}
        assert first['items'][0]['freshness'] == 'CURRENT_AS_OF_READ'
        assert first['items'][1]['freshness'] == 'HISTORICAL'
        status, second = transport.request('GET', path+'&before='+first['next_cursor'], None, 'reader')
        assert status == 200 and not ({i['query_id'] for i in first['items']} & {i['query_id'] for i in second['items']})
        assert all('certificate' not in item for page in (first, second) for item in page['items'])
        status, retry = transport.request('POST', f'/api/v1/workspaces/{workspace}/initialize', {'atoms': list(reversed(atoms))}, 'operator')
        assert status == 201 and retry['revision_id'] == head and store.head != head
        status, _ = transport.request('POST', f'/api/v1/workspaces/{workspace}/initialize', {'atoms': atoms[:1]}, 'operator')
        assert status == 409
    finally:
        app.state.solver_executor.shutdown()
