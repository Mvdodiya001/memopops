# Submission form copy

Draft for human review. Paste after the real FalkorDB recording/setup gate in [PLAN.md](PLAN.md) succeeds. Replace pending video/blog URLs with published links. These answers describe implementation, not evidence of a completed upload or organizer submission.

## Project title

memopops — Proof-Carrying Memory for AI Agents

## Description

An agent's old answer can stay convincing after the facts behind it change. That becomes dangerous when another agent or a later session treats the answer as current.

memopops gives developers building multi-agent workflows a shared memory of accepted assertions, evidence, and immutable revisions. Agents query a specific revision; the service distinguishes what follows, what is refuted, and what is still unknown. Small decisive results can carry a resolution certificate checked by an independent verifier.

FalkorDB stores revision membership, provenance, and the premise relationships used to find queries affected by a correction. An operator can replace an observation without deleting history, while a stale reader must refresh before recording a current decision.

Our release-readiness example uses synthetic data and explicitly scripted agents. It demonstrates the intended workflow without claiming autonomous live model tool use. The repository includes the local setup, graph model, core Cypher, and reproducible checks.

## Track

Select **Track 02 — Agent Memory and Coordination** only. This is the clearest fit; extra tracks would require additional demonstrated product behavior.

## Repository

https://github.com/Mvdodiya001/memopops

## Demo video

**PENDING:** insert the actual public or unlisted YouTube watch URL after upload. Test it signed out. Do not paste a drive file, local path, or draft URL.

Suggested video title: **memopops: When Shared Agent Memory Changes | Graph Hacks**

## Live demo or deployment

**Leave blank.** We are submitting the complete local setup and working video route permitted by the rules. The local instructions are linked from README. No public deployment is claimed.

## How did you use FalkorDB?

FalkorDB is the production shared-memory store. Each authorized workspace selects its own graph. Revisions connect to accepted assertions through INCLUDES; assertions connect to canonical Boolean formulas through ENCODES and to evidence through SUPPORTED_BY. The service reconstructs the complete accepted revision from these relationships and verifies its hashes before reasoning over it.

Persisted query results connect to their revision and the assertions used by their proof. When an operator replaces an observation, a Cypher traversal follows USES_PREMISE to identify affected queries at the parent revision. We preserve the old revision and proof instead of silently presenting them as current. Re-querying determines whether the new conclusion is proved, refuted, or unknown.

Revision publication and decision recording use expected-head guards and idempotency receipts in their graph writes. Inconsistent submissions are retained as quarantined proposals outside accepted memory.

FalkorDB handles persistence, provenance, and dependency traversal. Z3 handles propositional reasoning, and a separate checker validates bounded proof certificates. The graph is central to the production memory path; in-memory stores are explicitly isolated test/replay tools.

## Blog link

**PENDING:** insert the public published article URL after the post and images are accessible signed out. Use [BLOG_BRIEF.md](BLOG_BRIEF.md) for the content and review plan. This field is optional in the form; the blog remains one of our intended deliverables.

## What did you like about FalkorDB?

Cypher made the relationships in our memory model explicit. We could express revision membership, assertion-to-evidence provenance, and query-to-premise dependencies directly, rather than rebuild those connections in application code. Using a separate graph per workspace also fit the scope of our authenticated memory API. The same relationships that load memory give us a concrete way to explain which prior queries need review after a correction.

## What improvements would you like to see?

A single copyable cloud connection example covering endpoint, port, username, TLS mode, and an authenticated GRAPH.QUERY check would make first connection and troubleshooting easier. We encountered connection timeouts during setup, although we have not established whether their cause was our network/proxy or the service configuration.

More end-to-end examples of revision-checked, idempotent application writes and recovery after an ambiguous network response would also help developers building shared agent memory. These patterns were important to our design, beyond basic CRUD examples.

The team should review these feedback drafts against its own experience before submitting; avoid adding unmeasured speed or scale claims.

## AI assistance disclosure

Include this in README and the blog; the form currently has no separate disclosure field:

> AI coding assistants supported planning, implementation, tests, UI, and documentation. The repository records the work and verification results in its activity logs. We remain responsible for the submission and its technical claims. The demonstrated agent workflow is scripted replay unless explicitly labeled otherwise.

Both humans must understand and be able to explain the graph model, queries, revision guard, reasoning/checker boundary, and limits. Do not substitute an unsupported statement that every generated line was personally reviewed.

## Final review

- Actual team names/accounts are entered accurately in the organizer's team settings.
- Public repo opens signed out; the submitted URL points to the final main branch.
- YouTube video plays fully signed out; the blog and images also load.
- Deployment is blank and local setup is complete.
- Description matches what the recording actually demonstrates.
- Track 02 is selected and the organizer confirms submission.
