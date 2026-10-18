# Local submission setup

This is the intended full local path, checked against repository configuration on October 18. It still needs the clean-clone/database rehearsal in [PLAN.md](PLAN.md); successful unit tests do not establish that rehearsal. No public application hosting is required.

## Prerequisites

- Docker Desktop with its Linux engine running, and Docker Compose.
- Node.js 24/npm for the web inspector, matching the release notes.
- Python 3.12 and `uv` for host-side agent tools, tests, and certificate checking.
- Available local ports 6379 (DB), 8000 (API), 5173 (web).

Start in a fresh clone of [the repository](https://github.com/Mvdodiya001/memopops):

```powershell
git clone https://github.com/Mvdodiya001/memopops.git
Set-Location memopops
Copy-Item .env.example .env
```

The copy command is for a fresh clone only. Preserve any existing private `.env`. Edit `.env` privately: replace the DB password and reader/writer/operator token keys with distinct local values. All three identities must point to `workspace_demo`. Keep the role strings unchanged. No Google/model key is required for the scripted path. Do not paste `.env` into public logs.

## Database and API

```powershell
docker compose config --quiet
docker compose up -d --build
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready
docker compose exec api python -m scripts.seed_demo
```

Wait for readiness before seeding. Expect `rev_001`, four assertions, four registered atoms. Seeding again verifies the original seed; it does not reset an already-corrected workspace. If a container fails, inspect its logs privately; do not capture credentials for the video.

Compose binds its ports to loopback and stores FalkorDB data in a named volume. Stop without deleting data using `docker compose down`. Never use volume deletion as an incidental retry step.

## Web inspector (separate terminal)

Run from the repository root:

```powershell
npm --prefix apps/web ci
$env:MEMOPOPS_API_ORIGIN = 'http://127.0.0.1:8000'
npm --prefix apps/web run dev
```

Open `http://127.0.0.1:5173`. Do not enable `source=development`. Enter the **reader token key** chosen in `.env` in the live connection form, off camera. Select `workspace_demo`; inspect memory and query `release_ready`. Expect PROVED with VERIFIED proof status at the initial revision. Try `docs_signed` for UNKNOWN.

The explicit API origin is essential: Vite otherwise proxies to port 8010, used by the synthetic test harness. The frontend is not a service in the current Compose file.

## Host tooling

```powershell
uv sync --locked --group dev
uv run --locked pytest -q
uv run --locked python -m evaluation.run --suite acceptance --output .artifacts/acceptance
```

The acceptance command is **in-memory**, even when local FalkorDB is running. It does not validate DB persistence. Do not run `scripts/run_agent_demo.py --mode remote` as though it already performs the full recording sequence: the runner gaps and required stages are documented in [PLAN.md](PLAN.md). Use the repaired staged runner only after its real-API path has been tested.

Download a verified certificate from the inspector, then check its mathematics:

```powershell
uv run --locked python -m proofcheck path/to/certificate.json
```

Without `--expected-context`, the CLI intentionally reports provenance UNVERIFIED. The API's VERIFIED label additionally checks a trusted context from the independently loaded revision. Do not manufacture that trusted context from the same certificate.

## Recording/restart checklist

Use the operator API for the conflict/replacement stages; reader/writer credentials cannot commit accepted memory. Save query/revision IDs before changing revisions. After correction, restart the API and DB containers with their existing volume, wait for readiness, and verify r2 plus the old r1 certificate still load. The complete acceptance path and safeguards are in [PLAN.md](PLAN.md).
