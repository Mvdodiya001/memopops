import json
from pathlib import Path

import agents.model as model_config
from agents.client import MemoryClient
from agents.demo_memory import WORKSPACE_ID
from agents.gemini_tools import GeminiFunctionCallingModel
from agents.session import AgentSession
from agents.transport import AsgiTransport
from evaluation.lab_store import LabSnapshotStore
from memopops.api import create_app


def _response(name: str, args: dict) -> dict:
    return {
        "candidates": [
            {
                "content": {
                    "parts": [{"functionCall": {"name": name, "args": args}}],
                }
            }
        ]
    }


def _actor(responses: list[dict], *, role: str = "reader") -> tuple[GeminiFunctionCallingModel, list]:
    captured = []

    def complete(payload, timeout):
        captured.append((payload, timeout))
        return responses.pop(0)

    return (
        GeminiFunctionCallingModel(
            complete,
            role=role,
            goal="Test the release.",
            workspace_id=WORKSPACE_ID,
            sleep=lambda _seconds: None,
        ),
        captured,
    )


def test_maps_query_and_strips_rationale():
    actor, captured = _actor(
        [
            _response(
                "query_conclusion",
                {
                    "rationale": "Check the current release fact.",
                    "revision_id": "rev_001",
                    "atom_id": "release_ready",
                    "negated": True,
                },
            )
        ]
    )

    action = actor.next_action({"type": "start"})

    assert action == {
        "type": "tool",
        "name": "query_conclusion",
        "arguments": {
            "revision_id": "rev_001",
            "query": {"op": "not", "arg": {"op": "atom", "id": "release_ready"}},
            "proof_mode": "certificate",
        },
    }
    assert actor.last_rationale == "Check the current release fact."
    assert captured[0][0]["toolConfig"]["functionCallingConfig"]["mode"] == "ANY"
    assert "propose_assertion" not in actor.allowed_names


def test_writer_maps_proposal_and_reader_does_not_receive_writer_tool():
    actor, captured = _actor(
        [
            _response(
                "propose_assertion",
                {
                    "rationale": "Submit the failed test observation.",
                    "expected_revision_id": "rev_001",
                    "atom_id": "tests_pass",
                    "negated": True,
                    "reason": "Integration tests failed.",
                    "client_ref": "writer-tests-failed",
                    "evidence_uri": "fixture://failed",
                    "evidence_excerpt": "Synthetic tests failed.",
                    "observed_at": "2026-10-17T12:00:00Z",
                },
            )
        ],
        role="writer",
    )

    action = actor.next_action({"type": "start"})

    assert "propose_assertion" in actor.allowed_names
    assert action["arguments"]["formula"] == {
        "op": "not",
        "arg": {"op": "atom", "id": "tests_pass"},
    }
    assert action["arguments"]["evidence"]["uri"] == "fixture://failed"
    declarations = captured[0][0]["tools"][0]["functionDeclarations"]
    assert {item["name"] for item in declarations} == set(actor.allowed_names)


def test_second_turn_sends_function_response():
    actor, captured = _actor(
        [
            _response("inspect_memory", {"rationale": "Read the current memory."}),
            _response(
                "finish",
                {"rationale": "The read is complete.", "summary": "Finished safely."},
            ),
        ]
    )

    first = actor.next_action({"type": "start"})
    second = actor.next_action(
        {"outcome": "ok", "tool": "inspect_memory", "head_revision_id": "rev_001"}
    )

    assert first == {"type": "tool", "name": "inspect_memory", "arguments": {}}
    assert second == {"type": "stop"}
    contents = captured[1][0]["contents"]
    assert contents[0]["role"] == "user"
    assert contents[1]["role"] == "model"
    response = contents[2]["parts"][0]["functionResponse"]
    assert response["name"] == "inspect_memory"
    assert response["response"]["event"]["head_revision_id"] == "rev_001"
    assert actor.last_rationale == "Finished safely."


def test_plain_text_is_ignored_once_then_stops():
    text = {"candidates": [{"content": {"parts": [{"text": "I cannot call a tool."}]}}]}
    actor, _captured = _actor([text, text])

    assert actor.next_action({"type": "start"}) == {
        "type": "text",
        "content": "I cannot call a tool.",
    }
    assert actor.next_action({"outcome": "ignored_text"}) == {"type": "stop"}


def test_missing_key_returns_none(monkeypatch, tmp_path):
    for key in (
        model_config.LIVE_KEY_ENV,
        model_config.LIVE_BASE_ENV,
        model_config.LIVE_NAME_ENV,
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(model_config, "_LOCAL_ENV_PATH", tmp_path / "missing.env")

    assert (
        GeminiFunctionCallingModel.from_env(
            "reader",
            "Check release readiness.",
            workspace_id=WORKSPACE_ID,
        )
        is None
    )


def test_retryable_failures_are_bounded():
    attempts = 0

    def complete(_payload, _timeout):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("model request failed: HTTP 503")
        return _response("finish", {"rationale": "Done.", "summary": "Done."})

    actor = GeminiFunctionCallingModel(
        complete,
        role="reader",
        goal="Test.",
        workspace_id=WORKSPACE_ID,
        sleep=lambda _seconds: None,
    )

    assert actor.next_action({"type": "start"}) == {"type": "stop"}
    assert attempts == 3


def test_function_adapter_runs_guarded_reader_session(monkeypatch, tmp_path: Path):
    monkeypatch.setenv(
        "MEMOPOPS_AUTH_TOKENS",
        json.dumps(
            {
                "reader-token": {
                    "workspace_id": WORKSPACE_ID,
                    "role": "reader",
                }
            }
        ),
    )
    store = LabSnapshotStore()
    client = MemoryClient(AsgiTransport(create_app(store)), "reader-token", WORKSPACE_ID)
    responses = [
        _response("inspect_memory", {"rationale": "Read accepted memory."}),
        _response(
            "query_conclusion",
            {
                "rationale": "Check readiness at the head.",
                "revision_id": "rev_001",
                "atom_id": "release_ready",
                "negated": False,
            },
        ),
    ]

    def complete(payload, _timeout):
        if len(responses) == 2:
            return responses.pop(0)
        if len(responses) == 1:
            return responses.pop(0)
        last_event = payload["contents"][-1]["parts"][0]["functionResponse"]["response"]["event"]
        if last_event["tool"] == "query_conclusion":
            return _response(
                "record_decision",
                {
                    "rationale": "A proved query means ship.",
                    "expected_revision_id": last_event["revision_id"],
                    "query_id": last_event["query_id"],
                    "choice": "ship",
                },
            )
        return _response(
            "finish",
            {"rationale": "The decision is recorded.", "summary": "Release can ship."},
        )

    actor = GeminiFunctionCallingModel(
        complete,
        role="reader",
        goal="Decide whether release_ready holds.",
        workspace_id=WORKSPACE_ID,
        sleep=lambda _seconds: None,
    )
    session = AgentSession(
        client=client,
        model=actor,
        role="reader",
        workspace_id=WORKSPACE_ID,
        mode="live_model",
        journal_path=tmp_path / "reader.json",
    )

    result = session.run()

    decision = session.current_decision()
    assert decision is not None
    assert decision["choice"] == "ship"
    assert decision["persisted"] is True
    assert result["mode"] == "live_model"
    assert json.loads((tmp_path / "reader.json").read_text())["mode"] == "live_model"
