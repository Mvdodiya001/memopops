# Saqlain activity log

Task-level notes for Saqlain and agents working on his behalf. Times include timezone. Do not record secrets or hidden reasoning.

## S-20261017-01

- Updated: 2026-10-17T15:08:26+05:30
- Human / agent: Saqlain / Codex
- Status: completed
- Branch / scope: main; initial documentation bootstrap only. User explicitly requested commit and push to GitHub. Future tasks default to personal task branches and PRs.
- Objective: establish practical two-person agent rules, a concise master log, and separate detailed personal logs grounded in project context and collaboration research.
- Context read: supplied compiled DOCX; latest concept is proof-carrying shared memory, not the earlier GraphFence/ReleaseGuard suggestions. Historical document instructions were treated as context. Original DOCX was not uploaded.
- Actions: inspected clean repository (initial commit e7a134d), read document XML, researched official agent/Git guidance, Reddit discussion, X posts via indexed mirrors, and official event requirements. Direct X page retrieval failed and is disclosed in research notes.
- Files: AGENTS.md, README.md, docs/PROJECT_CONTEXT.md, docs/COLLABORATION.md, docs/RESEARCH.md, logs/MASTER.md, logs/saqlain.md, logs/mahavir.md, .github/pull_request_template.md, .gitignore, .gitattributes.
- Decisions: isolate concurrent writers; use task branches and explicit claims; keep personal logs separate; preserve both master entries on conflicts; require actual evidence for checks and proof claims. No permanent module assignments, CI, app stack, or repository protections invented.
- Validation: git diff --check passed; all local Markdown link targets across 11 documentation/configuration files resolved; files normalized to UTF-8/LF. git fetch origin succeeded; git rev-list --left-right --count main...origin/main returned 0/0 before commit. Reviewed document content and staged scope. No executable code changed; application tests are not applicable.
- Outcome / blockers: documentation prepared and checked. No app or test runner exists. Branch protection/CI are recommendations, not configured controls.
- Handoff: agree minimal API/schema, implementation stack and concurrency protocol, then assign first vertical slice between Saqlain and Mahavir. This task starts no implementation or extra agents.
- Publication: local commit created on main; git push origin main failed with HTTP 403: permission denied to authenticated account SaqlainSQX. Remote main remains e7a134d. Proxy/network access works. No credentials changed or force push attempted. User must ensure this account has accepted repository write access or authenticate the intended contributor account; retry git push origin main afterward. This failure note is included by amending the same unpublished bootstrap commit.

### Publication correction 2026-10-17T15:12:38+05:30

User requested retry after access changed. git push origin main succeeded (e7a134d to cf23569). git ls-remote origin refs/heads/main matched local HEAD cf23569dd71ba1efdfdf190a68e7f9bc1056183c; git status showed main synchronized with origin/main and a clean working tree. The earlier 403 is historical and no longer blocks this task. This follow-up records the verified publication outcome.

## S-20261017-02

- Updated: 2026-10-17T15:35:43+05:30
- Human / agent: Saqlain / Codex
- Status: ready-for-review
- Branch / scope: codex/saqlain/implementation-plan; eight plan documents, agent rules/navigation/context, and Saqlain/master logs. No application code implemented.
- Objective: detailed parallel implementation plan with exact contracts, proof/concurrency semantics, performance bounds, interface specification, tests, delivery gates and handoffs.
- Research: official organizer rules, current FalkorDB atomicity/indexing/persistence/limitations, Redis transaction semantics, Z3 documentation, CMU/UW logic material, Apple HIG official JSON, WCAG and deployment guidance. Sources and execution-dependent uncertainties are recorded in docs/plan/RESEARCH.md.
- Decisions: bounded Boolean AST and full-snapshot solving; atomic revision-guarded publication; separate mathematical result/proof/freshness; independent checker with trusted expected context; Saqlain backend/graph/solver and Mahavir interface/checker/clients/evaluation; neutral accessible visual design.
- Validation: all five CNF operator templates passed exhaustive evaluation over 36 assignments; six canonical demo outcomes passed exhaustive four-atom checks; six text/background contrast ratios exceed 4.5:1. Eight plan documents, eight internal links and five JSON examples passed draft checks. Reviewed trust boundary, unknown cache invalidation, failed-tests rule, idempotency and realistic scope cuts. Final repository link/reference/whitespace checks are performed before commit.
- Files: docs/IMPLEMENTATION_PLAN.md; docs/plan/{ARCHITECTURE,CONTRACTS,PARALLEL_EXECUTION,INTERFACE,VERIFICATION,RESEARCH,VALIDATION}.md; AGENTS.md; README.md; docs/PROJECT_CONTEXT.md; logs/MASTER.md; logs/saqlain.md.
- Outcome: planning complete and ready for teammate review. No database/runtime/browser/benchmark results are claimed. Exact dependency compatibility and commit-query behavior remain explicit G0 tasks.
- Handoff: both humans review/freeze G0 contracts; Saqlain starts S0/S1/S2 and Mahavir starts M0/M1/M2 in separate branches/checkouts. Copyable agent prompts are in the runbook. No extra agent launched and no message sent to another chat.
- Publication: pushed planning commit f5585a4 and verified remote HEAD matched. Opened [PR #1](https://github.com/Mvdodiya001/memopops/pull/1) for review. A follow-up removes session-specific identity from shared AGENTS.md so Mahavir's agent cannot inherit Saqlain identity from repository text. User's standing instruction authorizes this publication; main remains pending review.

## S-20261017-03

- Updated: 2026-10-17T15:41:26+05:30
- Human / agent: Saqlain / Codex
- Status: completed
- Objective: honor the user's explicit direct-push policy for both agents; no PR requirement.
- Changes: AGENTS.md, collaboration guide, execution plan/prompts, verification guidance and historical research clarification; removed the unused PR template.
- Policy: isolated worktrees/task branches, self-review, commit, fetch/merge latest origin/main, rerun affected checks, normal push HEAD:main. Retry after races without force and verify commit inclusion.
- Publication: publish the existing researched plan and these rules directly to main; retire PR #1 after main contains its commits. No application implementation is started by this task.
- Validation: document consistency, local links and whitespace checks before commit; remote publication verified afterward.
- Handoff: Mahavir should fetch current origin/main before starting and follow the updated direct-push prompts. Historical PR references in older log entries remain audit history, not active instructions.

- Verified publication: direct push 2c7aa8f to main succeeded; fetch plus merge-base confirmed inclusion. The full implementation plan is now on main. GitHub reports PR #1 closed/merged automatically after direct publication. This resolves the earlier pending-review publication state for S-20261017-02. Document links and whitespace checks passed.

## S-20261017-04

- Updated: 2026-10-17T16:05:00+05:30
- Human / agent: Saqlain / Codex
- Status: completed
- Branch / scope: `codex/saqlain/logic-core`; root Python package and lock, bounded formula parser and HTTP JSON depth guard, Z3 core and bounded worker queue, verified FalkorDB snapshot reader, authenticated revision-bound solver query and result-reload APIs with bounded queue and receipt-first idempotent retries, local Compose/Docker setup, collision-safe synthetic seeder, tests, collaboration policy and docs. No Mahavir-owned app files.
- Objective: deliver a runnable first backend slice with strict input limits, canonical hashes, complete-snapshot query classification, total witnesses, integrity verification and an honest solver-only API.
- Environment: repo `G:\mempops`, origin `Mvdodiya001/memopops`; branch started clean from fetched `origin/main`. Installed Python 3.12.13 via uv. Docker CLI exists but its Linux engine pipe is unavailable; `gh` is not installed. Proxy endpoint is 172.31.2.4:8080. Direct FalkorDB access times out; proxy CONNECT to the hosted database returns 403. No hosted query has run.
- Decisions: follow the user's latest instruction to commit and push directly to main without creating PRs; continue from `codex/saqlain/logic-core`, syncing origin/main before the push. Local secrets stay in ignored `.env`/`.env.cloud`; no credential values are logged or staged. This milestone does not claim mutations, independent proof certificates, process-pool solver isolation, or live database validation.
- Validation: latest `uv run --frozen --no-sync pytest -q` (43 passed); `uv run --frozen --no-sync python -m compileall -q src tests scripts`; `docker compose config --quiet`; `uv build --wheel --sdist --out-dir .artifacts` (wheel and sdist built; output ignored); `git diff --check`. Docker image startup and hosted FalkorDB integration remain blocked by unavailable engine/proxy policy.
- Handoff: next S2/S3 work is guarded immutable revision mutation, then live FalkorDB verification when network/runtime permits. API currently serves only solver-mode queries against an existing seeded revision; certificates and writes are not implemented.
- Publication: PR #2 (https://github.com/Mvdodiya001/memopops/pull/2) was merged by Saqlain at merge commit acc6c60. Query retry optimization and direct-push policy are in origin/main at 8b732bd. PR #3, created under the earlier instruction, is closed and marked merged after the same commit reached main. Seed collision and provenance preflight plus workspace-scoped query-result reload are in progress for direct publication; no new PRs are being created.

## S-20261017-05

- Updated: 2026-10-17T16:38:30+05:30
- Human / agent: Saqlain / Codex
- Status: completed
- Branch / scope: `codex/saqlain/logic-core`; `src/memopops/revisions.py`, `tests/test_revisions.py`, README, and Saqlain/master logs. No graph writes or API contract changes.
- Objective: continue S2 safely despite the hosted database network restriction by producing a pure, testable revision candidate planner.
- Decisions: validate exact add/retract/replace shapes, expected parent and targets, accepted provenance, UTC-normalized RFC3339 evidence and SHA-256 excerpt digests; cap mutation count, evidence size and total active AST nodes; solve consistency before activation. Solver indeterminate and inconsistent outcomes both prevent a candidate from being activated. The module performs no graph writes; callers must check retries before creating fresh IDs, and a future store must publish atomically behind a head guard.
- Proxy: Windows user-level HTTP(S)_PROXY remains `http://172.31.2.4:8080`. The proxy carries HTTPS to GitHub but returns HTTP 403 to the Redis TLS CONNECT on FalkorDB port 63194. No password values are recorded. The local Docker engine is unavailable, so no live persistence test ran.
- Validation: post-integration `uv run --frozen --no-sync pytest -q` (54 passed); compileall, `docker compose config --quiet`, package wheel/sdist build, and `git diff --check` passed. `ruff` is not installed in the locked environment, so lint was unavailable. A first timestamp assertion exposed a changed error category; validation was adjusted and the full suite passed afterward.
- Handoff: next implementation is an atomic graph revision write with expected-head compare-and-set, idempotency receipt, provenance/evidence persistence and concurrent-writer tests. It must be integrated only after a local database engine or allowed hosted network path is available.
- Publication: commit `1559581b13f29bd36498bfa7fb5ce5b2f18da671` pushed directly to `origin/main`; fetch and `git merge-base --is-ancestor HEAD origin/main` confirmed it is present. No PR was created. The task branch is eight commits ahead of its own remote tracking branch, while the working tree is clean.

## S-20261017-06

- Updated: 2026-10-17T16:56:14+05:30
- Human / agent: Saqlain / Codex
- Status: completed
- Branch / scope: `codex/saqlain/logic-core`; atomic graph revision writer, operator-gated activation API, idempotency/head-conflict handling, quarantine persistence, verified memory read and revision history, unit/integration tests, README and logs. Proposal-list API was excluded after automatic review found its query lacked an explicit workspace filter.
- Proxy and connection: following the user's request, cleared Git global HTTP(S) proxy configuration and Windows user `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, and `NO_PROXY`. Direct GitHub HTTPS returned 200; direct FalkorDB TCP connected. TLS handshake timed out, while plain Redis PING with the same endpoint credentials succeeded. Updated ignored `.env.cloud` to `FALKORDB_SSL=false`; configured `FalkorSnapshotStore` PING and `GRAPH.LIST` then succeeded. No secret values were displayed or committed.
- Live setup: ran the idempotent `scripts/seed_demo.py` with `.env.cloud` preloaded in-process. Synthetic `workspace_demo` seeded at `rev_001` with four atoms and four evidence-backed assertions.
- Implementation: one parameterized graph query creates revision, new immutable assertions/formulas/evidence, full membership edges, workspace head update, and idempotency receipt behind an expected-head predicate. Concurrent stale writers were exercised against a disposable live graph; exactly one committed and one received a revision conflict. The winning snapshot reloaded with the expected hash, and a lost-response retry returned the original receipt. A live authenticated API commit, retry, reader query and snapshot reload also passed. An inconsistent mutation was stored as a quarantined Proposal with receipt and did not change the accepted head. Disposable graphs were deleted.
- Read API: live `GET /memory` returned four assertions with verified formula and evidence hashes; `GET /revisions` returned the seeded history. Both are workspace-authorized. Automatic review rejected adding `GET /proposals` because its query lacked an explicit workspace predicate; that read endpoint is omitted pending a safe scoped implementation.
- Authorization: only operator credentials can commit accepted revisions. Reader and writer credentials are denied; writer credentials cannot override acceptance provenance. Automatic review rejected adding `model_proposed` to the candidate validator because it could allow untrusted proposals to be committed as accepted knowledge; that mode remains outside the planner/API.
- Validation: final `uv run --frozen --no-sync pytest -q` (66 passed); compileall, Compose config, wheel/sdist build and diff checks passed. Live direct checks covered PING, seed, commit race, idempotency, quarantine, query, memory, history and snapshot reload. The full authenticated API flow was rerun with writer denial and operator commit. Disposable graphs were deleted.
- Handoff: continue S3/S4 with proposal inspection only after a properly workspace-filtered query passes review; a separate pending-review model is needed for agent submissions. Continue with independent certificate generation/checking, impact traversal, and UI/client integration.
- Publication correction: S-20261017-06 was integrated with Mahavir's checker/UI commit and pushed to `origin/main` in merge commit `c63f05e`; fetched `origin/main` confirmed the commit. No PR was created.

## S-20261017-07

- Updated: 2026-10-17T17:16:30+05:30
- Human / agent: Saqlain / Codex
- Status: completed
- Branch / scope: `codex/saqlain/logic-core`; `src/memopops/certificates.py`, query API, checker runtime path, tests, README and Saqlain/master logs. Certificate generator is independent from the checker implementation; UI remains Mahavir-owned.
- Objective: implement bounded proof generation and independent context-bound verification for decisive query results; keep solver outcomes distinct from proof-budget outcomes.
- Decisions: deterministic Tseitin variables and initial clauses; unit-first bounded resolution; export only empty-clause ancestors. API defaults to certificate mode, checks solver witnesses and evidence IDs against separately loaded immutable memory, and returns VERIFIED only when the independent checker reports valid mathematics and MATCHED context. Store the bundle within the persisted query result so the workspace-authorized certificate route can reproduce it after a retry/restart; omit bundle bytes from ordinary query responses and hash-check them on export. Packaged Mahavir's standard-library checker as a local proofcheck dependency after the first live attempt exposed that test-only import paths did not work in normal API runs; moved its sources into the conventional packages/proofcheck/src/proofcheck layout without changing checker logic.
- Proxy: no Git or environment proxy configuration was present at task start. User requested proxy unset because the proxy was closed. Continue using direct HTTPS for GitHub and direct DB endpoint.
- Validation: `uv run --frozen --no-sync pytest -q` (113 passed); checker unittest suite (40 passed); compileall, Docker Compose config, `uv build --offline`, `git diff --check`, and installed-package import passed. Authenticated query against existing workspace_demo/rev_001 on hosted FalkorDB returned PROVED + VERIFIED with support as_api_v2, as_ready_rule, as_tests_pass; workspace-authorized export returned 23 clauses. One query receipt/result was persisted by the normal API. Proxy configuration and environment variables were absent. Live query timings showed about 3 seconds for snapshot loading on this hosted endpoint; no performance claim is made.
- Handoff: expose the new authenticated certificate endpoint in the live frontend, then implement dependency impact traversal and S5 fault/performance checks.
- Publication: commit `1fb90557b645fff9f840eedb69c58a14fb1aae00` pushed directly to `origin/main`; subsequent fetch and `git merge-base --is-ancestor` confirmed it. No PR was created.

## S-20261017-08

- Updated: 2026-10-17T17:24:00+05:30
- Human / agent: Saqlain / Codex
- Status: completed
- Branch / scope: `codex/saqlain/logic-core`; `src/memopops/store.py`, query persistence, API impact route, tests, README and Saqlain/master logs. No accepted memory or revision head changes planned.
- Objective: identify query results from a revision's parent that used removed/replaced assertions, prioritizing checked proof support and conservatively depending on all active assertions for solver-only or budget-limited results.
- Decisions: persist explicit `USES_PREMISE` edges with each immutable QueryResult; compute distinct impacted query count before applying a bounded ID cursor/page; require workspace identity in every impact query and keep old query statuses historical.
- Validation: `uv run --frozen --no-sync pytest -q` (119 passed); all 40 independent checker tests included; frontend `npm test -- --run` (7 passed); compileall, Compose config and diff checks passed. Hosted FalkorDB smoke created a fresh certified query, atomically linked its 3 checked support assertions, then created and deleted a temporary non-head revision that removed `as_ready_rule`; the workspace-scoped impact API found exactly that query, returned its historical status/support, and counted one result. Temporary revision was detached/deleted; workspace head and accepted memory were not changed.
- Handoff: expose impact summaries and certificate download in the revision UI after backend routes are available; then proceed to S5 fault and performance checks.
- Publication: commit `3c8f238407da3173181e0288ef3b79f9b501dbdc` pushed directly to `origin/main`; subsequent fetch and `git merge-base --is-ancestor` confirmed it. No PR was created.

## S-20261017-09

- Updated: 2026-10-17T17:25:30+05:30
- Human / agent: Saqlain / Codex
- Status: completed
- Branch / scope: `codex/saqlain/logic-core`; verification tests, API/store edge handling, release notes and Saqlain/master logs. No deployment or accepted-memory changes planned.
- Objective: close high-value deterministic fault/oracle gaps from the S5 verification matrix and measure persistence behavior that can be tested without Docker.
- Decisions: run an independent seeded truth-table comparison with 1,000 small solver cases, test head advancement during query and missing-database failure behavior, then verify query result/certificate replay across separate API lifespans on hosted FalkorDB. Docker-based container restart remains blocked if the engine is unavailable.
- Validation: `uv run --frozen --no-sync pytest -q` (122 passed), including 1,000 deterministic seeded solver-vs-truth-table cases; direct independent checker tests (40 passed); compileall, Compose config and diff checks passed. API fault tests confirm database unavailability returns 503 without fallback and a head advance during solve marks the response HISTORICAL. Hosted FalkorDB check closed the first API lifespan, started a fresh store/app, replayed the same idempotency request with the same query ID, reloaded the VERIFIED result, and exported its 23-clause certificate. Docker engine check failed because the Docker Desktop Linux-engine named pipe is absent; an actual local container restart remains unverified.
- Handoff: backend verification is complete; frontend integration, UI/API auth wiring, full correction walkthrough at r2, Docker restart on a host with its engine, and final video/submission rehearsal remain.
- Publication: code/tests/log commit `47882c9` is included in `origin/main` after fetch verification; direct push succeeded after restoring the Windows Git proxy. No PR was created.

## S-20261017-10

- Updated: 2026-10-17T17:33:29+05:30
- Human / agent: Saqlain / Codex
- Status: completed
- Branch / scope: `codex/saqlain/logic-core`; `src/memopops/api.py`, `tests/test_api.py`, and Saqlain/master logs. No frontend files changed.
- Objective: implement the authenticated GET /workspaces and GET /workspaces/{workspace_id} contracts needed by the live workspace gate and detail screen.
- Decisions: derive the sole discoverable workspace from the authenticated principal, never enumerate other tenant graphs; return 404 for a different workspace ID; use the current persisted head and principal role; expose memory write capability only to operator credentials. The seed has no display-label field, so label is the workspace ID until a label is added to the schema.
- Validation: `uv run --frozen --no-sync pytest -q` (124 passed); `git diff --check` passed. Tests cover authenticated listing/details, role capability, workspace isolation and missing bearer credentials. Frontend integration cannot yet succeed until its API client supplies an authorized bearer token.
- Handoff: Mahavir can integrate `listWorkspaces` and `getWorkspace` against these exact routes. Remaining UI work includes bearer-token session wiring, proposal review endpoint/UI, certificate download, impact display, and the end-to-end correction walkthrough. Reproduce backend checks with `uv run --frozen --no-sync pytest -q`.
- Publication: commit `ad5d9e2` and S09 commit `47882c9` were pushed directly to `origin/main`; fetching and confirming `ad5d9e2` as an ancestor of origin/main succeeded. No PR was created.

## S-20261017-11

- Updated: 2026-10-17T17:39:01+05:30
- Human / agent: Saqlain / Codex
- Status: completed
- Branch / scope: `codex/saqlain/logic-core`; `tests/test_api.py` and Saqlain/master logs.
- Objective: cover the new workspace discovery routes when FalkorDB is unavailable or the authorized workspace has no current head.
- Validation: `uv run --frozen --no-sync pytest -q` (126 passed). A read-only live smoke using `.env.cloud` returned HTTP 503 from both routes; an isolated `FalkorSnapshotStore.ping()` failed with `TimeoutError`, confirming this session cannot reach the database endpoint now. Credentials and endpoint values were not printed. No live workspace data was changed.
- Handoff: retry live workspace-list/detail smoke when the database endpoint is reachable; use the same authenticated GET requests as the S10 contract. Backend failure handling is covered and returns a generic 503.
- Publication: commit `d734a28` was pushed directly to `origin/main`; fetch and ancestor verification succeeded. No PR was created.

## S-20261017-12

- Updated: 2026-10-17T17:44:27+05:30
- Human / agent: Saqlain / Codex
- Status: completed
- Branch / scope: `codex/saqlain/logic-core`; `scripts/benchmark_solver.py`, `docs/performance/README.md`, raw result JSON, and Saqlain/master logs.
- Objective and success criteria: create and run a reproducible benchmark following the verification plan's fixed workloads, warm-up, 100 samples and three independent runs; clearly identify solver-only scope and record actual runtime metadata/results.
- Actions and decisions: keep database/API/certificate timing claims out of this report because FalkorDB is paused/unreachable and Docker is unavailable. Use a deterministic implication-chain workload and validate every answer as PROVED.
- Validation: smoke run passed at all four sizes. Full command `uv run --frozen --no-sync python scripts/benchmark_solver.py --output docs/performance/solver-baseline-2026-10-17.json` completed 10 warm-ups and 3×100 samples at 10, 50, 100, and 256 assertions. Every result was PROVED and no solver timed out. Combined nearest-rank p95 values were 12.220, 15.972, 19.260, and 29.591 ms respectively; p50 values were 8.591, 10.799, 12.522, and 20.513 ms. Recorded OS, CPU, Python, Z3 and benchmark source commit in the raw artifact. This excludes FalkorDB, API, certificate generation and independent checking.
- Handoff: after this measurement, integrate Mahavir's UI/model/evaluation changes when available and complete local release checks before retrying hosted database work.
- Publication: benchmark source `7c30d39` and report/raw samples `0d3dbd7` were pushed directly to `origin/main`; fetch confirmed `0d3dbd7` is an ancestor. No PR was created.

## S-20261017-13

- Updated: 2026-10-17T17:52:02+05:30
- Human / agent: Saqlain / Codex
- Status: completed
- Branch / scope: `codex/saqlain/logic-core`; new `.github/workflows/backend.yml` plus Saqlain/master logs. Existing Mahavir web/checker workflow was not changed.
- Objective and success criteria: run locked backend dependencies and meaningful backend tests on main pushes and pull requests, with read-only workflow permissions and no secrets.
- Actions and decisions: use the supported Python 3.12 project range and locked `uv` workflow. Include pytest, compile, checker suite and wheel/sdist build; do not require Docker or live FalkorDB credentials in CI.
- Validation: `uv sync --locked` passed; local workflow-equivalent commands passed: `uv run --locked pytest -q` (126 passed), compileall, independent checker unittest (40 passed), and `uv build`. After fetching/merging Mahavir's UI integration, `npm test` (8 passed), typecheck and production build passed. A Chrome browser smoke connected to the explicitly synthetic `MemorySnapshotStore` harness and obtained a verified `release_ready` result; it did not exercise FalkorDB or claim persistence. No secrets, database service, or Docker engine were required. `actionlint`, Ruby, and a local YAML parser are not installed, so the workflow received a manual syntax review; the first hosted GitHub Actions run is still pending.
- Handoff: actual hosted GitHub Actions run will provide the final CI execution evidence after push.
- Publication: workflow commit `a146df2` was pushed and is included in merge commit `fbfebcc` on `origin/main`; the integrated web checks passed after merge. Fetch and ancestor verification succeeded. No PR was created.

## S-20261017-14

- Updated: 2026-10-17T17:53:29+05:30
- Human / agent: Saqlain / Codex
- Status: completed
- Branch / scope: `codex/saqlain/logic-core`; root README and Saqlain/master logs.
- Objective and success criteria: give contributors an exact browser-smoke recipe that works while FalkorDB is offline and clearly states the harness is synthetic, in-memory, and non-persistent.
- Actions and decisions: document only the command sequence actually exercised with the committed build and Chrome; do not conflate it with the hosted database restart gate.
- Validation: the documented sequence passed locally: deterministic API harness, Vite preview, and Chrome CDP E2E query returned a verified `release_ready` result. The readme explicitly excludes FalkorDB persistence/restart and correction walkthrough claims.
- Handoff: local smoke is repeatable; retain actual FalkorDB persistence and correction-flow rehearsal as separate release gates.
- Publication: README/runbook commit `af58ed0` is on `origin/main`; fetch and ancestor verification succeeded. No PR was created.

## S-20261017-15

- Updated: 2026-10-17T17:57:15+05:30
- Human / agent: Saqlain / Codex
- Status: completed
- Branch / scope: `codex/saqlain/logic-core`; `src/memopops/store.py`, `src/memopops/api.py`, API/store tests, contract/README and Saqlain/master logs. No frontend edits.
- Objective and success criteria: implement a bounded, workspace-scoped read endpoint for existing quarantined revision submissions so a review client can inspect the exact submitted request without exposing credentials or suggesting that a proposal is accepted.
- Actions and decisions: return original validated mutation data as a pending submission; do not fabricate a minimal conflict core because the persistence format does not calculate one. Limit pages to 50 and restrict status to QUARANTINED.
- Validation: `uv run --locked pytest -q` (129 passed); `git diff --check` passed. Tests cover authenticated reads, role/workspace isolation, the 50-item bound, allowed status, request-data sanitization, and store query scoping/limit. The response excludes internal `actor_id` and does not invent conflicting assertion IDs.
- Handoff: the endpoint is `GET /api/v1/workspaces/{workspace_id}/proposals?status=QUARANTINED&limit=50`, returning `{proposals:[{proposal_id,status,base_revision_id,reason,created_at,submitted_request}]}`. `apps/web/src/api/types.ts` still describes the earlier proposal shape and should be updated before UI consumes this route. Exact conflict cores and model-proposed submissions remain separate work.
- Publication: code/docs/completion-log publication pending; no PR.
