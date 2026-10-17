# Submission checklist (Track 02)

Authoritative rules: [FalkorDB Graph Hacks](https://www.wemakedevs.org/hackathons/falkordb). Deadline: **October 18, 2026, 23:59 IST**.

## Repository

- [x] Public GitHub repo linked; final commit hash recorded (`434ad4e` on `main` as of 2026-10-17 IST).
- [x] README: problem, setup, FalkorDB role, demo commands, limits, evaluation summary.
- [x] `scripts/verify_release.sh` passes on a clean machine with Node 24 and Python 3.12 (138 pytest, web CI, 4/4 acceptance).

## Demo evidence

- [ ] Video (signed-out link check) or complete local instructions.
- [ ] Screenshots from real UI states (not fixture mode unless labeled).
- [x] Measured evaluation: `docs/evaluation/README.md` and `docs/evaluation/acceptance-sample-report.json`.

## Technical talking points

- One Cypher traversal for premise/evidence or revision membership.
- How entailment is tested (complete snapshot + Z3).
- Revision guard and idempotency receipts.
- What the independent checker verifies.

## AI assistance disclosure

State which parts used AI coding assistants (planning, backend, UI, tests) and that humans reviewed commits, tests, and demo claims. Do not claim live model autonomy when the recording used scripted replay.

## Not done in this repository

- Team registration on the organizer site.
- Public deployment (local Compose + video is the supported fallback).
- Live model writer/reader without explicit credentials and labeling.
