# memopops: Remembering Why an AI Agent Believes Something

*How we built shared agent memory that keeps track of an answer's sources, reasoning, and history.*

![Accepted facts and a release policy lead to a revision-bound answer with evidence and a checked certificate.](figures/01-memory-with-reasons.png)

Imagine two AI agents helping a team prepare a software release. One checks the tests and saves the result: everything passed. The other reads that result, checks the release policy, and concludes that the release is ready.

A little later, someone corrects the test result. The tests actually failed.

Saving the correction is only part of the job. The earlier answer is still sitting in memory. Which result did it rely on? Does its reasoning still hold? Will the second agent notice that something changed?

We built **memopops** around that problem. We wanted agents to remember the reasons behind an answer, so those reasons could be checked again when the information changed.

The first results were encouraging. On **3,000 synthetic logic problems**, every answer classification matched a separate check that tried all possible truth assignments. All **90 controlled revision lifecycle cycles** passed, and the system rejected **all 600 tested changes to proofs or their context**. Those numbers describe our tests, with the limits we'll get to below.

## A quick look at agent memory

An agent often needs something from an earlier conversation: a project decision, a test result, a user preference, or a rule another agent was given.

Being able to find that information later is useful. But in our release example, finding the sentence “the release is ready” doesn't tell us enough. We still need to know what supported it, which version it described, and whether any of those supporting facts have changed.

We wanted to be able to follow that trail.

That starts with keeping the things we were told separate from the conclusions we drew. “The tests passed” is an accepted statement. “The release is ready” may be a conclusion that depends on it. Keeping that connection lets us revisit the conclusion when the test result changes.

## Why we start with propositions

Consider three statements about one particular release:

- API v2 is active.
- The tests pass.
- The release is ready.

Each statement needs a clear meaning and must refer to the same release. We can then write a rule connecting them:

**(API v2 active AND tests pass) → release ready**

If we've accepted the first two statements, this rule gives us the third. We can save both the answer and the statements that led to it.

There's a small detail here that's easy to miss: the arrow goes one way. This rule alone doesn't say that failed tests make a release unready. Another policy might still allow it.

For the correction in our example to rule out readiness, we need to say that explicitly:

**NOT tests pass → NOT release ready**

Now, when the corrected result says the tests failed, we have a stated reason to conclude that the release isn't ready. We haven't left the system to fill in that rule for itself.

In the app, users define what each proposition means and write formulas using operators such as AND, OR, and NOT. That takes more care than typing a sentence, but it makes the meaning visible. Turning free-form conversation into reliable formulas is a separate problem.

## Where a statement came from, and what follows from it

A test report tells us where “the tests passed” came from. The release rule tells us how that statement supports “the release is ready.” We keep both.

The source gives us something to inspect. The proof gives us a way to check the reasoning.

Of course, a correct proof can't fix a wrong test report. It tells us what follows from the statements we accepted. Someone still needs to decide whether those statements deserve to be accepted in the first place. That's why sources and operator review are part of the workflow.

## What the graph remembers

We use FalkorDB to connect the pieces: workspaces, saved memory revisions, accepted statements, formulas, evidence, and answers. Each revision is kept as it was, and every saved answer names the revision it used.

When an answer has a checked proof, we record links to the statements used in that proof. Otherwise, we take the cautious route and link it to the whole memory snapshot. After a correction, the impact view uses those links to find answers from the immediately preceding revision that need another look.

Finding an affected answer doesn't mean it's wrong. There might be another way to reach the same conclusion using the remaining facts. The links help us find what to revisit; asking the question against the new revision tells us whether the answer changes.

Here's how the pieces fit together:

![Five stages: sourced input, FalkorDB revision graph, Z3 logical query, independent proof check, and saved answer.](figures/02-architecture.png)

*FalkorDB keeps the memory and its connections. Z3 checks what follows from all the accepted statements. In certificate mode, a separate program checks the generated proof and the context it belongs to.*

We check the whole accepted snapshot because a few retrieved statements might leave out a contradiction elsewhere in the memory. The consistency check needs to see that conflict before we give an ordinary logical answer.

## When a premise changes

Let's return to the release example and follow the correction:

![Six steps show initial acceptance, a checked answer, a correction, dependency traversal, rechecking, and preserved history.](figures/03-revision-walkthrough.png)

*The question stays the same. The accepted facts change. Each answer keeps the version of the memory that supported it.*

Say we're at revision 12; these numbers are just for the example. The memory says API v2 is active and the tests pass. Under our release policy, the release is ready. We check the proof and save the answer with that revision.

An operator then replaces the test statement using the corrected report. We now have revision 13. Revision 12 and its original answer are still there.

The graph helps us find the affected answer from revision 12. A reader can ask the question again at revision 13, where the failed-test rule gives us a different result: the release isn't ready. This rerun is an explicit step; finding an affected answer doesn't automatically recompute it.

The old proof can still be correct for the old facts. It just doesn't tell us whether the release is ready now. Keeping both versions lets us explain what changed without rewriting the history.

This also matters when two people or agents write at once. Each update names the revision it expects to change. If someone else has already moved the workspace forward, the stale update is rejected. And if a proposed addition contradicts the accepted memory, we keep it in quarantine for inspection without adding it to the active facts.

## What an answer actually means

Before answering, we check that the accepted statements can all hold together. If they can, a question has three possible logical outcomes:

- **PROVED:** the accepted statements imply the answer is yes.
- **REFUTED:** they imply the answer is no.
- **UNKNOWN:** either answer is still possible given what we know.

“Unknown” is an answer we want the system to be comfortable giving. If approval isn't recorded, that doesn't mean it was denied. We may simply not know yet.

If the memory contradicts itself, we say so. If the solver can't finish, we report that separately too. Those cases need different responses from a normal unknown answer.

In certificate mode, a yes or no answer triggers an attempt to build a proof certificate within a fixed budget. If that succeeds, a separate checker goes through the proof and checks that it belongs to the right workspace, revision, question, and accepted statements. For an unknown answer in this mode, we check two assignments: one where the query is true and another where it's false, both compatible with the memory.

We implemented and tested the checker separately from the generator. We haven't formally verified it in a proof assistant. There's also an explicit solver-only mode in the app, and the interface keeps the solver's answer separate from whether a certificate was verified.

## What the experiments showed

We benchmarked the implementation as it stood, keeping its existing limits. We used fixed seeds and three fresh Python worker processes, and published the setup, raw results, and exact source revision so others can inspect the run.

The **3,000 problems** were evenly split across proved, refuted, unknown, and inconsistent-memory outcomes. Every classification matched a separate evaluator that tried all possible truth assignments. All returned example assignments also passed that independent check.

We also ran **90 controlled lifecycle cycles**, checking corrections, preserved historical answers, stale writes, and related safeguards. All passed. To test the certificate checks, we made **600 changes across 60 valid certificates**, including damaged proof content and mismatched workspace or revision information. Every altered case was rejected by the combined proof and context checks.

In a smaller subset of generated problems with yes or no answers, **234 of 240 queries received independently checked certificates**. The other six hit the proof budget and stayed uncertified.

![Measured correctness, lifecycle and mutation checks, alongside the separate scaling experiment's certificate coverage.](figures/04-measured-results.png)

*The smaller certificate sample and the scaling workloads are separate experiments. The chart shows why the result from one shouldn't be applied to the other.*

## Where the current approach needs work

The biggest thing to improve is **proof generation as the memory grows**. In the separate scaling workloads, every decisive request at four and eight assertions received a certificate. That dropped at 16 and 32. At 64, 128, and 256 assertions, none received a verified decisive certificate. The logical answers were still correct, but our bounded generator couldn't produce the proofs. That's the next part of the implementation we need to improve.

The other limit is **what we tested**. These were synthetic Boolean problems, and the API tests used an in-memory store. They don't tell us how well the system understands everyday language, whether a source is telling the truth, or how fast a live FalkorDB deployment would be. Those need their own experiments.

## How this connects to earlier ideas

Keeping reasons behind beliefs has a long history. Jon Doyle's [work on truth maintenance](https://dspace.mit.edu/handle/1721.1/5733) describes maintaining reasons and revising beliefs when assumptions change. Separately checked solver certificates are also established practice, illustrated by [work on LRAT proof checking](https://arxiv.org/abs/1612.02353). Temporal graph frameworks such as [Graphiti](https://github.com/getzep/graphiti) also address changing, interconnected information for agents.

We're bringing those ideas together in a shared-agent workflow: explicit propositions, a graph that preserves revisions, and answers that can carry separately checked proofs. The useful contribution is in how those pieces work together and what we can measure about them.

## Questions we want to explore next

First, we want to improve certificate generation while keeping the separate checks and the connection to the full memory revision.

We'd also like to make propositions easier to write. A language model could suggest a formula and point to its source, with a person reviewing what the formula actually says before accepting it.

Then there's testing the whole graph-backed workflow with persistence and several users working at once. Having a reproducible benchmark gives us something concrete to compare against as we make those changes.

## A different starting point for shared memory

We started with a small question: when an agent remembers an answer, can it also remember how it got there?

In the release example, that means keeping the question, the test result, the release rule, the sources, and the revision where we checked the reasoning. When the test result changes, we have a trail to follow back to the answer.

That's what we want memopops to make easier: knowing why an answer made sense at the time, and knowing when it's time to ask again.

---

*Built by Mohammad Saqlain and Mahavir.*

[Explore the source code](https://github.com/SaqlainSQX/memopops) · [Read the benchmark report and access the raw results](https://github.com/SaqlainSQX/memopops/blob/main/docs/evaluation/benchmark-2026-10-25/REPORT.md)
