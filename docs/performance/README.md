# Local performance measurements

## Solver classification baseline — 2026-10-17

This is a local Z3 classification measurement, not end-to-end service latency. It excludes FalkorDB reads/writes, FastAPI and HTTP overhead, proof generation, and independent certificate checking. Database-dependent measurements will be added after the hosted instance is available again.

The benchmark script commit is `7c30d3960100e6516ff7a442ce753ddd267e3874`. The machine ran Windows 11, Python 3.12.13, Z3 5.3.1, and 24 logical CPUs (Intel64 Family 6 Model 183). Each workload performs ten warm-ups followed by three independent runs of 100 measured calls. Quantiles below combine all 300 retained samples per size and use nearest-rank selection. The exact sample values and per-run counts are in [solver-baseline-2026-10-17.json](solver-baseline-2026-10-17.json).

| Active assertions | Samples | p50 (ms) | p95 (ms) | Results | Timeouts |
| ---: | ---: | ---: | ---: | --- | ---: |
| 10 | 300 | 8.591 | 12.220 | 300 PROVED | 0 |
| 50 | 300 | 10.799 | 15.972 | 300 PROVED | 0 |
| 100 | 300 | 12.522 | 19.260 | 300 PROVED | 0 |
| 256 | 300 | 20.513 | 29.591 | 300 PROVED | 0 |

The deterministic workload asserts the first atom, adds a chain of implications through the remaining atoms, and queries the final atom. It tests a simple satisfiable proof path; it does not represent hard worst-case Boolean formulas. Run the same protocol with:

```powershell
uv run --frozen --no-sync python scripts/benchmark_solver.py --output docs/performance/solver-baseline-2026-10-17.json
```

The report is a baseline for the current local environment, not a promise about other machines or database-backed queries. It should be supplemented with separate database, certificate, checker, and end-to-end measurements before making a service latency claim.
