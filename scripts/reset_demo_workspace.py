"""Delete only the synthetic demo graph, then reseed it for a fresh take."""

from __future__ import annotations

import argparse
import os

from memopops.store import FalkorSnapshotStore, graph_name_for_workspace
from scripts import seed_demo


def reset_demo_workspace(*, confirmed: bool) -> None:
    seed_demo.load_local_env()
    if not os.getenv("FALKORDB_HOST"):
        raise SystemExit("FALKORDB_HOST is required")
    if not confirmed:
        raise SystemExit("Refusing to delete the demo graph without --yes")

    target = graph_name_for_workspace(seed_demo.WORKSPACE_ID)
    store = FalkorSnapshotStore.from_env()
    try:
        client = store._get_client()
        graphs = sorted(client.list_graphs())
        untouched = [name for name in graphs if name != target]
        print(f"Demo graph selected for reset: {target}")
        print(f"Other graphs left untouched: {untouched}")
        if target in graphs:
            client.select_graph(target).delete()
            print("Deleted the demo graph.")
        else:
            print("The demo graph did not exist.")
    finally:
        store.close()

    seed_demo.main()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset only workspace_demo for a video retake.")
    parser.add_argument("--yes", action="store_true", help="Confirm deletion of workspace_demo only.")
    args = parser.parse_args()
    reset_demo_workspace(confirmed=args.yes)


if __name__ == "__main__":
    main()
