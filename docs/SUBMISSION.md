# Submission checklist (Track 02)

Authoritative rules: [FalkorDB Graph Hacks](https://www.wemakedevs.org/hackathons/falkordb). Deadline: **October 18, 2026, 23:59 IST**.

The current detailed instructions are in the [submission execution plan](submission/PLAN.md), with [form copy](submission/FORM_ANSWERS.md), [video script](submission/VIDEO.md), and [blog brief](submission/BLOG_BRIEF.md). Public application deployment is excluded by the user's decision; complete local setup **and** a working video are required for our chosen route.

## Repository

- [x] GitHub source linked and final implementation fetched; record `git rev-parse origin/main` at submit time.
- [ ] Anonymous public repository access checked at submission time.
- [x] README: problem, setup link, implemented graph model/core Cypher, limits, and AI disclosure.
- [x] October 18 local audit: 144 pytest passed; web typecheck/8 tests/build passed; 4/4 in-memory acceptance cases passed. Earlier 138-test release results remain historical notes in Mahavir's log.
- [ ] Complete database-backed setup rehearsed from a clean clone. Local unit/lab checks do not complete this gate.

## Demo evidence

- [ ] Working FalkorDB-backed video on YouTube, with signed-out link check.
- [ ] Complete local instructions rehearsed, including separate frontend/API port configuration.
- [ ] Screenshots from real UI states (not fixture mode unless labeled).
- [ ] Correction, resumed reader, and persistence across local container restart demonstrated.
- [x] Measured evaluation: `docs/evaluation/README.md` and `docs/evaluation/acceptance-sample-report.json`.
- [ ] Blog published and public URL checked; optional form field, requested project deliverable.

## Technical talking points

- One Cypher traversal for premise/evidence or revision membership.
- How entailment is tested (complete snapshot + Z3).
- Revision guard and idempotency receipts.
- What the independent checker verifies.

## AI assistance disclosure

README discloses AI assistance for planning, implementation, tests, UI, and documentation. Both humans must review the final claims and understand the code. Do not assert that every commit was human-reviewed unless that happened. Do not claim live model autonomy when the recording used scripted replay.

## Not done in this repository

- Team registration on the organizer site.
- Public deployment (local Compose + video is the supported fallback).
- Live model tool-calling writer/reader. The current optional model client returns plain text; the demo tool loop is scripted.
