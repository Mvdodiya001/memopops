import sys

import pytest

from evaluation import run as evaluation_cli
from scripts import run_agent_demo
from agents.client import MemoryClient


def test_acceptance_cli_exits_nonzero_for_a_failed_case(monkeypatch, tmp_path):
    monkeypatch.setattr(evaluation_cli, "run_acceptance", lambda _path: {"cases": [{"passed": False}]})
    monkeypatch.setattr(sys, "argv", ["evaluation", "--suite", "acceptance", "--output", str(tmp_path)])
    with pytest.raises(SystemExit) as error:
        evaluation_cli.main()
    assert error.value.code == 1


def test_agent_client_encodes_workspace_and_query_identifiers():
    calls = []
    class Transport:
        def request(self, method, path, body, token):
            calls.append(path)
            return 200, {}
    client = MemoryClient(Transport(), "synthetic", "team / one")
    client.workspace()
    client.memory("rev&other=value")
    client.impact("rev&other=value")
    client.query_result("query?#one")
    client.certificate("query?#one")
    assert calls[0].endswith("team%20%2F%20one")
    assert calls[1].endswith("revision_id=rev%26other%3Dvalue")
    assert "revision=rev%26other%3Dvalue&limit=50" in calls[2]
    assert calls[3].endswith("/queries/query%3F%23one")
    assert calls[4].endswith("/queries/query%3F%23one/certificate")


@pytest.mark.parametrize("configured", [False, True])
def test_lab_replay_uses_its_own_fixture_identity(monkeypatch, tmp_path, configured):
    if configured:
        monkeypatch.setenv("MEMOPOPS_AUTH_TOKENS", '{"unrelated-private-token":{"workspace_id":"other","role":"reader"}}')
    else:
        monkeypatch.delenv("MEMOPOPS_AUTH_TOKENS", raising=False)
    monkeypatch.setattr(sys, "argv", ["run_agent_demo", "--mode", "lab", "--output", str(tmp_path)])
    run_agent_demo.main()
    assert (tmp_path / "reader.json").exists()
    assert (tmp_path / "summary.json").exists()
