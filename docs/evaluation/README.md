# Evaluation

Scripted replay compares memopops against two intentionally weak baselines:

1. **Naive shared notes** — caches the last answer and labels it current without revision checks.
2. **Solver-only ablation** — recomputes Boolean results but omits guarded publication and revision-aware decisions.

## Run acceptance (no FalkorDB)

```bash
uv run --locked python -m evaluation.run --suite acceptance --output docs/evaluation/acceptance-run
```

The command writes `report.json` (case summary) and `sessions.json` (sanitized agent journals) under the output directory.

## Scripted agent demo

```bash
uv run --locked python scripts/run_agent_demo.py --mode acceptance --output docs/evaluation/acceptance-run
uv run --locked python scripts/run_agent_demo.py --mode lab --output .artifacts/agent-demo
```

`remote` mode requires `MEMOPOPS_AUTH_TOKENS` and `--api-base` pointing at a running API.

## Claims

Report pass/fail counts only. Do not describe scripted replay as a live model conversation.
