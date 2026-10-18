import json

from agents.client import MemoryClient
from agents.demo_memory import WORKSPACE_ID
from agents.transport import AsgiTransport
from evaluation.lab_store import LabSnapshotStore
from memopops.api import create_app
from scripts.demo_video import DemoRunner


def test_scripted_video_scenes_cover_correction_flow(monkeypatch, tmp_path):
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
    store = LabSnapshotStore()
    transport = AsgiTransport(create_app(store))
    runner = DemoRunner(
        reader=MemoryClient(transport, "reader-token", WORKSPACE_ID),
        writer=MemoryClient(transport, "writer-token", WORKSPACE_ID),
        operator=MemoryClient(transport, "operator-token", WORKSPACE_ID),
        output=tmp_path / "video",
        model_mode="scripted",
        take="test",
    )

    summary = runner.run(
        [
            "preflight",
            "memory",
            "reader",
            "uncertain",
            "writer",
            "correction",
            "resume",
            "graph",
        ]
    )

    assert summary["scenes"]["reader"]["decision"]["result"] == "PROVED"
    assert summary["scenes"]["reader"]["decision"]["choice"] == "ship"
    assert summary["scenes"]["uncertain"]["decision"]["result"] == "UNKNOWN"
    assert summary["scenes"]["uncertain"]["decision"]["choice"] == "abstain"
    assert summary["scenes"]["writer"]["quarantine"]["status"] == "QUARANTINED"
    assert summary["scenes"]["writer"]["head_revision_id"] == "rev_001"
    assert summary["scenes"]["correction"]["status"] == 201
    assert summary["scenes"]["correction"]["impact"]["total_count"] >= 1
    assert summary["scenes"]["resume"]["decision"]["result"] == "REFUTED"
    assert summary["scenes"]["resume"]["decision"]["choice"] == "hold"
    assert summary["scenes"]["graph"] == {"skipped": True}
    assert (tmp_path / "video" / "summary.json").exists()
    assert (tmp_path / "video" / "graph-queries.cypher").exists()
