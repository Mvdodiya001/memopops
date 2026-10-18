# Mahavir activity log

Task-level notes for Mahavir and agents working on his behalf. Times must include timezone. Edit this log only when working for Mahavir; do not infer identity from Git configuration.

## M-20261017-01

- Updated: 2026-10-17T16:52:49+05:30
- Human / agent: Mahavir / Grok 4.7
- Status: completed
- Branch / scope: `codex/mahavir/m1-m2` in a separate worktree. Files: `apps/web/`, `packages/proofcheck/`, `tests/proofcheck/`, `.github/workflows/web-proofcheck.yml`, this log, and the master index. Saqlain's service, `pyproject.toml`, `uv.lock`, Compose, and `.env.example` were not edited.
- Objective and success criteria: M0 review of the shared contract, then an interface foundation that renders the specified shapes only in an explicit development-fixture mode. API failures stay visible.
- Actions and decisions: Fetched `origin/main` and fast-forwarded Saqlain's backend commits through 1cc26ce before committing. The only overlapping untracked file was a local `.env.example`; it was removed so his published example remained. Fixture mode requires `source=development` and shows a persistent banner. Live mode has no fixture fallback. Provisional read types are documented in `apps/web/src/api/types.ts` until OpenAPI replaces them.
- Validation: `npm --prefix apps/web test` passed 7 tests. `npm --prefix apps/web run typecheck` passed. `npm --prefix apps/web run build` passed and emitted a separate fixture chunk. Headless Chrome wrote `apps/web/review/desktop-memory.png`, `desktop-query.png`, `narrow-memory.png`, and `live-error.png`. Browser end-to-end against a live API was not run; the service was not part of this change.
- Outcome / blockers: Fixture shell, memory, query, history, conflict review, and live error/retry states are in the web app. Hosted database credentials were not committed.
- Handoff: Saqlain can point the client at a running API with `VITE_API_BASE`. Do not treat development fixtures as backend data.
- Publication: fast-forwarded onto Saqlain's main, then pushed normally. A later fetch showed this branch and origin/main at the same commit. No force-push.

## M-20261017-02

- Updated: 2026-10-17T16:52:49+05:30
- Human / agent: Mahavir / Grok 4.7
- Status: completed
- Branch / scope: `packages/proofcheck/` and `tests/proofcheck/`. No new Python dependencies and no edits to `pyproject.toml`.
- Objective and success criteria: `check_certificate(bundle, expected_context=None)` validates original formulas, definition clauses, witnesses, resolution steps, support, and an optional trusted context. The package must not import Z3 or the certificate generator.
- Actions and decisions: The checker uses the standard library. Formula and knowledge hashes were aligned to the published service: `{"formula", "semantics_version"}` and `{"assertions": [[id, formula_hash]], "semantics_version"}`. Without `--expected-context`, the CLI reports provenance unverified. Development certificate vectors live in `tests/proofcheck/vectors/` and are labeled as fixtures.
- Validation: `PYTHONPATH=packages python -m unittest discover -s tests/proofcheck -q` passed 40 tests. A separate process imported `memopops.formula.formula_hash` and `memopops.store.calculate_knowledge_hash` and compared them with the checker for atom `p`; both hashes matched. `proofcheck` does not import `z3`. Saqlain's pytest suite was not rerun because those modules were unchanged by this merge.
- Outcome / blockers: Decisive demo vectors for revision 1 PROVED and revision 2 REFUTED pass with a trusted context. Certificate search and API export remain in Saqlain's generator milestone.
- Handoff: Call `check_certificate` with a context loaded independently of the bundle. Run `PYTHONPATH=packages python -m proofcheck CERTIFICATE.json --expected-context MANIFEST.json`.
- Publication: same push as the inspector milestone. Fetch after the push confirmed the commit is contained in origin/main.

## M-20261017-03

- Updated: 2026-10-17T18:10:00+05:30
- Human / agent: Mahavir / Grok 4.7
- Status: completed
- Branch / scope: `codex/mahavir/m3-live-ui`. Files: `apps/web/` only, plus this log and the master index. Saqlain's API, store, benchmark script, `pyproject.toml`, and checker sources were not edited. Fast-forwarded his commits through the solver benchmark before committing.
- Objective and success criteria: Connect the inspector to the published endpoints. Keep fixture mode explicit. Do not treat a failed API call as fixture data.
- Actions and decisions: Live mode asks for a bearer token kept in page memory, then calls `GET /workspaces` and `GET /workspaces/{id}` for the authorized workspace, head revision, and operator write capability. Memory uses `revision_id`. History reads `items`. Queries use `proof_mode=certificate`. A verified result can download `GET .../queries/{id}/certificate`. A 409 keeps the form and asks for review before another submit. The dev server proxies `/api` to the local API.
- Validation: `npm --prefix apps/web run typecheck` passed. `npm --prefix apps/web test` passed 8 tests. `node apps/web/e2e/live-query.mjs` passed: the browser connected, queried `release_ready`, and showed “Follows from memory” and “Proof verified” without the development-fixture banner. That browser check used `apps/web/e2e/harness.py`, an in-memory snapshot behind the published FastAPI routes, because Docker Hub timed out pulling FalkorDB and a direct connection to the hosted database timed out from this machine. It is not a FalkorDB persistence test.
- Outcome / blockers: Live memory, history, certificate query, and download are wired. Hosted FalkorDB end-to-end from this machine remains blocked by a connection timeout. No credentials were committed.
- Handoff: Run the API with the ignored `.env` / `.env.cloud` settings Saqlain already uses, then open the web app without `source=development`. Reader tokens cannot activate memory. Operator tokens can try a revision write; the service still decides.
- Publication: feature commit `5671884` is contained in `origin/main` (verified with `git merge-base --is-ancestor`). No further M3 code push was required. Revalidated on current `origin/main` at `91d2abd`: `npm --prefix apps/web ci`, `typecheck`, `test` (8 passed), and `build` all passed. Browser E2E was not rerun in this session; prior harness result remains the recorded smoke evidence.

### Publication correction 2026-10-17T18:10:00+05:30

Earlier text said publication was pending; the live UI integration was already merged to main before this correction. This entry records the verified remote inclusion and the repeat web checks above.

## M-20261017-04

- Updated: 2026-10-17T18:28:00+05:30
- Human / agent: Mahavir / Grok 4.7
- Status: completed
- Branch / scope: `codex/mahavir/m4-agents`, fast-forwarded through Saqlain commits through S-20261017-18 (`40a446b`). Files: `agents/`, `evaluation/`, `tests/test_agent_sessions.py`, this log, and the master index. Did not edit `src/memopops/`, `pyproject.toml`, or `apps/web/`.
- Objective: deterministic writer and reader clients against the published memory API, recording reader decisions through Saqlain's `POST /decisions` endpoint, plus a small acceptance evaluation and scripted-replay baselines. Live model calls stay disabled unless credentials exist.
- Actions and decisions: merged latest `origin/main` before work to avoid backend conflicts. Reader `record_decision` maps ship/hold to `PROCEED`/`BLOCK`; abstain stays journal-only. Operator corrections use trusted fixture revisions outside the writer tool allowlist.
- Validation: `uv run --locked pytest -q` (136 passed, including 3 new agent/acceptance tests). Pytest exercises the acceptance path via `evaluation.acceptance.run_acceptance`. No FalkorDB or live model run.
- Handoff (closed): live UI wires `GET /proposals` and `POST /decisions` (M-04/M-05). A read-only decision list API does not exist yet; no further Mahavir UI task until Saqlain adds one. Live model adapter stays optional behind env credentials.
- Publication: merged to `origin/main` as `be55565` with UI proposals/decision wiring, demo script, and evaluation docs.

## M-20261017-05

- Updated: 2026-10-17T18:31:00+05:30
- Human / agent: Mahavir / Grok 4.7
- Status: completed
- Branch / scope: `main`; `apps/web/` impact/history, `evaluation/lab_store.py`, `scripts/verify_release.sh`, `docs/DEMO.md`, `docs/SUBMISSION.md`, `docs/evaluation/acceptance-sample-report.json`, tests and logs. No `src/memopops/` edits.
- Objective: close remaining P0 presentation gaps — revision impact in the live UI, lab impact parity, writer/quarantine tests, release verification script, demo/submission docs, and a committed acceptance sample.
- Validation: `uv run --locked pytest -q` (138 passed); web typecheck and 8 vitest tests passed; `evaluation.run --suite acceptance` (4/4 cases passed).
- Handoff: run `./scripts/verify_release.sh` before submit; record demo video per `docs/DEMO.md`; FalkorDB persistence/restart and live model remain optional.
- Publication: pushed to `origin/main` as `434ad4e` after validation (`merge-base` confirmed).

## Lane status (2026-10-17T18:38:00+05:30)

- Active implementation tasks: **none** (M-20261017-01 through M-20261017-05 are **completed** and on `origin/main`).
- Out of scope for this lane: hackathon registration, demo video/screenshots, optional FalkorDB restart smoke, optional live model demo — see `docs/SUBMISSION.md` and `docs/DEMO.md`.

## M-20261018-01

- Updated: 2026-10-18T13:04:22+05:30
- Human / agent: Mahavir / Cursor
- Status: ready-for-review
- Branch / scope: `codex/mahavir/video-demo`; `agents/gemini_tools.py`, `scripts/demo_video.py`, `scripts/reset_demo_workspace.py`, focused tests, demo/readme documentation, and logs. Existing API, solver, store, checker, and UI behavior remain unchanged.
- Objective: implement the approved video plan in `docs/plan/VIDEO_DEMO_PLAN.md`: Gemini Flash native function calling through the existing guarded `AgentSession`, a deterministic narrated scene runner with truthful scripted fallback, a safe retake reset, and reproducible demo documentation.
- Success criteria: live and scripted scenes use the published service contracts; secrets never enter artifacts or tracked files; model calls remain bounded and role-scoped; tests cover adapter mapping and the scripted correction flow; `scripts/verify_release.sh` passes.
- Actions and decisions: added a native Gemini function-calling adapter with per-role allowlists, function-response chaining, bounded retry/backoff, argument mapping into the unchanged `AgentSession` contract, and redacted transcript summaries. Added a nine-scene narrated runner, guarded reset of only `workspace_demo`, certificate tamper check, and graph-query artifacts. Writer credentials remain unable to activate memory; the demo shows denial followed by a distinct operator validation that quarantines the conflict. The uncertainty scene uses solver mode because UNKNOWN has no decisive certificate.
- Validation: focused adapter/runner/agent tests passed (13); full pytest passed **152** tests; independent checker suite passed 40; web typecheck, 8 Vitest tests, production build, and 4/4 lab acceptance passed through `./scripts/verify_release.sh`. A live Gemini reader used `inspect_memory`, `query_conclusion`, and `record_decision` to produce `ship`/PROVED with no fallback. A full scripted run against real local FalkorDB covered all nine scenes, proofcheck exit 0, tampered proofcheck exit 1, and both Cypher queries; the guarded reset returned the demo graph to `rev_001`.
- Known gap: a multi-scene live-model lab rehearsal completed the product outcomes but truthfully used scripted fallback for some scenes after transient model runtime errors; a separate live uncertainty scene completed UNKNOWN/abstain. Recording day must run the live dry run first and keep every live/replay banner visible.
- Files: `agents/gemini_tools.py`, `agents/client.py`, `scripts/demo_video.py`, `scripts/reset_demo_workspace.py`, `tests/test_gemini_tools.py`, `tests/test_demo_video.py`, demo/submission/readme docs, `.env.example`, and logs. No secret file or key was changed or staged.
- Handoff: review the terminal verbosity and narration, configure the hosted FalkorDB values privately, run reset plus scripted/live dry runs, then record with `--pause`. The video itself, screenshots, upload, signed-out check, and organizer submission remain human tasks.
- Publication: implementation committed locally as `7e4999f`; `origin/main` was current and the post-merge release gate passed, but `git push origin HEAD:main` was rejected because this checkout has no GitHub credentials. The GitHub CLI is not installed, so publication remains pending authenticated access.

## M-20261018-02

- Updated: 2026-10-18T13:52:58+05:30
- Human / agent: Mahavir / Cursor
- Status: ready-for-review
- Branch / scope: `codex/mahavir/adaptive-video-demo`; `scripts/demo_video.py`, its focused tests, demo documentation, and logs. No API, store, solver, checker, or schema changes.
- Objective: remove the video runner's accidental `rev_001` runtime assumption, make repeated public-repository walkthroughs easy and safe, and retain an explicit validation that the selected baseline has the canonical demo facts required by the correction story.
- Success criteria: runtime head drives reads, writes, certificate naming, and graph queries; an opt-in reset supports repeat takes; invalid baseline state produces an actionable error; focused and release checks pass.
- Actions and decisions: the runner now discovers and validates the current canonical baseline through the API, carries that revision through operator writes and graph queries, names certificate artifacts from the runtime revision, and exposes `--reset` to delete/reseed only `workspace_demo`. Canonical atom/assertion names remain intentional scenario inputs; endpoints, credentials, model mode, take, and baseline revision are runtime values.
- Validation: adaptive focused tests passed (9); the complete scripted nine-scene flow passed against local FalkorDB/API using `--reset`, including quarantine, correction, impact, stale-decision recovery, valid/tampered proofcheck exits 0/1, and dynamic graph queries; the workspace was reset to the canonical baseline afterward. `./scripts/verify_release.sh` passed 153 pytest, 40 checker tests, web typecheck, 8 Vitest tests, production build, and 4/4 acceptance. Node 20 still emits the existing Vitest Node 22.12+ engine warning.
- Handoff: for repeat takes use `scripts/demo_video.py ... --reset`; omit `--reset` to preserve the current graph. Environment variables intentionally override `.env`, so clear stale exported FalkorDB settings or pass the active host/port explicitly.
- Publication: implementation commits are local (`6540ef3`, `e5db90b` plus handoff updates); the branch was current with `origin/main` and passed post-merge checks, but push remains blocked because this checkout has no GitHub HTTPS credentials.
- Follow-up: a manual live take appeared frozen at scene 2 because the first Gemini HTTPS response remained silent inside the 60-second socket timeout; the human interrupted it before fallback. Add visible request/retry status and a bounded configurable live-model timeout so a provider stall is observable and falls back promptly.
- Follow-up outcome: live calls now print attempt/timeout/retry status, default to 10 seconds with one retry, and accept `--model-timeout` or `MEMOPOPS_MODEL_TIMEOUT_SECONDS`. A real live smoke exposed two provider timeouts followed by Google HTTP 429 quota exhaustion; the runner labeled and completed the reader scene with scripted fallback instead of hanging. Focused tests passed (10), and the release gate passed 154 pytest, 40 checker tests, web typecheck, 8 Vitest tests, production build, and 4/4 acceptance.
