# Demo storyboard (about 3 minutes)

Label scripted replays as **Scripted replay**, not live model output.

1. **Problem (0:00–0:20)** — Two agent identities share memory; a later correction can invalidate an earlier conclusion.
2. **Proof (0:20–0:55)** — Reader queries `release_ready` at revision 1; show verified certificate and supporting assertions.
3. **Uncertainty (0:55–1:15)** — Query `docs_signed`; show UNKNOWN / not established.
4. **Conflict (1:15–1:45)** — Writer proposes inconsistent data; show quarantined proposal and unchanged head.
5. **Correction (1:45–2:15)** — Operator replaces `tests_pass`; history impact lists the old `release_ready` query; resumed reader gets REFUTED at r2.
6. **Verification (2:15–2:40)** — Export certificate; run `python -m proofcheck`; tamper one step and show rejection.
7. **Limits (2:40–3:00)** — Show FalkorDB traversal or README query; state bounded logic and accepted-premise dependence.

## Commands

```bash
# Scripted two-client path (no FalkorDB)
uv run --locked python scripts/run_agent_demo.py --mode lab --output .artifacts/agent-demo

# Full stack (requires .env and Docker)
docker compose up -d --build
docker compose exec api python scripts/seed_demo.py
```
