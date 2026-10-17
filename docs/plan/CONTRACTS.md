# Shared contracts v0.1

This is the proposed implementation contract. At G0, Saqlain turns it into Pydantic/OpenAPI models and versioned fixtures; Mahavir checks the fixtures and generates TypeScript types. Freeze those files before parallel implementation. No endpoint described here is implemented yet.

## 1. Identity, IDs and boundaries

- API prefix `/api/v1`; opaque string IDs; timestamps RFC3339 UTC in storage/API, local display in UI.
- `semantics_version = "boolean-v1"`; `certificate_version = "resolution-v1"`.
- Authenticate server-side. Map credential to actor/allowed workspace/role. Do not trust actor or tenant supplied in a mutation body.
- Development credentials: two separate writer/reader identities, stored in local environment. A single public read-only identity may expose only synthetic demo data. No production claim about full account management.
- Browser must never contain the database password or LLM provider key. If local operator token login is needed, keep the short-lived token in memory; public mode is read-only.
- Cross-workspace unknown IDs return 404 without leaking existence. Malformed data returns 422. Validation happens again server-side even if TypeScript types agree.

## 2. Formula AST

```ts
type Formula =
  | { op: "atom"; id: string }
  | { op: "not"; arg: Formula }
  | { op: "and" | "or" | "implies" | "iff";
      args: [Formula, Formula] };
```

No optional unknown properties. Formula language excludes raw Cypher, SMT-LIB, arbitrary source URLs to fetch, and executable text. Evidence URIs are metadata, not instructions to make network calls.

Example `(api_v2 AND tests_pass) IMPLIES release_ready`:

```json
{"op":"implies","args":[{"op":"and","args":[{"op":"atom","id":"api_v2"},{"op":"atom","id":"tests_pass"}]},{"op":"atom","id":"release_ready"}]}
```

Atom registration includes `id`, `label`, `meaning`, `scope`. Register all four demo atoms up front. Scope belongs to the workspace; a revision says what is accepted at that snapshot, not a universal statement across all time.

## 3. Endpoint list

| Method/path (beneath /api/v1) | Purpose / important behavior |
| --- | --- |
| GET /health/live | Process liveness; no sensitive config. |
| GET /health/ready | DB/schema/worker readiness; 503 if unavailable. |
| GET /workspaces | Only authorized workspace summaries. |
| GET /workspaces/{w} | Head revision, label, limits, role/capabilities. |
| POST /workspaces/{w}/atoms | Operator registers immutable atom meanings; idempotent exact duplicate, conflict on different meaning. |
| GET /workspaces/{w}/memory?revision={r} | All active assertions under bounded MVP; include atom registry, evidence summaries, knowledge hash. |
| POST /workspaces/{w}/revisions | Atomic mutation batch; expected revision and idempotency key required. |
| GET /workspaces/{w}/revisions?cursor=... | Stable sequence-ordered history, page size ≤50. |
| POST /workspaces/{w}/queries | Evaluate AST against required explicit revision; persist QueryResult. |
| GET /workspaces/{w}/queries/{q} | Stored result, freshness observation, premises/evidence; no automatic relabeling. |
| GET /workspaces/{w}/queries/{q}/certificate | Export original snapshot, variable map, definitions, steps and witnesses. |
| GET /workspaces/{w}/proposals?status=QUARANTINED | Inspect conflicts and pending model suggestions. |
| GET /workspaces/{w}/impact?revision={r} | Changed IDs and graph-derived affected query summaries for r versus its parent. |
| GET /workspaces/{w}/events?after={sequence} | Ordered sanitized history, bounded pages; polling is enough for v1. |
| POST /workspaces/{w}/decisions | Record a reader decision against an expected current revision and QueryResult; does not deploy anything. |

Workspace creation, fixture seeding and resets are operator scripts for v1, not anonymous public endpoints. This avoids building a full onboarding/account product. `POST /queries` requires an idempotency key as well, so automatic retries do not duplicate result/event records. Its receipt protects audit identity, not knowledge revision publication.

## 4. Mutation request and outcomes

```json
{
  "expected_revision": "rev_001",
  "idempotency_key": "demo-correct-tests-01",
  "reason": "Correct the test report for release demo-42",
  "acceptance": "human_confirmed",
  "mutations": [
    {"op":"replace","target_assertion_id":"as_tests_pass",
     "assertion":{
       "client_ref":"test-correction",
       "formula":{"op":"not","arg":{"op":"atom","id":"tests_pass"}},
       "evidence":[{"uri":"fixture://demo-42/tests-corrected",
         "excerpt":"The integration suite failed in the corrected report.",
         "observed_at":"2026-10-17T10:00:00Z"}]
     }}
  ]
}
```

Mutation union: `add {assertion}`, `retract {target_assertion_id}`, `replace {target_assertion_id, assertion}`. No duplicate target in one batch. Targets must be members of expected_revision. Server assigns immutable IDs and evidence digests. Require nonempty batch, ≤32 items, no assertion/evidence overwrite, and a reason for retract/replace. An identical formula with new evidence may create a distinct assertion intentionally; its activation must still pass consistency.

Acceptance provenance values: `human_confirmed`, `trusted_fixture`, `model_proposed`. Permission policy determines who may use each value: it is not a client-controlled bypass. Model-proposed input is stored pending review. During the demonstration an operator explicitly confirms synthetic observations, or the seeded trusted fixture path is clearly identified.

Outcomes:

- `COMMITTED` (201): new `revision_id`, `parent_revision_id`, `knowledge_hash`, mapped client references, receipt and timings.
- `QUARANTINED` (200): proposal ID, base revision, conflicting assertion IDs and reason. Head unchanged; conflict is a successful domain response, not network failure.
- `PENDING_REVIEW` (202): proposal ID; no accepted-memory change.
- `VALIDATION_INDETERMINATE` (503): solver could not finish; no activation. Reuse the same idempotency key only for identical payload.
- `REVISION_CONFLICT` (409): expected and actual head, user-visible refresh/review instruction. No blind automatic correction against a new head.

Do not silently remove a conflicting premise to make an update SAT. A correction must identify what it retracts and why. Acceptance policies can reject evidence without making a logical claim.

## 5. Query request and response

```json
{
  "revision_id":"rev_001",
  "idempotency_key":"reader-ready-01",
  "query":{"op":"atom","id":"release_ready"},
  "proof_mode":"certificate"
}
```

`proof_mode` is `certificate` or `solver`; default certificate. Example shape (symbolic hashes below are placeholders, not valid fixture checksums):

```json
{
  "query_id":"query_001",
  "workspace_id":"workspace_demo",
  "revision_id":"rev_001",
  "head_revision_observed":"rev_001",
  "freshness":"CURRENT_AS_OF_READ",
  "semantics_version":"boolean-v1",
  "knowledge_hash":"<sha256>",
  "query_hash":"<sha256>",
  "result":"PROVED",
  "proof_status":"VERIFIED",
  "witnesses_verified":true,
  "certificate_id":"cert_001",
  "support_assertion_ids":["as_api_v2","as_tests_pass","as_ready_rule"],
  "explanation":"Release readiness follows from the accepted deployment and test results.",
  "solver":{"name":"z3","version":"<pinned>","reason_unknown":null},
  "timings_ms":{"load":0,"solve":0,"certificate":0,"check":0},
  "witnesses":{"knowledge":{"api_v2":true,"tests_pass":true,"release_ready":true},"query_true":null,"query_false":null}
}
```

Generate measured timings and actual witnesses at runtime; zeros/nulls here describe the shape only. Witnesses in the exported certificate are required when VERIFIED. Use deterministic explanations from formal result/evidence; optional LLM prose cannot change result or invent support.

Logical result enum: `PROVED | REFUTED | UNKNOWN | INCONSISTENT_MEMORY | SOLVER_UNKNOWN`. Proof status: `VERIFIED | NOT_REQUESTED | BUDGET_EXCEEDED | FAILED`. `witnesses_verified` is a required boolean. For UNKNOWN, certificate_id is null and proof status NOT_REQUESTED; witnesses_verified describes independent checking of both models. INCONSISTENT_MEMORY/SOLVER_UNKNOWN have no decisive query certificate and witnesses_verified=false. FAILED leads to an integrity error rather than a normal trusted query response.

Freshness is separate from logic and proof status. PROVED + VERIFIED + HISTORICAL is valid historical evidence; it is not current permission to act.

## 6. Certificate contract

Bundle fields:

```text
certificate_version, semantics_version
workspace_id, revision_id, knowledge_hash, query_hash
result: PROVED or REFUTED
assertions: [{id, formula, evidence_ids}]
query: Formula
atom_variables: [{atom_id, variable: positive integer}]
definitions: [{variable, op, operands: [variable,...], formula_hash}]
roots: [{assertion_id, variable}]
query_root: positive integer
knowledge_witness: {atom_id: boolean}
clauses: [{id: contiguous integer, literals: [signed integer,...],
           origin: definition | premise | query_assumption | resolution,
           definition_variable?, assertion_id?, parents?: [id,id], pivot?: positive integer}]
empty_clause_id
support_assertion_ids
```

Original atom variables are sorted by atom ID then assigned 1..n. Non-atomic definitions follow deterministic postorder traversal of assertions sorted by ID, then query; shared canonical subformulas reuse one ID. Separate v1 test vectors lock this algorithm before authors implement independently. Reject duplicate variable IDs, dangling operands, cycles, oversized integers and undefined atoms. Definition DAG must structurally match the original formulas, not just their declared hash.

Use complete initial-clause data so the checker can reject extra assumptions. Root units identify assertions; query assumption is negative root for PROVED, positive for REFUTED. Enumerate definition clauses by increasing definition-variable ID and the template order in ARCHITECTURE.md, then premise roots by assertion ID, then the query assumption. Sort literals numerically after removing duplicate literals; omit tautologies. Keep duplicate initial clauses with different origins so provenance stays explicit. Search may use one representative for duplicate clauses; the certificate retains the full initial list. Derived clause records follow in topological order. The checker compares the complete expected initial list and then verifies inference steps.

Checker report: `logical_valid: boolean`, `context_binding: MATCHED | UNVERIFIED | MISMATCH`, `errors: [{code, step_id?, message}]`, computed support IDs. Accept optional `expected_context` with trusted workspace/revision, sorted assertion-ID/formula-hash pairs and their evidence-ID references, knowledge/query hashes and semantics version. Backend always supplies it from the original loaded snapshot; VERIFIED requires logical_valid=true and context_binding=MATCHED. CLI without it reports only mathematics for the supplied snapshot, not authenticated provenance. Never trust an expected context merely because it is embedded in the same untrusted certificate. The CLI supports `--expected-context <trusted-manifest.json>` when obtained independently. Evidence IDs bind to the expected service records; this does not certify the factual truth of those records.

All witness maps are total over the original atoms appearing in the snapshot and query. Query-only registered atoms receive explicit values using model completion. An omitted assignment is invalid, not silently false. The checker uses the original AST evaluator, not the CNF compiler, to verify the witness.

G0 example checker vector can use the simple clause set for P, P→Q, Q→R, and NOT R: resolve P with (-P,Q) to get Q; resolve Q with (-Q,R) to get R; resolve R with -R to get empty. This illustrates steps only. A full bundle must also contain the original ASTs, validated encoding and SAT(K) witness; these clauses alone are not sufficient for the export format.

## 7. Error envelope

```json
{"error":{"code":"REVISION_CONFLICT","message":"Memory changed. Review the latest revision before retrying.","request_id":"req_123","retryable":false,"details":{"expected_revision":"rev_001","actual_revision":"rev_002"}}}
```

Use 401 authentication; 403 role denial; 404 inaccessible/missing object; 409 revision/idempotency conflict; 413 body limit; 422 schema/atom/target errors; 429 bounded-queue saturation; 503 DB or validation unavailable; 500 integrity failure. Never expose tokens, stack traces or raw database credentials. Database errors are transport/service failures, not SOLVER_UNKNOWN. Rate limits/Retry-After are explicit.

## 8. Canonical scenario

Workspace scope: release demo-42. Atoms: P=`api_v2`, Q=`tests_pass`, R=`release_ready`, D=`docs_signed`.

Revision r1 accepts P, Q, `(P AND Q) IMPLIES R`, and `(NOT Q) IMPLIES (NOT R)`, each with synthetic source evidence. D is registered but unasserted.

| Action | Required outcome |
| --- | --- |
| Query R at r1 | PROVED, checked certificate for demo. |
| Query NOT P at r1 | REFUTED. |
| Query D at r1 | UNKNOWN, two satisfying witnesses. |
| Add NOT Q without retracting Q | QUARANTINED; head remains r1. |
| Replace Q with NOT Q in one batch | Commit r2, preserving old Q and evidence historically. |
| Query R at r2 | REFUTED using the explicit failed-tests rule. |
| Remove Q without replacement, in a separate fixture fork | R is UNKNOWN. Do not report false just because support vanished. |
| Resume reader client | Fetch r2, re-query, record a revision-bound blocked decision. |

The inverse rule is explicit policy. `(P AND Q) -> R` alone does not imply `NOT Q -> NOT R`. Scope and evidence are displayed so the viewer understands what the proof actually establishes.

## 9. Internal interfaces and file ownership

Saqlain supplies `load_snapshot(workspace, revision)`, `publish_revision(candidate, expected_revision, key)`, `classify(snapshot, query, budget)`, `generate_certificate(snapshot, query, result, budget)` and typed HTTP models.

Mahavir supplies `check_certificate(bundle, expected_context=None) -> CheckReport`, independent AST evaluator, frontend API client and agent adapter. Checker accepts JSON-compatible data only; no database, model or Z3 imports. Saqlain supplies trusted expected_context at the API boundary. Contract fixtures live in `contracts/fixtures/` and are validated by both languages. All function names are planned targets, not existing symbols.

Events expose accepted/quarantined proposals, committed revisions, completed queries and recorded decisions. Events do not contain hidden reasoning or full model prompts. After commit, query/decision events must refer to durable objects; event ordering uses workspace sequence plus stable ID, not wall-clock alone.
