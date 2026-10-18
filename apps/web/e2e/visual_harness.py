"""Synthetic browser fixture service and real-producer recorded artifacts.

Uses isolated in-memory stores, never FalkorDB or private environment config.
Start from the repository root: python -m apps.web.e2e.visual_harness
"""
import json
import os
from contextlib import redirect_stdout
from pathlib import Path

import uvicorn

from agents.client import MemoryClient
from agents.demo_memory import WORKSPACE_ID
from agents.transport import AsgiTransport
from evaluation.lab_store import LabSnapshotStore
from memopops.api import create_app
from scripts.demo_video import DemoRunner


def main():
    roles = {f"local-{role}-token": {"workspace_id": WORKSPACE_ID, "role": role} for role in ("reader", "writer", "operator")}
    os.environ["MEMOPOPS_AUTH_TOKENS"] = json.dumps(roles)
    recorded_store = LabSnapshotStore()
    transport = AsgiTransport(create_app(recorded_store))
    runner = DemoRunner(
        reader=MemoryClient(transport, "local-reader-token", WORKSPACE_ID),
        writer=MemoryClient(transport, "local-writer-token", WORKSPACE_ID),
        operator=MemoryClient(transport, "local-operator-token", WORKSPACE_ID),
        output=Path(".artifacts/frontend-browser/take-synthetic"),
        model_mode="scripted", take="synthetic-browser",
    )
    with Path(".artifacts/frontend-browser/producer.log").open("w", encoding="utf-8") as output, redirect_stdout(output):
        runner.run(["preflight", "memory", "reader", "uncertain", "writer", "correction", "resume", "verify", "graph"])
    app = create_app(LabSnapshotStore())

    @app.get("/__fixture/visualization")
    def fixture_identity():
        return {"synthetic_visualization_harness": True}

    uvicorn.run(app, host="127.0.0.1", port=8010)


if __name__ == "__main__":
    main()
