#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== Backend =="
uv sync --locked --group dev
uv run --locked pytest -q
uv run --locked python -m compileall -q src tests packages/proofcheck/src scripts agents evaluation
uv run --locked python -m unittest discover -s tests/proofcheck -q

echo "== Web =="
npm --prefix apps/web ci
npm --prefix apps/web run typecheck
npm --prefix apps/web test
npm --prefix apps/web run build

echo "== Acceptance (lab) =="
uv run --locked python -m evaluation.run --suite acceptance --output .artifacts/acceptance-verify

echo "Release verification finished."
