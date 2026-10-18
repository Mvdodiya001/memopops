# Demo storyboard (about 3.5 minutes)

Use the expanded [recording plan and implementation notes](plan/VIDEO_DEMO_PLAN.md), [3:30 narration](submission/VIDEO.md), and [execution gates](submission/PLAN.md) for final production. Full local startup is in [LOCAL_SETUP.md](submission/LOCAL_SETUP.md).

`scripts/demo_video.py` now stages the complete correction flow. With `--model live`, Gemini Flash chooses calls from the bounded reader/writer tool declarations and the existing `AgentSession` validates and executes them. If the model is unavailable, that scene falls back to deterministic replay and prints **Scripted replay**. Keep the printed mode label visible in the recording; never describe fallback footage as live model output.

1. **Problem (0:00–0:20)** — Two agent identities share memory; a later correction can invalidate an earlier conclusion.
2. **Proof (0:20–0:55)** — Reader queries `release_ready` at revision 1; show verified certificate and supporting assertions.
3. **Uncertainty (0:55–1:15)** — Query `docs_signed`; show UNKNOWN / not established.
4. **Conflict (1:15–1:45)** — Writer proposes inconsistent data; show quarantined proposal and unchanged head.
5. **Correction (1:45–2:15)** — Operator replaces `tests_pass`; history impact lists the old `release_ready` query; resumed reader gets REFUTED at r2.
6. **Verification (2:15–2:40)** — Export certificate; run `python -m proofcheck`; tamper one step and show rejection.
7. **Limits (2:40–3:00)** — Show FalkorDB traversal or README query; state bounded logic and accepted-premise dependence.

## Commands

```bash
# Full narrated run against a configured API and FalkorDB.
PYTHONPATH=.:src:packages/proofcheck/src uv run --locked python scripts/demo_video.py \
  --api-base http://127.0.0.1:8001 --model live --pause --take 1

# Deterministic dry run through the same service contracts.
PYTHONPATH=.:src:packages/proofcheck/src uv run --locked python scripts/demo_video.py \
  --api-base http://127.0.0.1:8001 --model scripted --take dry

# Reset only workspace_demo before a retake; all other graphs are preserved.
PYTHONPATH=.:src:packages/proofcheck/src uv run --locked python scripts/reset_demo_workspace.py --yes
```

The runner writes redacted journals, a summary, valid and tampered certificates, and reusable Cypher under `.artifacts/video-demo/take-<id>/`. The writer scene is deliberately honest: writer credentials are denied activation; a trusted operator submits the same observation for consistency checking, and the conflicting proposal is quarantined.

For the older in-memory lab replay, use:

```bash
MEMOPOPS_AUTH_TOKENS='{"reader-token":{"workspace_id":"workspace_demo","role":"reader"},"operator-token":{"workspace_id":"workspace_demo","role":"operator"}}' \
  uv run --locked python -m scripts.run_agent_demo --mode lab --output .artifacts/agent-demo
```
