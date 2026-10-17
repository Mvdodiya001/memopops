# Implementation research ledger

Researched October 17, 2026. Primary documentation and course material support the technical choices. The plan is our engineering synthesis, not a vendor-certified architecture. Behavior of the pinned runtime still needs integration tests. No official numerical judging rubric was found in the pages inspected; prioritization and timing budgets are our judgments.

| ID | Source | Finding and implication |
| --- | --- | --- |
| R1 | [Graph Hacks rules](https://www.wemakedevs.org/hackathons/falkordb/rules) and [event](https://www.wemakedevs.org/hackathons/falkordb) | FalkorDB must be central; Track 02 is persistent/shared memory. Deliver public code, setup, graph model/queries, video and disclose AI assistance. Deadline October 18, 23:59 IST. Human technical understanding matters. |
| R2 | [FalkorDB atomicity and concurrency](https://docs.falkordb.com/design/concurrency) | Individual write queries are documented as atomic and serialized per graph. We use a guarded publication query; this alone does not make external solver work transactional. |
| R3 | [Redis transactions](https://redis.io/docs/latest/develop/using-commands/transactions/) | Execution errors do not roll back other queued commands. Avoid treating MULTI/EXEC as application-level rollback. |
| R4 | [Z3 propositional logic](https://microsoft.github.io/z3guide/docs/logic/propositional-logic/) | Entailment can be tested by unsatisfiability of the negated goal. Tracked assertions support unsatisfiable cores. Core extraction is not certificate checking. |
| R5 | [Programming Z3](https://z3prover.github.io/papers/programmingz3.html) | Separate contexts are required for safe parallel use; proof APIs and solver state have specific limitations. Use isolated jobs and explicit result handling. |
| R6 | [CMU propositional encodings](https://www.cs.cmu.edu/~15414/s24/lectures/15-encodings.pdf) and [UW Tseitin discussion](https://courses.cs.washington.edu/courses/csep590b/26sp/lecture/l01/02-theory/) | Tseitin encoding avoids distributive CNF blow-up using fresh definitions and an asserted root. We independently test each local template. |
| R7 | [CMU propositional logic and logical agents](https://www.cs.cmu.edu/~15281/coursenotes/proplogic/) | Resolution is sound and complete without resource truncation but may be exponential. Keep search bounded and certificate coverage explicit. |
| R8 | [FalkorDB indexing](https://docs.falkordb.com/cypher/indexing) | Index frequently queried identity fields and inspect plans; unnecessary indexes add overhead. |
| R9 | [FalkorDB known limitations](https://docs.falkordb.com/cypher/known-limitations) | Relationship-count optimizations and eager operations around LIMIT need care. Test exact queries; do not assume Neo4j parity. |
| R10 | [FalkorDB persistence](https://docs.falkordb.com/operations/durability/persistence) and [Redis persistence](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/) | Configure actual persistence/volume settings and verify restart. Fsync policy affects crash durability; a successful process restart is not a zero-loss proof. |
| R11 | [GRAPH.QUERY](https://docs.falkordb.com/commands/graph.query) | Parameterized query shapes support plan reuse. Keep untrusted values out of string interpolation. |
| R12 | [Apple layout](https://developer.apple.com/design/human-interface-guidelines/layout) | Hierarchy, alignment, grouping, disclosure and adaptation guide the split-view design. |
| R13 | [Apple color](https://developer.apple.com/design/human-interface-guidelines/color) | Use color consistently and pair it with other cues. Our muted web palette is a design choice, not Apple system colors. |
| R14 | [Apple accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility) | Legibility and alternative interaction/cues are integral. Verify zoom, keyboard, motion and status readability. |
| R15 | [WCAG contrast minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) | Test text contrast in actual web states; use standard 4.5:1 normal-text target. |
| R16 | [FastAPI server workers](https://fastapi.tiangolo.com/deployment/server-workers/) | Multiple processes are a deployment choice. Keep one API process initially and do not mistake in-memory coordination for cross-process locking. |
| R17 | [Git worktrees](https://git-scm.com/docs/git-worktree) | Separate working trees enable isolated branches. They do not eliminate logical integration conflicts. |

Apple's normal HIG pages exposed little text through the reader. Their official documentation JSON was read instead: [layout JSON](https://developer.apple.com/tutorials/data/design/human-interface-guidelines/layout.json), [color JSON](https://developer.apple.com/tutorials/data/design/human-interface-guidelines/color.json), [accessibility JSON](https://developer.apple.com/tutorials/data/design/human-interface-guidelines/accessibility.json). No third-party design mirror is needed for the recommendations here.

The older FalkorDB [documentation issue #393](https://github.com/FalkorDB/docs/issues/393) is closed via merged documentation. It would be incorrect to cite that issue as evidence that current atomicity documentation is absent. The live documentation was checked. We still require a runtime spike because a design depends on the tested version, not a page alone.

## Decisions and rejected complexity

| Decision | Reason | Revisit trigger |
| --- | --- | --- |
| Bounded propositional language | Testable semantics and feasible certificate checker | A real use case requires richer logic and has a verification budget. |
| Full active snapshot solving | Avoid unsound conclusions from retrieval omissions | Proven-safe component decomposition with regression evidence. |
| Mature solver + small certificate search/checker | Fast logical checks plus transparent bounded proofs | Certificates routinely exceed budget; evaluate established proof-logging solver/checker tooling. |
| One API process + guarded revision publish | Simple coordination with a real database guard | Measured throughput need and a tested multi-instance protocol. |
| Copy revision memberships | Small bounded knowledge makes history simple | Storage/latency measurements justify delta/checkpoint complexity. |
| Structured input first | Clear atom meanings and reproducible behavior | Model extraction has a human-reviewed evaluation set. |
| Inspector before graph canvas | People need an answer and evidence quickly | Larger graph exploration becomes a demonstrated user need. |
| REST clients before MCP/framework | Two clients can share memory without extra plumbing | Another host needs integration after core release gates. |

PySAT/DRUP and native solver proofs are possible future alternatives, not additional dependencies in this plan. A broad literature novelty review is outside this implementation task. Prior systems named in the supplied history remain context; do not claim that propositional memory, truth maintenance or graph provenance are new inventions.

## Items that research cannot settle without execution

Exact package/image compatibility; complete publication-query syntax; write rollback on the chosen build; worker shutdown behavior; certificate coverage and latency; database durability settings; provider credentials; clean-machine setup; final deployment capacity. Each has a named gate/test. Do not replace these with confident prose.
