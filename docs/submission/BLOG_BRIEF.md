# Blog editorial and publication brief

## Decision

**Title:** When Shared Agent Memory Changes: Building memopops with FalkorDB

**Subtitle:** Revisioned evidence, dependency traversal, and checkable proofs for a small shared-agent workflow.

Target **1,100–1,400 words**, six real images/diagrams at most, published through an existing public account. Default to [DEV Community's editor](https://dev.to/new) if a platform must be selected; sign-in is required. Keep a Markdown source copy in the repository once the actual article is written. This file is an editorial plan with a sample opening, not a published post.

The organizer's [event page](https://www.wemakedevs.org/hackathons/falkordb) describes a best-blog side prize. No separate required word count or judging rubric was found there. Do not invent mandatory tags, social-post requirements, or a different deadline. A public article should be linked before our final submission review.

## Central argument

Shared memory needs a way to revisit a decision when its evidence changes. memopops demonstrates this with a small, inspectable Boolean world rather than claiming a general cure for hallucinations. The reader should leave understanding why revision membership and premise dependencies belong in the graph, and why the logical proof and accepted evidence are separate trust boundaries.

Do not open with generic claims about AI transforming industries, a list of libraries, or a product pitch unsupported by the demo. Open with the corrected test report.

## Suggested opening (adapt after the real demo)

> The API was available. The tests passed. Our release policy said those two observations were enough to call the candidate ready.
>
> Then the test report was corrected.
>
> A reader agent returning later could still retrieve its old answer. The interesting question was whether it knew that answer belonged to an earlier state of memory, and which evidence needed to be checked again.
>
> We built memopops around that question: shared memory with immutable revisions, evidence links, and small proofs that can be checked independently. FalkorDB stores the relationships between accepted assertions, revisions, and query dependencies. A separate Boolean reasoning service answers a narrower question: what follows from the accepted premises at this revision?

Do not say this is a real customer's release incident. The scenario is synthetic. Frame the narrated sequence as an observed run only after the database-backed rehearsal and recording have succeeded.

## Article outline and word budget

| Section | Budget | Specific content and asset |
| --- | ---: | --- |
| 1. The report changed | 130 | Opening above; synthetic release scope; before/after result screenshot |
| 2. What shared memory needs to preserve | 130 | Assertions, evidence, accepted revision, query context; user is a developer coordinating agents across sessions |
| 3. Where FalkorDB does the work | 220 | Actual schema diagram and one short Cypher excerpt from [GRAPH_MODEL.md](GRAPH_MODEL.md); explain INCLUDES, SUPPORTED_BY, USES_PREMISE |
| 4. What proved, refuted and unknown mean | 170 | Exact checks below; include `docs_signed` example; do not equate missing support with negation |
| 5. Correct the observation without rewriting history | 190 | Quarantine first, operator replacement, current-head guard, idempotent retry, stale decision rejection; real r2 impact screenshot |
| 6. What a certificate establishes | 150 | Independent checker, witness/formula/context checks, tampering rejection; CLI provenance boundary |
| 7. Verification and implementation lessons | 180 | Actual test table, lab-vs-DB distinction, honest weak-baseline scope, fresh-process runner bug and port mismatch found in audit |
| 8. Limits and next steps | 100 | Bounded propositional model, trusted observations, scripted agents, no public deployment; repo/video/local-setup links and AI disclosure |

## Technical facts to get right

For accepted knowledge `K` and query `Q`, first require `K` to be satisfiable. With consistent K:

```text
UNSAT(K AND NOT Q) -> PROVED
UNSAT(K AND Q)     -> REFUTED
both satisfiable  -> UNKNOWN
```

Inconsistent accepted memory is INCONSISTENT_MEMORY. Timeout/indeterminate solver output is SOLVER_UNKNOWN. Neither becomes a proof. A separate explicit policy says `NOT tests_pass -> NOT release_ready`; negating the antecedent of the readiness rule alone would not justify that result.

Implementation details must match [GRAPH_MODEL.md](GRAPH_MODEL.md): formulas are canonical JSON on Formula nodes, certificates are stored/exported JSON, and the head is an ID property. Do not draw persisted operator trees, proof-step nodes, an Event feed, vector retrieval, or a global dependency engine that this snapshot does not implement.

The impact query examines results at the immediate parent revision. An affected old proof is still a historical proof of its original snapshot. Recomputing the new revision decides what changed; impact alone does not establish falsehood.

The production memory path depends on FalkorDB; an explicit in-memory lab is used for tests. Do not claim lab passes prove database persistence. The optional Gemini client currently generates plain text; the constrained demo actions remain scripted. A model key does not turn this into a live autonomous workflow.

## Evidence table for the draft

| Evidence | Audited result | How to describe it |
| --- | --- | --- |
| Backend at implementation `e9bd8c3` | 144 pytest tests passed on October 18 | Regression-test result, not a correctness proof for every input |
| Frontend | Typecheck, 8 tests, production build passed | Build and unit checks, not a full real-DB browser acceptance test |
| Lab acceptance | 4/4 expected behavioral cases | Includes two intentionally weak baseline behavior checks; no claimed accuracy superiority over real products/models |
| Existing solver benchmark | Retained samples and scope in [performance notes](../performance/README.md) | Optional paragraph only; simple workload, solver-only, no DB/proof/HTTP latency |
| Real DB correction/restart | Pending in this planning task | Fill from actual rehearsal with commit/environment and saved IDs; do not publish as completed until observed |
| Video/screenshots | Pending | Use frames from the same actual database run |

## Assets

1. Opening image: a clean crop showing the two revision/result states, labeled “r1” and “r2.” Each must come from the actual run.
2. One simple schema diagram matching implemented labels/relationships. For blog platforms without Mermaid support, render it to SVG/PNG and upload it; do not rely on unsupported Markdown rendering.
3. One r1 proof/evidence screenshot.
4. One quarantine or impact screenshot (choose the one that best explains the story).
5. Optional checker tamper-rejection terminal crop.

Use neutral backgrounds, readable labels, a single restrained accent, and descriptive alt text. A cover can use project name plus the real inspector screenshot. No stock AI brain art, fabricated dashboards, neon circuits, or invented result charts are needed.

## Writing and review workflow

1. Mahavir drafts the narrative and implemented UI/agent workflow while Saqlain establishes the real DB path.
2. Saqlain reviews the Cypher, logic truth conditions, guarded write, and checker/context explanation against code.
3. Add screenshots and a short observed-run paragraph only after the real rehearsal. State scripted mode and synthetic data in the article itself, not just a footer.
4. Both humans replace generic language with their actual technical decisions and observations. Do not invent personal experiences, customer stories, pain points, or claims that every generated line was manually reviewed.
5. Add the source repository, final YouTube link, local setup, and AI-assistance paragraph from [FORM_ANSWERS.md](FORM_ANSWERS.md).
6. Read the post aloud once. Remove repetition, promotional adjectives, duplicated architecture summaries, and unmeasured superlatives.

## Publication workflow

Use an existing account to avoid account-setup work on the critical path. Paste the final Markdown, upload real images to the platform, verify headings/code blocks/alt text, and preview on desktop and phone width. Confirm that image URLs are public rather than local file paths.

Publish the post, open it signed out, and click repository/video links. Put that stable public URL in the submission and README. Keep the editable Markdown locally/in Git for revisions. Social promotion is optional and is not authorized or performed by this planning task.

If time is short, publish a precise 700–900 word account of the working correction path, graph query, and limits. Preserve the human explanation and evidence rather than filling space.
