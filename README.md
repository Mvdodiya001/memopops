# memopops

Proof-carrying shared memory for AI agents, targeting Graph Hacks Track 02. Working concept: persistent propositions, evidence, revisions, and proof dependencies in FalkorDB, with a separate propositional-logic checker.

Status: first backend implementation in progress. The Python 3.12 package contains strict Boolean formula parsing, canonical hashes, a two-worker Z3 classifier with a bounded 16-request waiting queue, hash-verified FalkorDB snapshot reads, receipt-first retries, and workspace-scoped query-result reloads. Local package versions are locked in `uv.lock`; live database behavior remains to be checked against the available FalkorDB instance.

## Local FalkorDB

Install Docker Desktop with its Linux engine, then copy `.env.example` to `.env` and replace the local development password and demo bearer tokens. Start the persistent, loopback-only database and API with `docker compose up -d --build`; check them with `docker compose ps` and `docker compose logs api falkordb`. Seed the synthetic workspace with `docker compose exec api python scripts/seed_demo.py`. Stop services with `docker compose down`. The named volume keeps graph data when the container stops. Do not run `docker compose down -v` unless you intend to erase that data.

The Compose image currently uses the official server image's moving `latest` tag for local development. Pin a tested version or digest before release. Hosted FalkorDB uses the same client settings; configure its exact host, port, username, password and TLS from its Connectivity panel, and keep those values in an ignored `.env` file or the deployment's secret store. The supplied hosted endpoint is in `.env.cloud`, which is ignored by Git. This network's proxy currently rejects `CONNECT` to its database port, so the hosted instance has not yet been reached from this machine.

## Python core

Use the locked Python 3.12 environment with `uv sync --frozen --group dev`, then run `uv run pytest`. The core accepts the versioned JSON formula AST, rejects unregistered atoms and over-limit formulas, and classifies queries over the complete supplied snapshot. The current API supports solver-only query requests; independent certificate generation/checking and revision mutation are later milestones and are not represented as complete.

## Start here

- [Detailed implementation plan and parallel work](docs/IMPLEMENTATION_PLAN.md)
- [Agent and contributor rules](AGENTS.md)
- [Project context and MVP boundaries](docs/PROJECT_CONTEXT.md)
- [Two-person workflow](docs/COLLABORATION.md)
- [Research and source notes](docs/RESEARCH.md)
- [Master activity log](logs/MASTER.md)
- Detailed logs: [Saqlain](logs/saqlain.md) and [Mahavir](logs/mahavir.md)

Each person should use their own clone and task branch. Do not run concurrent agents in the same working directory. Read AGENTS.md before making changes.
