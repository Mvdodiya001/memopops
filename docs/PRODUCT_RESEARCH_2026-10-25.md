# From a recorded demo to usable propositional memory

## Primary-source research

[Graphiti's project documentation](https://github.com/getzep/graphiti) describes evolving facts, historical state and provenance, with incremental graph updates. The useful lesson here is to preserve the previous state and its sources when accepting a correction. memopops already has immutable revisions and premise dependencies; replacement/retraction controls make those capabilities usable without copying another memory engine or changing the theorem prover.

[LangMem's conceptual guide](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/) distinguishes semantic knowledge, episodic experiences and procedural instructions, and organizes memory by namespaces. The product implication is a focused contract: this project manages explicitly accepted facts and rules for a scoped project. It should not pretend to be an unrestricted chat archive. Custom workspaces and precise proposition definitions turn that distinction into something users can configure.

[Letta's memory-block documentation](https://docs.letta.com/v1-sdk/memory/memory-blocks) explains descriptive memory blocks and read-only access, and warns that concurrent full replacements can overwrite earlier changes. The relevant design is controlled, understandable writes. memopops retains operator-only activation and expected-revision concurrency guards, adds source-aware corrections, and never treats a changed memory paragraph as automatically accepted knowledge.

These are design inputs, not comparative benchmark results or claims that another system is logically unsound.

## Decisions implemented in this iteration

| Friction | Change | Correctness constraint |
| --- | --- | --- |
| Only the release demo can be seeded | Authorized initialization of a custom empty workspace | One atomic graph command, fixed vocabulary, safe identical retry, no overwrite |
| Proposition meanings are discarded by the web client | Return and display labels, meanings and scopes | Retain backward-compatible atom IDs; never reinterpret an old ID |
| UI mostly accepts individual atoms | Deterministic expression notation for facts, policies and questions | Compile to the existing bounded AST; validate again on the server |
| Corrections require hand-built API requests | Explicit add/replace/retract form with evidence and reason | Complete candidate consistency check and expected-head commit guard remain intact |
| Query IDs must be copied from a terminal | Paginated saved-question history | Tenant-bound reads, stable keyset ordering, original revision/proof and current freshness |
| Docker looks mandatory | Host API command loading a private configuration file | Requires a real reachable FalkorDB; no silent synthetic fallback |
| Quarantine gives little explanation | Show the submitted formulas, changes and sources | No fabricated unsatisfiable core or automatic promotion |

## Deliberately deferred

Natural-language ingestion is a separate trust boundary: extraction should produce reviewable candidates, not silently accepted premises. Semantic retrieval may select relevant records for an agent's context, but should not truncate the knowledge set used to establish a proof. Retrieval, temporal validity windows and arbitrary vocabulary extensions need explicit schema/version designs. They were not added as rushed dependencies or advertised as implemented features.

The next meaningful evidence gate is a real custom-workspace persistence/concurrency rehearsal using a valid database endpoint, followed by observation of actual user workflows. The previously supplied cloud hostname was unavailable during this iteration. Docker restart testing remains excluded at the user's request.
