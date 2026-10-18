# Correctness audit — October 18, 2026

Task S-20261018-05, Saqlain / Codex. Audited starting point: `dd8f958`. This is a code review and regression audit of the implemented MVP, not a formal proof that the entire application is defect-free.

## Scope

Reviewed the production paths for API authentication/workspace isolation, request limits, immutable revisions and evidence, graph writes and receipts, query classification, certificate generation/independent checking, agent tool/session handling, live model argument mapping, recorded-run import, frontend observer/query/mutation state, CLI workflows, packaging, Compose and CI configuration. Checked actual implementations against current contracts rather than treating old planning documents as implemented features.

The propositional solver's existing test compares 1,000 seeded cases with a separate truth-table evaluator. The independent checker reconstructs the encoding, checks the complete initial clauses and resolution steps, checks consistency witnesses, and binds service certificates to trusted snapshot context. These tests passed. This audit found concrete defects mainly in integration, malformed-input handling, and client workflows.

## Defects corrected

| ID | Defect before correction | Correction and regression evidence |
| --- | --- | --- |
| A01 | UNKNOWN queries in default certificate mode returned HTTP 500: the API sent plain formula ASTs to a checker expecting assertion records. | Send ID/formula/evidence-ID records. API test now verifies both witnesses and retains UNKNOWN with no decisive certificate. A deliberately false knowledge witness still fails verification and is not persisted. |
| A02 | Non-string formula operators, certificate results, and model action/choice/proof-mode values could reach hash-set membership and raise TypeError. | Validate enum types before membership, and safely classify malformed model actions. Service parser, API, independent checker and agent regressions cover arrays/objects and other invalid types. |
| A03 | An authenticated lookup of a non-ASCII workspace path crashed in string-only constant-time comparison. | Compare UTF-8 bytes; inaccessible Unicode workspace paths return 404. Configured role types are also checked before membership. |
| A04 | The live adapter used Python truthiness for negation: the string `"false"` became `True`, reversing the formula. | Require actual Boolean negation values; malformed model arguments fail before execution. Seven coercion cases are covered. |
| A05 | The web UI could suggest a decisive action when the requested certificate failed or exceeded its budget. | Match the agent policy: decisive suggestions require VERIFIED or explicit solver-only NOT_REQUESTED. UNKNOWN and solver-indeterminate results never generate a suggestion. Unit tests and an injected browser budget response cover this. |
| A06 | Each browser decision retry generated a new idempotency key. A lost successful response could create duplicate receipts on retry. | Keep one key per query-bound decision component. Browser test loses a response after the server commits, retries, and verifies identity reuse. Query changes reset decision UI state. |
| A07 | The operator Add memory form always sent `evidence: []`, which the service correctly rejected. Its request type also incorrectly required a server-generated evidence ID. | Require a URI, source excerpt and observation time; convert local time to UTC and let the service assign IDs. Extended Chrome check successfully commits an evidence-backed observation. |
| A08 | The advertised default lab replay checked external credentials before configuring synthetic identities, so it failed on a fresh environment or unrelated token configuration. | Configure isolated process-local identities before the lab run. Remote mode still validates its supplied credentials. Tests cover both absent and unrelated environment configuration; README startup is updated. |
| A09 | Acceptance CLIs printed failed-case totals but could exit successfully, allowing a release shell gate to continue after a failed evaluation. | Exit nonzero for failed/empty suites in both CLI entry points. A mocked failed-case regression verifies the evaluation CLI; the normal 4/4 suite still exits successfully. |
| A10 | JSON nesting beyond the decoder's recursion limit could terminate the checker CLI with a traceback instead of its structured invalid-input report. | Catch decoding RecursionError and return the existing invalid-input exit code 2. A deeply nested synthetic file is covered by the standalone CLI suite. |
| A11 | A configured native model proxy ending in `/models` was silently replaced with the default Google endpoint. | Preserve explicit native model base URLs; a custom-base regression verifies routing without making a model request. |
| A12 | Agent clients interpolated workspace/revision/query identifiers directly into URLs, so reserved characters could change the path or query parameters. | Encode path identifiers and query parameters consistently with the web client. A captured-transport regression verifies reserved-character handling. |
| A13 | Malformed percent escapes in a browser workspace URL could throw during routing and blank the app. | Treat the malformed workspace as unselected so the connection screen remains usable; route regression covers malformed and correctly encoded input. |

Failing tests reproduced the input, witness, coercion and CLI defects before their fixes. The UI defects were checked against the real frontend and published API routes using the isolated synthetic harness. No production database was reset or mutated in this audit.

## Verification

Final commands and counts are recorded in [Saqlain's log](../logs/saqlain.md#s-20261018-05). The audit exercised:

Final internet-enabled verification on October 18: 182 pytest tests and 3 subtests passed; 42 standalone checker tests passed; 30 frontend tests, TypeScript checking and the production build passed; acceptance passed 4/4. Locked dependency installation, Python compilation, source/wheel packaging, Compose parsing, and both Chrome suites passed. npm audit against the official registry and pip-audit of installed non-editable dependencies reported no known vulnerabilities. The two editable project packages were covered by the code review/tests rather than the advisory scan.

Implementation commit `87e3ba2` is published on main. Hosted [backend CI](https://github.com/Mvdodiya001/memopops/actions/runs/39122720006) and [web/checker CI](https://github.com/Mvdodiya001/memopops/actions/runs/39122720020) both completed successfully for that commit.

- Full pytest suite, including the 1,000-case truth-table comparison and new regressions.
- Standalone standard-library independent-checker tests.
- Frontend TypeScript, Vitest and production build.
- Scripted acceptance suite, package wheel/source-distribution build, compileall, and Compose configuration parsing.
- Extended Chrome test: live query/support, UNKNOWN certificate mode, lost decision response/retry, unchecked-certificate gating, evidence-backed operator addition, quarantine polling, head following, pinned history, revision impact, all recorded chapters, malformed-file recovery, responsive focus and reduced motion. Replay issues zero mutation requests.
- 3,000 deterministic mutations of a supplied synthetic certificate, replacing fields with malformed JSON values; no unhandled checker exceptions occurred. This is additional robustness coverage, not exhaustive proof verification.

Browser artifacts and test outputs are kept under ignored `.artifacts/`. The test service uses LabSnapshotStore and actual scripted DemoRunner artifact formats. This validates integration and presentation; it is not evidence of FalkorDB persistence or real live-model execution.

Separate real-cloud verification succeeded with the previously supplied endpoint and cloud credential, applied only within the verification processes. The configured local `.env` instead targets an inactive localhost database. The existing cloud demo snapshot passed read-only integrity validation. Two uniquely named disposable workspaces then exercised the complete nine-scene scripted demo (including independently accepted/tampered certificate exits 0/1 and actual graph dependency queries), UNKNOWN certificate-mode witness verification, query/certificate/snapshot recovery through fresh store/API instances, tenant isolation, and concurrent incompatible revisions. The concurrent requests returned 201 and 409, with exactly one head advance. Both disposable graphs were removed; the original demo workspace was not modified. A preliminary ad hoc recovery request used incorrect field names and correctly received 422; the follow-up used the published request schema and passed. This was a verification-script correction, not an application change. Reports are under ignored `.artifacts/cloud-audit/`.

## Remaining verification limits and intended semantics

- Earlier localhost readiness failed because no local database is running. Cloud graph publication, concurrency, proof checking and fresh-client recovery now pass as described above. Docker Desktop's Linux engine remains unavailable, so an actual database/container restart was not tested. A fresh client/API connection does not establish recovery after a database process restart.
- A live model probe found no configured model API key in this checkout, so no Gemini HTTP request could be made. Adapter mapping, retries and bounded behavior were tested with controlled responses. A recording must retain actual live/scripted/fallback labels.
- The decisions API records an authenticated, revision-bound choice; it is not itself a policy engine or deployment executor. It intentionally permits audit choices such as conservative BLOCK despite a PROVED result. The agent and suggested frontend actions enforce their matching-result/proof policy. Do not describe the API alone as enforcing every decision policy.
- Query freshness records the head observed at the query's original read. A retrieved historical result must be compared with a fresh workspace head; the frontend does this. A journal's local current decision is likewise not a promise that the database head has never changed.
- Certificates establish formal consequences of accepted premises, not factual truth or the correctness of an LLM's translation. Evidence and imported run artifacts are not cryptographically authenticated.
- Dependency advisory scans found no known vulnerabilities at verification time; they are not a penetration test or exhaustive security assessment. This task did not perform an exhaustive load test. Optional large-graph layout and automated recording features remain outside the MVP.

The corrected checks and scripted cloud rehearsal pass within these boundaries. A real live-model rehearsal and the final video recording remain required before claiming those delivery steps are complete.
