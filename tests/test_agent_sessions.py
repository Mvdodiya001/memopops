import json
from pathlib import Path

import pytest

from agents.client import MemoryClient
from agents.demo_memory import REVISION_ID, WORKSPACE_ID
from agents.operator import inconsistent_failure_add, replace_passing_tests, submit_revision
from agents.scripts import ScriptedFailureWriter, ScriptedReleaseReader
from agents.session import AgentSession
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
