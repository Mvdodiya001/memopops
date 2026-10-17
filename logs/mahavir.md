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

- Updated: 2026-10-17T17:44:06+05:30
- Human / agent: Mahavir / Grok 4.7
- Status: completed
- Branch / scope: `codex/mahavir/m3-live-ui`. Files: `apps/web/` only, plus this log and the master index. Saqlain's API, store, benchmark script, `pyproject.toml`, and checker sources were not edited. Fast-forwarded his commits through the solver benchmark before committing.
- Objective and success criteria: Connect the inspector to the published endpoints. Keep fixture mode explicit. Do not treat a failed API call as fixture data.
- Actions and decisions: Live mode asks for a bearer token kept in page memory, then calls `GET /workspaces` and `GET /workspaces/{id}` for the authorized workspace, head revision, and operator write capability. Memory uses `revision_id`. History reads `items`. Queries use `proof_mode=certificate`. A verified result can download `GET .../queries/{id}/certificate`. A 409 keeps the form and asks for review before another submit. The dev server proxies `/api` to the local API.
- Validation: `npm --prefix apps/web run typecheck` passed. `npm --prefix apps/web test` passed 8 tests. `node apps/web/e2e/live-query.mjs` passed: the browser connected, queried `release_ready`, and showed “Follows from memory” and “Proof verified” without the development-fixture banner. That browser check used `apps/web/e2e/harness.py`, an in-memory snapshot behind the published FastAPI routes, because Docker Hub timed out pulling FalkorDB and a direct connection to the hosted database timed out from this machine. It is not a FalkorDB persistence test.
- Outcome / blockers: Live memory, history, certificate query, and download are wired. Hosted FalkorDB end-to-end from this machine remains blocked by a connection timeout. No credentials were committed.
- Handoff: Run the API with the ignored `.env` / `.env.cloud` settings Saqlain already uses, then open the web app without `source=development`. Reader tokens cannot activate memory. Operator tokens can try a revision write; the service still decides.
- Publication: pending the push after this commit.
