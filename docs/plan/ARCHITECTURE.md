# Architecture and algorithms

This specifies the intended first release. Source IDs refer to [the research ledger](RESEARCH.md). G0 validates dependency versions and database syntax.

## 1. Correctness envelope

Use classical propositional logic over a finite atom registry. No quantifiers, arithmetic, probability, temporal inference, default negation or inferred natural-language equivalence. A workspace has a single subject/scope, such as release demo-42. Each revision is a snapshot of accepted assumptions about it.

Invariants:

1. Every published revision has immutable assertions and passes satisfiability and evidence-policy checks.
2. Answers bind workspace, revision, knowledge hash, query hash and semantics version.
3. Independently checked means the checker validates original inputs, inference steps and a consistency witness for the snapshot.
4. A stale revision cannot publish after another writer advances the head.
5. Rejected proposals, retractions and old proofs remain auditable and do not silently enter current knowledge.
6. Database/solver failures never become successful commits or fabricated results.

Entailment is conditional on the encoded premises. It does not establish evidence truth or translation correctness. The small checker and input/schema implementation remain trusted software; we are not formally verifying the whole system.

## 2. Boolean representation

Use a discriminated JSON AST: atom, not, and, or, implies, iff. All binary operators have exactly two ordered arguments; not has one. No empty conjunctions/constants in v1. Do not evaluate expression strings. Any UI shorthand produces AST before submission.

Canonical serialization uses ASCII atom IDs matching `[a-z][a-z0-9_]{0,63}`, recursively sorted object keys, compact JSON separators, UTF-8, no floats or extra keys. Preserve argument order even for commutative operators. Equivalent formulas can have different hashes; semantic deduplication is unnecessary. Hash an envelope containing semantics version and AST with SHA-256. Compare canonical content on a hash hit to detect corruption/collisions.

Validate depth/size before unbounded recursion. Atom meanings are immutable; changed meaning gets a new ID. Every atom must be registered. An unrelated registered atom without premises can yield UNKNOWN; a misspelled unregistered atom yields 422.

## 3. Query classification

Load the complete accepted snapshot K_r from FalkorDB and verify membership count/hash. Top-k/vector retrieval cannot define the logical knowledge base; omitted premises alter entailment and unknown classification.

1. Check K_r. UNSAT → INCONSISTENT_MEMORY. UNKNOWN/timeout → SOLVER_UNKNOWN. SAT → continue and retain a total Boolean witness over original atoms.
2. Check K_r AND NOT Q. UNSAT → PROVED.
3. If necessary, check K_r AND Q. UNSAT → REFUTED.
4. If both query checks are SAT → UNKNOWN, with witnesses for both sides.
5. Any unresolved case → SOLVER_UNKNOWN. After confirmed SAT(K_r), either UNSAT branch is decisive; the other need not run. Both UNSAT branches after SAT(K_r) indicate an internal integrity error.

Create a fresh Z3 Context per job. Translate JSON inside it; use push/pop for query assumptions. Never share Z3 objects between contexts/workers [R4,R5]. Record version and timings. An UNSAT core is an explanatory subset, not necessarily minimal or a proof certificate.

Keep CPU work off FastAPI's event loop. Worker processes receive JSON only. On wall timeout terminate/replace the worker; timing out an await does not stop computation. Clean up canceled jobs. Test process-spawn behavior or use the shared Linux container.

## 4. Authoritative graph

Use one graph per authorized workspace, selected from a server-derived opaque ID. Graph separation is not authorization: authenticate and check membership first. Never accept client graph names or trust client actor IDs.

| Node | Content |
| --- | --- |
| Workspace | Exactly one singleton per graph; ID, mutable head_revision and sequence. |
| Atom | ID, label, precise meaning, scope; immutable. |
| Formula | Hash, operator/atom reference, canonical JSON for integrity; immutable. |
| Assertion | ID, formula root, actor/session, time, evidence and acceptance provenance; immutable. |
| Evidence | ID, source URI/excerpt/time/content digest; immutable. |
| Revision | ID, sequence, parent, knowledge hash, complete membership, consistency witness; immutable once published. |
| Proposal | ID, payload hash, base revision, mutations, disposition/conflict. Pending transitions to terminal with history. |
| QueryResult | ID, query/revision hashes, result, solver metadata, proof status and witnesses. |
| ProofStep | Certificate ID, clause, parent indices and pivot; immutable. |
| AgentSession / Event | Actor/session identity, sanitized tool calls, decisions and handoffs. |
| RequestReceipt | Idempotency key, payload hash, outcome reference; atomic with successful publication. |

Edges:

- Revision -INCLUDES-> Assertion -ENCODES-> Formula.
- Formula -OPERAND {position}-> Formula; atom formula -REFERS_TO-> Atom.
- Assertion -SUPPORTED_BY-> Evidence; replacement -SUPERSEDES-> previous Assertion.
- Revision -PREVIOUS-> Revision.
- QueryResult -AT_REVISION-> Revision; QueryResult -USES_PREMISE-> Assertion.
- QueryResult -HAS_STEP-> ProofStep; ProofStep -PARENT-> earlier ProofStep.
- AgentSession -EMITTED-> Event; Event -ABOUT-> relevant proposal/revision/result.

Activation belongs to revision membership, not a global assertion.active flag. Duplicate formulas with different evidence remain separate assertions. Knowledge hash covers sorted `(assertion_id, formula_hash)` pairs and semantics version.

At ≤256 active assertions, copy membership edges per revision: O(A) edges/revision buys simple reconstruction. This is deliberately bounded. Cap demo workspace/history growth explicitly; never delete referenced proof revisions. Delta chains/checkpoints can wait.

Index label.id and Formula.hash with verified syntax; inspect GRAPH.EXPLAIN. Add supported uniqueness constraints and validate singleton/ID counts at bootstrap. Do not assume Neo4j procedures or unnamed-edge count behavior [R8,R9].

## 5. Revision publication

One API process and a bounded per-workspace queue reduce conflicts. The database revision guard is the correctness boundary; an in-process lock alone is insufficient.

For expected_revision r and idempotency key k:

1. Authenticate and validate payload; acquire bounded workspace queue slot.
2. Read receipt(k). Matching payload returns original outcome; different payload gives 409 IDEMPOTENCY_KEY_REUSED. Check this before the stale-revision check so lost-response retries work.
3. Read current head. If not r, return 409 REVISION_CONFLICT. Load immutable K_r and verify its hash.
4. Apply add/retract/replace to an in-memory assertion set. Validate all targets. Replacement removes/adds in one candidate; retraction does not imply negation.
5. Check SAT(K_new) and acceptance provenance. Indeterminate → no activation. UNSAT → preserve quarantined proposal/conflict outside accepted membership; do not advance head.
6. Publish the bounded new records, complete membership, receipt and head update in ONE parameterized graph write query. Begin with an expected-head predicate and idempotency guard, before any writes. Require exactly one success row.
7. Zero rows means conflict, never acceptance. Return current revision; caller explicitly retries against it.
8. Ambiguous network outcome → read receipt before replaying. The same key cannot create two revisions.
9. Release queue in finally. Prioritize affected query rechecks after commit.

Conceptual guard, not a complete executable query:

```cypher
MATCH (w:Workspace {id: $workspace_id})
WHERE w.head_revision = $expected_revision
WITH w
// Create immutable records, complete membership and receipt here.
SET w.head_revision = $new_revision, w.sequence = w.sequence + 1
RETURN w.head_revision
```

G0 must test complete publication for empty/nonempty lists, preserving `w` across WITH and avoiding zero-row UNWIND accidents. Separate fixed query templates by mutation shape if simpler. RETURN LIMIT does not limit writes. If a full query is impractical, stage immutable unreferenced records, verify the manifest, then atomically publish marker/receipt/head; readers follow published revisions only. That fallback requires crash tests and an updated design note.

Current FalkorDB documentation describes individual-query atomicity and serialized writes [R2]. That does not cover an earlier external solver check. The guarded revision comparison closes this gap. Assuming the code/database are correct and there are no out-of-band writers: empty r0 is SAT; every successor is SAT-checked against exactly its guarded parent; only one successor wins that parent's head. Test assumptions on the pinned image.

Do not use MULTI/EXEC to claim rollback across application phases: Redis execution-time failures do not roll back other commands [R3].

## 6. Reads and freshness

Snapshot head r, load immutable K_r, solve and return r even if head advances. Include head_revision_observed and freshness CURRENT_AS_OF_READ or HISTORICAL. Current means the last head read matched; it cannot promise the head will never change after response.

Frontend caches by workspace+revision and rejects late responses for a different selection. Before recording a current agent decision, compare the decision's expected revision to head in its write. A conflict requires reread. This demo records decisions; it performs no irreversible external release action.

Cache key: workspace, revision, knowledge hash, query hash, semantics version, solver version, proof mode. Use a bounded LRU after correctness passes. Cache immutable snapshots, not shared solver objects. Database unavailability is an error, not a trigger to serve hidden local memory as current.

UNKNOWN cannot carry over after new premises. Although a proof with still-active support can remain valid under consistent extension, v1 does not silently certify across revisions. Re-evaluate a viewed query and retain the original proof as historical.

## 7. Dependency impact

On correction, query QueryResults whose USES_PREMISE touches removed/replaced assertions. This identifies invalidated support, not false conclusions; alternative support may exist. Recompute these first, counting all affected results before UI pagination.

Every old result is historical. Queries at the new revision recompute or hit that exact revision's cache, including formerly UNKNOWN queries. Impact traversal prioritizes and explains work; it never blesses unvisited old answers as current. Solver-only results without reliable support conservatively depend on all active assertions. Checked proof support comes from assertion-root units in the empty clause's ancestor DAG.

Do not promote derived conclusions into accepted assertions in v1. Keep support flattened to original assertions/rules to avoid circular justification. Formula/proof DAGs must be acyclic; memory history may contain ordinary cross-links.

```cypher
MATCH (q:QueryResult)-[:USES_PREMISE]->(a:Assertion)
WHERE a.id IN $changed_assertion_ids
RETURN DISTINCT q.id, q.query_hash, q.revision_id
```

Verify this illustrative query against the pinned image. Evidence retrieval traverses QueryResult → Assertion → Evidence and Assertion → Formula → operands. Submit real query files. Removing FalkorDB must break memory/provenance retrieval, not reveal an alternative array store.

## 8. Independent certificates

Z3 classifies. A bounded resolution search creates refutations for decisive small results. A checker authored in Mahavir's lane validates without Z3 or the generator implementation. Keep separate packages.

PROVED certifies UNSAT(K AND NOT Q); REFUTED certifies UNSAT(K AND Q). Include a total SAT witness for K so the checker also rejects inconsistent-memory explosion. For UNKNOWN, independently evaluate two total witnesses on original ASTs; no refutation certificate is claimed.

Tseitin encoding gives each non-atomic subformula a fresh integer, disjoint from original atom variables. Assert all premise roots and the proper sign of the query root. The result is equisatisfiable under extension, not literally equivalent over the expanded vocabulary. Size is linear; naive distributive CNF can explode [R6].

| Definition | Clauses |
| --- | --- |
| z = NOT a | (-z OR -a), (z OR a) |
| z = a AND b | (-z OR a), (-z OR b), (z OR -a OR -b) |
| z = a OR b | (z OR -a), (z OR -b), (-z OR a OR b) |
| z = a IMPLIES b | (-z OR -a OR b), (z OR a), (z OR -b) |
| z = a IFF b | (-z OR -a OR b), (-z OR a OR -b), (z OR a OR b), (z OR -a OR -b) |

Clauses are immutable sorted sets of signed nonzero integers. Deduplicate literals. Discard tautologies containing x and -x; never confuse a discarded tautology with the empty clause. The checker reconstructs expected initial clauses from ASTs and validated definitions; uploaded arbitrary clauses are not premises.

Resolution: for p in C1 and -p in C2, the child must equal `(C1 minus {p}) union (C2 minus {-p})`. Remove exactly one complementary pair. Skip tautological children. Parents precede children; pivot signs and exact resolvent must match. Success requires a reachable empty clause.

Search uses a clause hash set, signed-literal postings, unit-first/FIFO agenda and parent/pivot arrays. Stop on empty clause or budget. Export only empty-clause ancestors. Do not build CDCL, restart heuristics or elaborate minimization. Resolution search remains exponential [R7]; budget exhaustion limits the certificate, not the known solver result.

Checker: enforce parse/size caps; validate atom map and definition DAG against original ASTs; reconstruct all initial clauses/root units; independently evaluate the K witness; check each resolution step; confirm empty clause and support. The backend passes an independently obtained expected context containing workspace, revision, assertion IDs/hashes and query hash. Compare against that context before setting VERIFIED. No assumption becomes valid because its hash matches.

Offline checking without an expected context proves only the supplied snapshot. Its report must say `context_binding=UNVERIFIED`; hashes are not signatures. A bundle with a relabeled workspace/revision can still be mathematically valid. Reject that relabeling only when it disagrees with a trusted expected context, not by pretending the checker can infer the original source. The CLI accepts an optional trusted manifest obtained separately from the authenticated service.

Proof status: VERIFIED, NOT_REQUESTED, BUDGET_EXCEEDED, FAILED. Result and proof status are separate. VERIFIED requires valid mathematics and matching expected context inside the service. Internal checker failure withholds the certificate and returns an integrity error; do not quietly downgrade a broken artifact to success. Planned budget exhaustion can return a solver-checked result. Demo decisive results must be VERIFIED.

## 9. Persistence and recovery

Use a named volume and tested RDB/AOF configuration [R10]. Record effective settings. Every-second fsync allows a power-loss window; do not claim zero-loss durability. Test ordinary process restart separately. No startup reset.

Readiness checks DB/schema. Workspace bootstrap creates exactly one empty SAT revision and head. Duplicate singletons or hash mismatch fail readiness for that workspace. Database credentials stay server-side. Recover ambiguous writes through receipts. Test cleanup only targets unique test-run graph prefixes, never the demo graph. Cold-cache proof retrieval must work.

## 10. Complexity and optimization

| Operation | Structure | Cost / limit |
| --- | --- | --- |
| AST validation/hash | Bounded traversal | O(n); no semantic equivalence solving. |
| Revision assembly | Assertion-ID set/dictionary | O(A + changes), O(A) membership edges/revision. |
| Snapshot loading | Indexed lookup + membership | Output-sensitive in A; measure DB/network separately. |
| Tseitin | Memoized subformula DAG | O(n) variables/clauses; collision-free fresh IDs. |
| SAT classification | Mature solver | Worst-case exponential, bounded time/size/concurrency. |
| Proof search | Postings + clause dedup | Fewer candidates in practice, still exponential. |
| Proof checking | Parent index + set operations | Approximately total processed literals plus AST/witness work. |
| Impact | Reverse support adjacency | Output-sensitive; future BFS uses visited set, O(V+E). |
| UI proof layout | Topological layering | O(V+E) on bounded DAG; summarize oversized views. |
| Cache | Exact-revision LRU | Expected O(1) lookup, bounded memory. |

Measure first. Optimize duplicate reads, N+1 evidence queries, missing ID indexes and response size. Parameterized query shapes help plan reuse [R11]. Defer distributed queues, vector indexes and persistent incremental solvers until a measured need exists.
