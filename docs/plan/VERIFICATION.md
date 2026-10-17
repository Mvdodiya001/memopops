# Verification, measurements and demo

No application tests have run yet. This is the acceptance specification to implement. Planning-only mathematical/style checks are recorded separately in VALIDATION.md.

## 1. Independent oracles

For formulas over ≤6 atoms, enumerate all 2^n assignments with a small independent AST evaluator. Derive SAT(K), entailment and refutation from those assignments. Compare Z3 classifications over at least 1,000 seeded bounded formula/query pairs. Include nested NOT/AND/OR/IMPLIES/IFF, duplicated subformulas, tautologies and contradictions. Keep random seeds and failing inputs.

Exhaustively check each Tseitin local operator template for all assignments to its arguments and extension variable. For complete small formulas, check that each original assignment extends to the compiled CNF exactly when the original formula is true (with its root asserted). This catches incorrect templates and missing root units. Use an independent evaluator, not the compiler to test itself.

Certificate generation and checking must not share the resolution/encoding implementation. Test both directions where feasible: legitimate certificates pass; mutations of trusted assumptions, binding and inference fail. A valid SAT witness for K is required for a decisive independently checked result.

## 2. Acceptance matrix

| ID | Case | Expected behavior | Owner |
| --- | --- | --- | --- |
| L01 | P, P→Q, Q→R; query R | PROVED | S |
| L02 | Same K; query NOT P | REFUTED | S |
| L03 | Registered unrelated D | UNKNOWN; two valid witnesses | S/M |
| L04 | Imported P AND NOT P | INCONSISTENT_MEMORY, no arbitrary conclusion | S |
| L05 | Empty K; tautology / contradiction | PROVED / REFUTED respectively | S |
| L06 | Timeout/solver indeterminate | SOLVER_UNKNOWN, never logical UNKNOWN | S |
| L07 | Unregistered atom / excess depth / wrong arity | 422 before solver | S |
| L08 | Missing fact | No closed-world negation | S/M |
| L09 | Retract Q from demo r1 without NOT Q | Release readiness UNKNOWN | S/M |
| P01 | Demo PROVED and REFUTED bundles | Independent checker VERIFIED | M/S |
| P02 | Wrong pivot/parent/resolvent or forward reference | Reject certificate | M |
| P03 | Extra initial premise, missing root or changed query | Reject certificate | M |
| P04 | Altered revision versus trusted expected context; altered hash/map/witness | Reject binding or mathematics as appropriate; no-context CLI labels provenance unverified | M |
| P05 | Search budget exhausted | Logical result preserved, certificate unavailable | S/M |
| P06 | Checker raises/fails internally | Integrity error; no trusted answer | S/M |
| G01 | Restart API and database; cold cache | Same revision/evidence/proof restored | S |
| G02 | Database disconnected | 503; no fixture/in-memory fallback | S/M |
| G03 | Hash mismatch/duplicate workspace singleton | Fail readiness for affected workspace | S |
| G04 | User A addresses user B's IDs | No access/data disclosure | S/M |
| C01 | Simultaneous P and NOT P from same base | At most one commit; loser stale/conflict; K stays SAT | S |
| C02 | Simultaneous compatible writes from same base | One first commit; other explicit retry produces next revision | S |
| C03 | Same key/payload repeated; response lost | Same outcome, no duplicate revision | S |
| C04 | Same key/different payload | 409 idempotency conflict | S |
| C05 | Fault during publishing query | Old or complete new revision, never partial accepted state | S |
| C06 | Cancellation/timeout while waiting or solving | No leaked queue slot/unbounded orphan process | S |
| C07 | Head advances while query solves | Result bound to original revision and labeled appropriately | S/M |
| C08 | Head advances before decision write | 409, reader rechecks | S/M |
| C09 | Correction alters proof support | Graph identifies affected prior result; recheck may change result | S/M |
| C10 | Earlier UNKNOWN plus new fact | Fresh query recomputes, not stale cache reuse | S |
| A01 | Writer/reader roles and resumed session | Reader uses persisted updated memory; cannot activate premises | M |
| A02 | Malformed/ambiguous model formula | Reject or pending review; no implicit acceptance | M/S |
| A03 | Model text requests unrelated execution | Tool/schema allowlist holds | M |
| U01 | All logical/proof/freshness states | Correct distinct copy and action availability | M |
| U02 | Late r1 response after r2 selection | No r1 content under r2 heading | M |
| U03 | 409 while editing correction | Preserve input, refresh, review before retry | M |
| U04 | Keyboard, 200% zoom, narrow width, reduced motion | Main workflow remains usable | M |
| U05 | Real service outage in production mode | Visible error; mock mode never activates | M |

For concurrency tests, use a barrier so both clients read the same base before publication. Repeat adversarial schedules, not just simultaneous starts that accidentally serialize. Fault injection belongs in test-only hooks, disabled in release. Inspect final persisted state, not only HTTP status codes.

## 3. Evaluation that is fair and informative

Use three systems on the same synthetic scenarios:

1. **Naive shared notes:** append observations and cache the last answer; no proof/revision validation. Report unsupported safety capabilities as absent, not as invented numerical failures.
2. **Solver-only ablation:** same ASTs, Z3 and full knowledge, but the test harness deliberately omits guarded publication/revision-aware cached answers. This isolates coordination failure from reasoning quality. Clearly label this intentionally weakened experimental baseline; it is never a deployable mode of the service.
3. **memopops:** complete revision protocol, dependency tracking and checker.

Do not claim these baselines represent all existing agent-memory products. No competitor benchmark or novelty claim is established by them. Separate ordinary query accuracy from stale-answer prevention and write consistency. Keep correct cases as well as failures in the workload.

Workloads: deterministic demo, acceptance matrix, seeded Boolean oracle corpus, 100 correction sequences, and 100 two-writer races in isolated temporary workspaces. Sizes: 10, 50, 100 and 256 active assertions; distinguish tiny demo certificates from larger solver-only cases. Include both relevant and irrelevant added facts, replacement, alternative supports and UNKNOWN becoming PROVED.

Metrics:

- Semantic classification accuracy against the independent oracle, per class.
- False decisive answers (PROVED/REFUTED when oracle disagrees): target zero on tested cases.
- Abstentions/timeouts reported separately; never count all abstentions as correctness.
- Invalid accepted revisions, stale answers labeled current and duplicate commit count: target zero.
- Valid certificate acceptance; mutated-certificate rejection; certificate coverage and budget failures.
- Latency p50/p95 with sample count, successes/failures and timeout count; DB, solver, generator and checker phases separately.
- Affected-query count and rechecks scheduled; do not claim complete maintenance from support traversal alone.
- Restart retention and cross-workspace leakage tests.

Starting experience targets, not promises: on the reference host and demo-sized K, p95 ordinary query <750 ms excluding model latency, certificate query <2 s, read/list <250 ms, correction <1 s. These targets may fail; publish observed values and limits. Worst-case Boolean solving remains expensive.

Measurement protocol: record commit, OS, CPU/RAM, image digest, solver/library versions and persistence settings. Warm up 10 operations, then measure at least 100 per workload; repeat three runs. Separate cold-start from warm runs. Fixed seeds, fixed models/settings, same data and environment across baselines. Report raw JSON/CSV plus a short table. Quantiles exclude neither failures nor timeouts silently: give successful-response quantiles alongside counts and deadline-censored outcomes. Never mix model network time into solver speed claims without labeling it.

## 4. CI and release commands

Saqlain establishes backend lint/core/property/DB integration workflow; Mahavir establishes web typecheck/build/E2E and checker tests. Trigger real integration tests against the pinned database, not mocks only. Exclude secret-dependent live model tests from default CI; deterministic tool-schema and replay tests still run.

CI checks should enforce behavior, not the presence of a string in code. Run relevant checks locally before opening pull requests and rely on configured CI as an additional gate. Existing protections still apply. Do not claim enforcement from a Markdown rule.

Release gate: all P0 cases pass; no untriaged correctness or data-isolation failure; no misleading verified badge; normal restart works; fresh clone setup succeeds; documented limitations agree with the UI. A proof failure, accepted inconsistency, stale-current leak or cross-workspace leak is a stop-ship defect. A missing optional theme or fancy graph is not.

## 5. Demo storyboard (about 3 minutes, adjust to organizer limits)

1. **0:00–0:20 — Problem.** “Agents share memory. When an observation is corrected, old conclusions can outlive their evidence.” Show the accepted assertions and two client identities.
2. **0:20–0:55 — Proof.** Reader asks release_ready. Show Follows from memory, revision, three supporting assertions and a short verified proof. Open one evidence record.
3. **0:55–1:15 — Honest uncertainty.** Ask docs_signed. Show Not established and explain that absence is not false.
4. **1:15–1:45 — Conflict.** Writer proposes tests failed while tests passed remains active. Show quarantine and unchanged head. Operator explicitly replaces the old report.
5. **1:45–2:15 — Shared correction.** Graph impact identifies the old result's support. Reader resumes a new session, reads r2 and gets REFUTED due to the explicit failure rule. Old proof remains valid only for r1.
6. **2:15–2:40 — Verification.** Export certificate, run independent checker, alter a step and show rejection. Display one measured race-test/result table with honest sample counts.
7. **2:40–3:00 — Graph and limits.** Show the actual premise/evidence graph query and a restart-retained record. State that logical validity depends on accepted premises and that the prototype is bounded.

Record real execution. If using deterministic replay, label it. If live model calls succeed, show mode/provider and sanitized tool events. Do not stage a model conversation or precomputed counter as a live result. Capture an uninterrupted fallback locally before experimenting with deployment.

## 6. Submission checklist

The official rules require central FalkorDB use, public code, setup/data model, core queries/algorithms, a working video, deployment or complete local instructions, named track, and AI-assistance disclosure [R1]. Keep this list concise in README; the organizer page is authoritative.

- Confirm team registration and correct members; do not assume a repository collaborator is registered.
- Name Track 02. Confirm repository is accessible to judges and the submitted commit is final.
- README: clear problem, real screenshots, setup with placeholders, schema/queries, demonstration instructions, measured evaluation, limits, contribution/AI disclosure.
- Verify the video link in a signed-out browser. Verify deployment or a clean local install on Mahavir's machine.
- Both humans explain one Cypher traversal, the entailment test, the revision guard and what the checker verifies.
- Agree repository licensing/ownership explicitly; do not silently add a license based on a third-party claim.
- Team member submits early and checks receipt before 23:59 IST October 18. This plan does not perform registration/submission.
