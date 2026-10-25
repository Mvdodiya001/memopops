# memopops blog benchmark protocol

This protocol evaluates the current implementation, not a new reasoning algorithm. Source revision, benchmark-source hash, seeds, configuration, environment and raw observations accompany every run. Product solver/checker limits stay unchanged. This is a synthetic single-machine engineering evaluation, not a comparison against another memory product.

## Predeclared run

- Seeds: 20261025, 20261026, 20261027. Run each in a fresh Python process, sequentially to avoid benchmark workers competing for CPU.
- Correctness: 1,000 unique generated cases per seed, balanced across PROVED, REFUTED, UNKNOWN and INCONSISTENT_MEMORY. Two to six atoms; zero to five premises; nested NOT/AND/OR/IMPLIES/IFF. A separate evaluator over raw JSON enumerates every truth assignment; it does not call Z3 or the product's formula evaluator.
- Extra proof checks: first 40 generated cases per decisive outcome per seed, plus 40 UNKNOWN cases. Record every generation refusal and limit; validate produced proofs with an independently constructed expected context. Validate UNKNOWN witnesses independently. Distinguish proof coverage from classification agreement.
- Mutation probes: up to 20 valid generated certificates per seed, with separately reported mathematical and context mutations. A changed context need not make the mathematics invalid; acceptance requires both logical validity and matching trusted context. These finite probes are not a security audit.
- Scaling: 4, 8, 16, 32, 64, 128 and 256 accepted assertions; chain, fan-out and distractor-heavy constructions; proved, refuted and unknown questions. At larger counts, cap active atom vocabulary and use explicit redundant rules to stay inside the public 128-proposition limit. Workload definitions are saved; these are easy structured inputs, not representative worst-case SAT instances.
- Direct classifier: 30 measured samples per outcome/family/size/process after 5 warmups. Formula parsing and fixture creation are outside the timed region.
- In-process API: 10 fresh (uncached) requests per outcome/family/size/mode/process after 5 warmups, in solver and certificate modes. Includes authentication, HTTP serialization/ASGI dispatch, revision loading from a synthetic store, solver-worker dispatch, optional generation/checking and in-memory persistence. Excludes real network and FalkorDB. One persistent HTTPX client/event loop per worker avoids per-request client startup. Modes are interleaved with a seeded schedule.
- Lifecycle: 30 fresh workspace cycles per seed. Accepted policy/fact, decisive query, contradictory addition/quarantine, explicit correction, fresh query, historical proof, stale decision rejection, role/tenant boundary and a two-writer expected-head race. Compare a fresh solver control with an intentionally stale query-only cache. The cache is a failure-mode control, not an implementation of Mem0, Zep, Letta or RAG.
- Contention: three batches of 32 solver-mode requests at concurrency 1, 2, 8 and 32 against the in-process API per process. Report successful throughput, HTTP statuses, successful-request latency and all-request latency separately. This exercises local admission/dispatch behavior, not production load capacity.

## Reporting

Reproduce from the repository root with the locked Python 3.12 environment (choose a new output path if it already exists):

```text
uv run --locked python -m evaluation.benchmark --output docs/evaluation/benchmark-2026-10-25 --seeds 20261025 20261026 20261027 --cases-per-seed 1000 --solver-samples 30 --api-samples 10 --warmup 5 --lifecycle-trials 30
```

Use `perf_counter_ns` wall-clock timings, discarded warmups, nearest-rank p50/p95/p99, raw samples, per-process summaries and pooled descriptive results. Show between-process variation; a pooled percentile is not a confidence interval. Report all requests, non-200s, SOLVER_UNKNOWNs, proof BUDGET_EXCEEDED/FAILED and exceptions. Small subgroups do not support stable p99 estimates.

For oracle agreement, report the actual number and distribution of generated unique cases. A Wilson interval describes the observed generated sample; it does not prove a deployment error rate or universal correctness. Repeated latency observations are not extra independent correctness cases. Never interpret passing regression tests as an accuracy benchmark on natural language.

Retain generated cases, raw observations, summary JSON, hashes and the exact command. State explicitly when a database phase is unavailable. If an implementation defect is found, preserve the failing baseline observations and identify any changed-source rerun separately.

## Boundaries

No LLM natural-language translation is evaluated. Facts/evidence are synthetic and accepted as test premises; factual truth is not assessed. No paid model, external competitor, container restart or user workspace is involved. Correctness of the API test store is separate from FalkorDB transaction semantics. Warmups exercise application paths but do not eliminate Windows scheduling, dynamic CPU frequency or other laptop activity.

Method references: [Google Benchmark guidance on warmup, repetition, interleaving and variance](https://google.github.io/benchmark/user_guide.html); [Python 3.12 high-resolution performance timing](https://docs.python.org/3.12/library/time.html#time.perf_counter_ns). This harness follows those measurement principles; it does not use the Google Benchmark library.

## Post-run analysis tools

`uv run --locked python -m evaluation.diagnose_benchmark PATH` performs separate untimed retries to explain observed proof limits; it never replaces primary observations. `evaluation/plot_benchmark.py PATH` renders the summary with matplotlib and verifies raw-data checksums first. Plotting is an optional analysis dependency, not a service dependency; the published figure used matplotlib 3.10.0 in a separate Python environment.

Interpretation details: uniqueness means distinct canonical raw JSON, not logical inequivalence; generated formula recursion depth is 0–3. The contention phase includes its initial request startup and has no separately discarded warmup. Those boundaries are visible in the frozen harness. Exact measured artifact bytes are preserved by the results directory's .gitattributes so checksums survive Git checkout on another platform.
