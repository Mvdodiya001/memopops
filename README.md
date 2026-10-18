# memopops

Proof-carrying shared memory for AI agents, targeting Graph Hacks Track 02. Working concept: persistent propositions, evidence, revisions, and proof dependencies in FalkorDB, with a separate propositional-logic checker.

Status: hackathon implementation on `main` — proof-carrying shared memory with FalkorDB, independent checker, web inspector, scripted agents, and acceptance evaluation. Submission preparation uses complete local setup rather than public application deployment. The real FalkorDB recording and local persistence/restart rehearsal still need completion; see the [submission execution plan](docs/submission/PLAN.md).

The Python 3.12 service contains strict Boolean formula parsing, canonical hashes, a two-worker Z3 classifier with a bounded 16-request waiting queue, hash-verified FalkorDB snapshot reads, atomic revision publication, idempotency receipts, quarantined inconsistent proposals, workspace-scoped memory/history/query reads, and bounded resolution certificates checked by the independent `proofcheck` package.

## Local FalkorDB

Follow the [complete local setup](docs/submission/LOCAL_SETUP.md) for prerequisites, separate frontend launch, API port selection, and the recording/restart checks. Compose runs the database and API; it does not start the web inspector.

Install Docker Desktop with its Linux engine, then copy `.env.example` to `.env` and replace the local development password and demo bearer tokens. Configure reader/writer tokens for agents and an operator token for accepted-memory commits. Start the persistent, loopback-only database and API with `docker compose up -d --build`; check them with `docker compose ps` and `docker compose logs api falkordb`. Seed the synthetic workspace with `docker compose exec api python scripts/seed_demo.py`; the seed command checks existing immutable content and provenance before retrying. Stop services with `docker compose down`. The named volume keeps graph data when the container stops. Do not run `docker compose down -v` unless you intend to erase that data.

The local Compose configuration pins the official server image to `v4.22.0`, matching the supplied hosted instance version. Set `FALKORDB_PASSWORD` and `MEMOPOPS_AUTH_TOKENS` in an ignored `.env` file before starting the stack. Hosted FalkorDB uses the same client settings; configure its exact host, port, username, password and TLS from its Connectivity panel, and keep those values in `.env.cloud` or the deployment's secret store. Database startup and persistence/restart checks have not been run in this work session; complete them with local Docker or the configured hosted instance before the final recording.

## Implemented graph data model

Each authorized workspace selects a separate FalkorDB graph. A Workspace's `head_revision` property selects the current immutable Revision. A revision `INCLUDES` accepted Assertions; each assertion `ENCODES` a Formula and is `SUPPORTED_BY` Evidence. Formula nodes store content-hashed canonical Boolean AST JSON. Atom nodes form the scoped meaning registry.

QueryResults point to their revision with `AT_REVISION` and to premise assertions with `USES_PREMISE`. A correction records removed assertion IDs; traversing these premise links identifies affected queries at the parent revision. Quarantined Proposals remain outside accepted membership. Decisions link to their query/revision, and RequestReceipts preserve idempotent outcomes. Certificates are stored/exported JSON, rather than separate proof-step graph nodes.

See the [actual schema, diagram, and core Cypher](docs/submission/GRAPH_MODEL.md), with source in [store.py](src/memopops/store.py) and [seed_demo.py](scripts/seed_demo.py). FalkorDB supplies persistence, provenance, and dependency traversal; Z3 and the independent checker supply logical reasoning and certificate verification.

## Python core

Use the locked Python 3.12 environment with `uv sync --frozen --group dev`, then run `uv run pytest`. The core accepts the versioned JSON formula AST, rejects unregistered atoms and over-limit formulas, and classifies queries over the complete supplied snapshot. The revision API validates bounded add/replace/retract candidates, hashes evidence, rejects inconsistent or indeterminate activation, and uses an atomic expected-head graph write. Conflicting candidates are preserved as quarantined proposals. Only an operator credential may commit accepted memory; reader and writer credentials cannot promote a proposal. Query requests default to `proof_mode: "certificate"`; decisive results are marked VERIFIED only after the independent checker validates both the proof and trusted workspace, revision, assertion and evidence context. Certificate search has fixed clause, pair and time limits. If it exceeds a limit, the solver result is retained with `proof_status: "BUDGET_EXCEEDED"`. Use `proof_mode: "solver"` to skip certificate generation. Export a verified bundle from `GET /api/v1/workspaces/{workspace_id}/queries/{query_id}/certificate`; the certificate itself is stored with the immutable query result for retry and history.

The live API exposes authenticated workspace discovery/details, `GET /api/v1/workspaces/{workspace_id}/memory`, `GET /api/v1/workspaces/{workspace_id}/revisions`, `POST /api/v1/workspaces/{workspace_id}/revisions`, `GET /api/v1/workspaces/{workspace_id}/proposals?status=QUARANTINED`, `GET /api/v1/workspaces/{workspace_id}/impact?revision={revision_id}`, revision-bound query endpoints, verified certificate export, and `POST /api/v1/workspaces/{workspace_id}/decisions`. Query results store server-derived actor and UTC creation time alongside their premise links and retry receipt. Decision receipts bind a reader's `PROCEED` or `BLOCK` outcome to a query and the current revision in one graph write; actor identity comes from authentication and an idempotency key prevents duplicate records. These receipts record a choice and never trigger an external action. Proposal inspection returns at most 50 recent quarantined submissions with their validated request data; it does not calculate or claim an exact unsatisfiable core. Impact pages list historical queries whose checked support, or conservative full-snapshot dependency for unverified results, includes an assertion removed by the selected revision. A separate model-proposed submission path and exact conflict-core analysis are not implemented.

## Local browser smoke without FalkorDB

For frontend development while the database is unavailable, the browser test uses a deliberately synthetic in-memory API. It verifies the live connection form, memory/history reads, and a certificate-verified `release_ready` query. It does not test graph persistence, database restart, accepted revision writes, or the correction walkthrough, and its results must not be described as FalkorDB evidence.

Build the frontend once, then run these in separate terminals from the repository root:

```powershell
npm --prefix apps/web run build
uv run --locked python apps/web/e2e/harness.py
```

In another terminal, start the built frontend with `npm --prefix apps/web run preview`. In a third terminal, run the browser check (set `CHROME_PATH` if Chrome is not on `PATH`):

```powershell
$env:CHROME_PATH = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
Set-Location apps/web
node e2e/live-query.mjs
```

The harness uses workspace `workspace_demo`, revision `rev_001`, and a local reader token defined by the harness. Keep this fixture out of hosted configuration.

## Agent clients and evaluation

Scripted reader/writer sessions live in `agents/` and call the same published routes as the web app, including `POST /decisions` for revision-bound `PROCEED`/`BLOCK` receipts. Run the acceptance suite without FalkorDB:

```bash
uv run --locked python -m evaluation.run --suite acceptance --output docs/evaluation/acceptance-run
```

For the synthetic lab replay, run this from the repository root. Lab mode configures its own process-local fixture identities and does not need production credentials:

```powershell
uv run --locked python -m scripts.run_agent_demo --mode lab --output .artifacts/agent-demo
```

This module invocation was checked on October 18. For the full real-API correction/resume recording, use the narrated runner:

```bash
PYTHONPATH=.:src:packages/proofcheck/src uv run --locked python scripts/demo_video.py \
  --api-base http://127.0.0.1:8001 --model live --model-timeout 10 \
  --pause --reset --take 1
```

The opt-in `--reset` deletes and reseeds only the synthetic `workspace_demo` graph, making repeat takes reproducible without assuming that its current revision is named `rev_001`. Omit the flag to preserve and inspect the current graph; the runner will stop with guidance if that graph no longer contains the canonical demo baseline.

See [docs/evaluation/README.md](docs/evaluation/README.md). Live model calls stay off unless `MEMOPOPS_MODEL_API_KEY` is set in the gitignored `.env` file. The video runner selects `gemini-flash-latest` and uses Google's native `generateContent` function-calling API with `X-goog-api-key`. Gemini can choose only the bounded functions declared for its reader or writer role; the existing `AgentSession` still validates every call, enforces role and revision guards, and caps tool steps. Live requests print progress and use a configurable 10-second default timeout; after two failed attempts, the runner labels that scene **Scripted replay** and uses the deterministic fallback.

The live web inspector can list quarantined proposals (`GET /proposals`) and record reader decisions after a verified query at the current head.

## Release verification

```bash
chmod +x scripts/verify_release.sh
./scripts/verify_release.sh
```

## Start here

- [Submission execution plan and parallel schedule](docs/submission/PLAN.md)
- [Draft form answers](docs/submission/FORM_ANSWERS.md), [timed video script](docs/submission/VIDEO.md), and [blog brief](docs/submission/BLOG_BRIEF.md)
- [Demo storyboard](docs/DEMO.md)
- [Submission checklist](docs/SUBMISSION.md)
- [Detailed implementation plan and parallel work](docs/IMPLEMENTATION_PLAN.md)
- [Agent and contributor rules](AGENTS.md)
- [Project context and MVP boundaries](docs/PROJECT_CONTEXT.md)
- [Two-person workflow](docs/COLLABORATION.md)
- [Research and source notes](docs/RESEARCH.md)
- [Master activity log](logs/MASTER.md)
- Detailed logs: [Saqlain](logs/saqlain.md) and [Mahavir](logs/mahavir.md)

Each person should use their own clone and task branch. Do not run concurrent agents in the same working directory. Read AGENTS.md before making changes.

## AI assistance and demonstration mode

AI coding assistants supported planning, implementation, tests, UI, and documentation. The [activity logs](logs/MASTER.md) record the work and verification results. The team remains responsible for the submission and its technical claims. Each demo scene is labeled live Gemini function calling or scripted replay; neither mode bypasses service validation. Demo observations are synthetic. A logical proof is conditional on accepted premises and does not establish their factual truth.
