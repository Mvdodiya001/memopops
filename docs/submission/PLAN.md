# Submission execution plan

Prepared October 18, 2026, around 11:50 IST, against implementation commit `e9bd8c3`. The user chose **no public application deployment**. This package plans the remaining work; it does not claim that a video, blog, or submission has been published.

## Decision

Submit **memopops — Proof-Carrying Memory for AI Agents** to **Track 02: Agent Memory and Coordination**. Tell one story: a reader makes a decision from shared memory, a test report is corrected, and the reader must reconsider using the new revision. Use the configured hosted FalkorDB-backed application. `scripts/demo_video.py --model live` uses Gemini Flash native function calling through the guarded `AgentSession`; every scene prints a truthful live-model or scripted-replay label.

Deliver a 3:30 narrated YouTube demonstration, a public technical blog, complete local setup, an implemented graph model with Cypher examples, and concise form answers. Video duration is our editorial choice, not an organizer-imposed limit.

The [official rules](https://www.wemakedevs.org/hackathons/falkordb/rules) allow complete local setup instead of deployment. They still require a working video, public source, graph model, core queries/algorithms, a named track, and AI-assistance disclosure. FalkorDB must perform central work. Deadline: **October 18, 2026, 23:59 IST**. The supplied submission form specifies a public or unlisted **YouTube** link. Leave deployment blank; do not put localhost there.

## Evidence audit

| Item | Observation on October 18 | Required next action |
| --- | --- | --- |
| Final code | Clean checkout; implementation `e9bd8c3`; fetched main matches | Record final published commit after any fixes |
| Backend | **144 pytest tests passed** | Tie counts to tested code, not older 138-test notes |
| Frontend | Typecheck, **8 tests**, production build passed | Rehearse live UI against real FalkorDB |
| Acceptance | **4/4 cases passed**, in-memory lab | Two check expected baseline weaknesses; this is not four independent accuracy wins |
| Performance | Existing solver-only samples, p95 12.220–29.591 ms for documented simple workloads | No database, proof-generation, or end-to-end latency claim |
| Graph model | Implemented storage differs from the original planned operator-node model | Use [GRAPH_MODEL.md](GRAPH_MODEL.md) |
| Local launch | Compose starts database/API; web runs separately | Rehearse [LOCAL_SETUP.md](LOCAL_SETUP.md) from a clean clone |
| Demo startup | Direct-file runner fails importing `agents`; bare module invocation checks tokens before lab defaults | README now has a tested module + explicit synthetic-token workaround; improve default startup separately |
| Narrated runner | `scripts/demo_video.py` includes reader, uncertainty, writer denial/operator quarantine, correction, resume, checker, and graph stages | Rehearse scripted and live modes against the hosted instance |
| UI correction | UI adds atom assertions and displays proposals/history/impact | Use an operator API call for replacement; no replace UI exists |
| Database | This audit did **not** start or contact one | Complete real correction/persistence checks before recording |
| Video/blog | No public URLs created by this task | Record, upload, publish, check signed out |
| Public repo | Git fetch worked; anonymous web verification inconclusive in this tool | Open repository signed out before submitting |

## 1. Freeze scope and assign work — 15 minutes

- Keep the title above; avoid another concept rename.
- Use synthetic release demo-42 data. Show both explicit policies: API availability plus passing tests implies readiness; failing tests implies not ready. The second rule is not inferred from the first.
- Keep the runner's per-scene label visible. An operator activates trusted observations; writer credentials cannot promote accepted memory. The runner shows writer denial, then a distinct operator validation call that persists the conflicting proposal as quarantined.
- PROCEED/BLOCK receipts record decisions; they do not ship software.
- Use separate checkouts. This is a proposed division of work, not a record of delegation or messages sent.

## 2. Close reproducibility gaps — 60–90 minutes

Saqlain prepares the real DB/API path and operator correction calls. Mahavir fixes agent demo tooling in his own checkout. Agree these interfaces first:

1. Use module invocation when scripts import root packages: `uv run --locked python -m scripts.run_agent_demo ...`. Pytest's extra import paths do not exist in a fresh Python process.
2. For default-startup polish, initialize lab defaults **before** validating lab tokens and test a fresh process without auth. Until then, the explicit synthetic-token README example is a verified lab workaround; it does not establish database behavior.
3. Real-API mode must select actual reader/operator token values from private configuration. Do not assume literal `reader-token`/`operator-token` match a judge's `.env`. Keep credentials out of arguments and journals.
4. Provide explicit stages: initial reader, conflicting operator add, accepted operator replacement, resumed reader. Retain sanitized query/revision IDs for UI inspection. Never reset a database automatically between stages.
5. Resume from the correct persisted journal in a **new process**. Show stale r1 decision rejection, reread r2, and a new current decision. Keep idempotency behavior consistent on retries.
6. Run agent tooling on the **host**. The current API Dockerfile copies neither `agents/` nor `evaluation/`; do not document agent commands inside that image without updating and testing it.
7. Set `MEMOPOPS_API_ORIGIN` to Compose's API port **8000**. Vite defaults to **8010**, the synthetic browser harness port.

The focused function-calling adapter and narrated runner are implemented in this branch. Do not expand them into a multi-provider model framework.

## 3. Establish real FalkorDB behavior — 60 minutes

Use local Docker FalkorDB `v4.22.0` and production `FalkorSnapshotStore`, with development fixture mode disabled. The seed refuses to reset a workspace advanced beyond `rev_001`. Preserve existing work/volumes. For another take, reuse footage, select historical revisions, or deliberately provision a separate disposable environment.

| Step | Action | Required evidence |
| --- | --- | --- |
| 1 | Seed and inspect | Four assertions/four registered atoms; actual DB/API readiness |
| 2 | Query `release_ready` at r1 | PROVED + VERIFIED, saved query ID and certificate |
| 3 | Query `docs_signed` | UNKNOWN; no evidence does not mean false |
| 4 | Operator adds `NOT tests_pass` beside `tests_pass` | QUARANTINED proposal; unchanged r1 head/membership |
| 5 | Operator replaces `as_tests_pass` with `NOT tests_pass` atomically | COMMITTED r2; old assertion remains in r1 |
| 6 | Select r2 history impact | The r1 readiness query appears because its support used the removed assertion |
| 7 | Resume reader in new process | Stale decision gets 409; read r2, REFUTED + VERIFIED, record BLOCK |
| 8 | Restart API and then DB container, preserving volume | r2 memory and original r1 query/certificate remain retrievable |
| 9 | Check export and corrupted copy | Original mathematics pass; changed certificate fails |

Store raw sanitized outputs under ignored `.artifacts/submission/`; publish only reviewed synthetic evidence. A working lab replay alone does not establish FalkorDB use. If local Docker access fails, resolve it or use the configured hosted FalkorDB for recording. Lab-only footage is not the primary submission fallback.

## 4. Rehearse judge setup — 30–45 minutes

Mahavir follows [LOCAL_SETUP.md](LOCAL_SETUP.md) from a clean clone and his own disposable environment. Record missing dependencies, wrong ports, import failures, or absent commands. Saqlain handles backend/infrastructure fixes; Mahavir handles UI/agent tooling. Test fixes, integrate current main, and push directly without PRs.

Done means README-linked instructions let someone start FalkorDB, seed memory, open the real UI, query `release_ready`, and locate the core Cypher. Cached builds and lab tests alone do not complete this gate.

## 5. Record/edit video — 90 minutes

Follow [VIDEO.md](VIDEO.md). Saqlain narrates and drives the rehearsed real app; Mahavir checks shots and captures screenshots from the same run. Save the complete working sequence before editing. Trim pauses and add restrained labels/captions. Keep the original recording. No slide deck, intro animation, or music is needed.

## 6. Write/publish blog in parallel — 90 minutes

Follow [BLOG_BRIEF.md](BLOG_BRIEF.md). Mahavir drafts while Saqlain prepares the database; complete screenshots and evidence after rehearsal. Saqlain reviews technical claims; both humans verify the account of their contributions. Use an existing public blogging account. Default to DEV Community if a platform must be chosen; an existing Hashnode/personal blog is fine. This does not require hosting the application.

## 7. Publish links and submit

1. Upload MP4 to YouTube as Unlisted or Public. Allow time for HD processing; watch the full video signed out.
2. Publish the blog; open its public URL signed out. A Markdown draft is not a submitted blog URL.
3. Add actual links and real screenshots to README. Replace pending placeholders.
4. Open the repo signed out; confirm current main contains setup, graph model, queries, AI disclosure, and artifact links.
5. Paste [FORM_ANSWERS.md](FORM_ANSWERS.md), select Track 02, leave deployment blank, and complete actual team details requested by the site.
6. Submit and retain the confirmation locally. Both humans verify URLs and track. Saving an editable draft is not proof of submission.

## Proposed parallel schedule — October 18, IST

| Window | Saqlain / this agent lane | Mahavir / his agent lane | Gate |
| --- | --- | --- | --- |
| 12:00–13:30 | DB/API, graph docs, operator stages | Runner startup/remote stages; blog outline | Real stack and staged path runnable |
| 13:30–14:30 | Correction/resume/restart checks | Clean-clone rehearsal; evidence checklist | Real database behavior established |
| 14:30–15:30 | Record narration and app | Real-state screenshots; blog draft | Complete raw working video |
| 15:30–17:00 | Edit/upload video early | Finish/publish blog; setup review | Two public artifact URLs |
| 17:00–18:00 | Review form/technical claims | Full video watch; signed-out links | Submission draft complete |
| By 21:00 | Submit and verify receipt together | Submit and verify receipt together | Buffer before 23:59 deadline |

Starting later: preserve the dependency order. Cut optional live model calls, graph animation, custom covers, benchmark reruns, and extra tracks first. Preserve the working FalkorDB video, local setup, and clear graph explanation. The blog is optional in the form but requested by the user; shorten it rather than invent results.

## Completion definitions

- **Repository:** public access verified; local recipe rehearsed; implemented schema/core Cypher linked; AI disclosure present; claims match final code.
- **Video:** real database flow, truthful live/replay labels, visible revision change, clear audio, accessible YouTube URL.
- **Blog:** public post, original problem/story, implemented details, real images, evidence limits, source/video links, human review.
- **Submission:** organizer confirmation retained and both humans checked all final fields. None of these becomes complete merely by having this plan.
