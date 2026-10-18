# Video production plan and narration

Target: **3 minutes 30 seconds**, 1920×1080, 30 fps, clear human narration. This is our chosen length; no fixed limit was found in the checked organizer rules. Use the real local API/FalkorDB stack. Keep a small label visible in automated segments: **Scripted replay · synthetic release data · FalkorDB local**.

## Prerequisites

- All real-DB gates in [PLAN.md](PLAN.md) have passed, including correction, reader resume, and restart.
- The staged real-API driver works. The current unmodified remote runner alone cannot perform the full sequence.
- Prepare browser tabs: live inspector, history/impact, repository graph notes. Prepare a terminal for concise sanitized stage output and certificate checking.
- Connect reader/operator identities off camera. Keep private `.env`, bearer/API keys, database passwords, auth panels, and unrelated browser tabs outside the captured area.
- Use a fresh deliberate demo environment or saved historical views. Do not delete the working graph/volume to get another take.
- Record a ten-second audio sample and play it back before the full run.

## Timed storyboard and spoken script

| Time | Visible action | Narration |
| --- | --- | --- |
| 0:00–0:20 | Show r1 memory and an existing readiness result. Plain title: “What happens when an agent's facts change?” | “An agent can remember an answer after the facts behind it have changed. Another agent may then act on that old answer. We built memopops to keep shared memory, evidence, and decisions tied to the revision that actually supported them.” |
| 0:20–0:50 | Reader session queries `release_ready`; show revision, PROVED, VERIFIED, and supporting assertions. | “Here our reader checks release readiness. API v2 is available, tests pass, and an explicit rule connects those observations to readiness. The accepted memory comes from FalkorDB. Z3 checks the logic, and a separate checker verifies the small proof certificate. This answer belongs to revision one.” |
| 0:50–1:05 | Query `docs_signed`, show UNKNOWN and no decisive certificate. | “Ask whether the documentation is signed, and the result is unknown. Missing evidence does not become a negative fact. That distinction matters when a later agent decides what it can safely assume.” |
| 1:05–1:30 | Submit conflicting failure observation with operator credentials through the rehearsed API stage. Show QUARANTINED, proposal in UI, unchanged head. | “Now a new report says the tests failed. Adding that beside the passing report is inconsistent, so the operator submission is quarantined. It remains available for review, but it does not change accepted memory. Ordinary writer credentials cannot activate facts themselves.” |
| 1:30–2:00 | Perform atomic replacement through operator API. Open r2 history/impact and highlight the old readiness query. | “The operator corrects the report by replacing the passing assertion in one revision. The old assertion and proof remain in history. FalkorDB follows premise dependencies to find the earlier query that used this evidence. This says which support needs review; it does not automatically mean every affected conclusion is false.” |
| 2:00–2:30 | New reader process resumes saved journal. Show stale r1 decision rejected, reread r2, REFUTED + VERIFIED, BLOCK receipt. | “The reader resumes in a new process. Recording a current decision against the old head is rejected. After reading revision two, the readiness query is refuted, because our policy explicitly says failing tests block readiness. The reader records BLOCK against the new revision and query. No software deployment is performed.” |
| 2:30–2:55 | Export certificate, run checker, show success; run against a separately corrupted copy and show rejection. | “The certificate is portable. The independent checker accepts the original mathematics and rejects a tampered copy. The standalone CLI labels provenance unverified unless it receives independently trusted context. The API's verified status also binds the proof to the revision it loaded.” |
| 2:55–3:15 | Show implemented graph diagram/Cypher and a brief genuine post-restart retrieval. Cut labeled waiting time if necessary. | “FalkorDB holds revision membership, source evidence, and query-to-premise links. Those relationships power both memory reconstruction and correction impact. After restarting the local containers with the same volume, the new memory and the historical proof remain available.” |
| 3:15–3:30 | Return to clean UI; repository and local-setup link in end frame. | “This demo uses scripted agents and synthetic observations. The logic is bounded and only as factual as its accepted premises. The public repository includes the graph queries, independent checker, measured checks, and complete local setup for reproducing the workflow.” |

Only keep the restart sentence once that behavior is actually observed and captured. If a stage fails, fix/rehearse it; do not narrate a successful result over fixture footage.

## Exact recording sequence

1. Record an uninterrupted baseline take of the full real-DB sequence. Keep the original file locally, even if the submitted video is edited.
2. Save r1 query ID/certificate before applying correction; selecting r1 later must show the historical context visibly.
3. Capture the quarantine response and unchanged head before replacement.
4. Capture the operator replacement response; label it “Operator correction,” not an autonomous writer action.
5. In the UI, select the newly committed revision's history/impact. Save that frame before moving on.
6. Resume the reader using persisted IDs/journal in a new process. Show actual stale-write rejection and subsequent fresh decision.
7. Download certificate and copy it before tampering. Change a resolution inference field in the **copy**, run `uv run --locked python -m proofcheck ...`, and capture the actual failure. Keep the valid original.
8. Record actual container restart and subsequent retrieval. Shorten waits in editing with an honest “After container restart” label; do not fabricate timing.
9. Capture clean screenshots from this same real run: r1 proof, UNKNOWN, quarantine, r2 impact, r2 blocked result, and graph/schema view.

## Presentation choices

Use an existing screen recorder. Capture the application window and a prepared terminal, with a readable cursor and roughly 18–22 px terminal text. A 1080p/30fps recording is sufficient. Record a local test before committing to software installation or changing tools.

Keep the existing calm UI, neutral backgrounds, dark text, and one restrained accent. Crop consistently. Use short plain labels and readable captions; no neon, fabricated chat animation, stock footage, or dramatic claims. Keep failures/loading transitions real; trim only idle time. Music is unnecessary.

Publish screenshots only after checking they contain synthetic data and no credentials. The existing `apps/web/review/` screenshots include development/error states and are not substitutes for proof of the final database workflow.

## Upload and link validation

Use [YouTube Studio](https://studio.youtube.com/): Create → Upload videos, choose the final file, set audience/settings accurately, then set visibility to Unlisted or Public. **Unlisted** is our default because anyone with the link can watch without a Google account. Upload early and allow HD processing time. See [YouTube upload instructions](https://support.google.com/youtube/answer/57407?hl=en) and [visibility guidance](https://support.google.com/youtube/answer/157177?hl=en).

Open the resulting watch URL signed out on a second browser/device. Watch from start to end with sound, verify readable UI text, and paste that same URL into the submission, README, and blog. Do not use Private visibility.

## YouTube metadata draft

**Title:** memopops: When Shared Agent Memory Changes | Graph Hacks

**Description:**

```text
memopops is proof-carrying shared memory for AI agents.

Graph Hacks — Track 02: Agent Memory and Coordination
Repository: https://github.com/Mvdodiya001/memopops
Local setup: https://github.com/Mvdodiya001/memopops/blob/main/docs/submission/LOCAL_SETUP.md

This demonstration uses synthetic release observations and explicitly scripted agent clients against a local FalkorDB-backed API. An operator corrects accepted memory; a resumed reader rechecks its decision against the new revision. No external release action or public application deployment is performed.

FalkorDB stores memory revisions, provenance, and premise dependencies. Z3 supplies propositional reasoning, and a separate checker validates bounded certificates.

AI coding assistants supported planning, implementation, tests, UI, and documentation. Verification details and limitations are in the repository.
```

Add blog URL and actual chapter timestamps after the final edit. Do not paste planned timestamps if the cuts change them.
