import json
from pathlib import Path

import pytest

from agents.client import MemoryClient
from agents.demo_memory import REVISION_ID, WORKSPACE_ID
from agents.operator import inconsistent_failure_add, replace_passing_tests, submit_revision
from agents.scripts import ScriptedFailureWriter, ScriptedReleaseReader
from agents.session import AgentSession
from agents.model import ScriptedActions
from agents.transport import AsgiTransport
from evaluation.acceptance import run_acceptance
from evaluation.lab_store import LabSnapshotStore
from memopops.api import create_app


@pytest.fixture
def lab_env(monkeypatch):
    store = LabSnapshotStore()
    monkeypatch.setenv(
        "MEMOPOPS_AUTH_TOKENS",
        json.dumps(
            {
                "reader-token": {"workspace_id": WORKSPACE_ID, "role": "reader"},
                "writer-token": {"workspace_id": WORKSPACE_ID, "role": "writer"},
                "operator-token": {"workspace_id": WORKSPACE_ID, "role": "operator"},
            }
        ),
    )
    app = create_app(store)
    reader = MemoryClient(AsgiTransport(app), "reader-token", WORKSPACE_ID)
    writer = MemoryClient(AsgiTransport(app), "writer-token", WORKSPACE_ID)
    operator = MemoryClient(AsgiTransport(app), "operator-token", WORKSPACE_ID)
    return store, reader, writer, operator


@pytest.mark.parametrize("action", [
    {"type": []},
    {"type": "tool", "name": "query_conclusion", "arguments": {"revision_id": REVISION_ID, "query": {"op": "atom", "id": "release_ready"}, "proof_mode": []}},
    {"type": "tool", "name": "record_decision", "arguments": {"expected_revision_id": REVISION_ID, "query_id": "missing", "choice": {}}},
])
def test_malformed_model_actions_are_rejected_without_crashing(lab_env, tmp_path, action):
    store, reader, _writer, _operator = lab_env
    session = AgentSession(client=reader, model=ScriptedActions([action]), role="reader", workspace_id=WORKSPACE_ID, mode="scripted_replay", journal_path=tmp_path / "malformed.json")
    report = session.run()
    assert report["events"][0]["outcome"] == "rejected"
    assert not store._decision_receipts


def test_scripted_reader_persists_proceed_decision(lab_env, tmp_path: Path):
    _store, reader, _writer, _operator = lab_env
    session = AgentSession(
        client=reader,
        model=ScriptedReleaseReader(),
        role="reader",
        workspace_id=WORKSPACE_ID,
        mode="scripted_replay",
        journal_path=tmp_path / "reader.json",
    )
    session.run()
    decision = session.current_decision()
    assert decision is not None
    assert decision["choice"] == "ship"
    assert decision.get("persisted") is True
    assert _store._decision_receipts


def test_resumed_reader_changes_decision_after_correction(lab_env, tmp_path: Path):
    _store, reader, _writer, operator = lab_env
    journal = tmp_path / "reader.json"
    first = AgentSession(
        client=reader,
        model=ScriptedReleaseReader(),
        role="reader",
        workspace_id=WORKSPACE_ID,
        mode="scripted_replay",
        journal_path=journal,
    )
    first.run()
    prior = first.current_decision()
    assert prior is not None

    status, body = submit_revision(
        operator,
        expected_revision=REVISION_ID,
        idempotency_key="test-correction",
        reason="Operator replaces the passing test report.",
        mutations=replace_passing_tests(),
    )
    assert status == 201

    resumed = AgentSession.resume(
        journal,
        client=reader,
        model=ScriptedReleaseReader(prior_decision=prior),
        role="reader",
        mode="scripted_replay",
    )
    resumed.run()
    current = resumed.current_decision()
    assert current is not None
    assert current["revision_id"] == body["revision_id"]
    assert current["choice"] == "hold"


def test_acceptance_suite_writes_report(tmp_path: Path):
    report = run_acceptance(tmp_path / "acceptance-run")
    assert (tmp_path / "acceptance-run" / "report.json").exists()
    assert all(item["passed"] for item in report["cases"])


def test_inconsistent_operator_proposal_is_quarantined(lab_env):
    store, _reader, _writer, operator = lab_env
    status, body = submit_revision(
        operator,
        expected_revision=REVISION_ID,
        idempotency_key="quarantine-tests-failed",
        reason="Attempt to add failing tests beside the passing report.",
        mutations=inconsistent_failure_add(),
    )
    assert status == 200 and body.get("status") == "QUARANTINED"
    proposals = store.list_quarantined_proposals(WORKSPACE_ID)
    assert len(proposals) == 1


def test_writer_cannot_activate_memory(lab_env, tmp_path: Path):
    _store, _reader, writer, _operator = lab_env
    session = AgentSession(
        client=writer,
        model=ScriptedFailureWriter(),
        role="writer",
        workspace_id=WORKSPACE_ID,
        mode="scripted_replay",
        journal_path=tmp_path / "writer.json",
    )
    result = session.run()
    assert any(event.get("outcome") == "rejected" for event in result["events"])
