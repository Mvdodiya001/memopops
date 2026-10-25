# Blog-ready interpretation

## A defensible paragraph

> We evaluated memopops on 3,000 unique synthetic propositional problems, balanced across proved, refuted, unknown and inconsistent-memory outcomes. Across three fresh Python processes, every classification matched a separate exhaustive truth-table evaluator, and no returned witness failed independent evaluation. In a sampled subset of 240 decisive queries, the bounded proof generator produced 234 independently checked certificates; six requests correctly remained uncertified after reaching the proof budget. We also rejected all 600 mathematical/context mutation probes across 60 valid certificates, and passed 90 controlled revision lifecycle cycles. These measurements evaluate explicit Boolean reasoning and a synthetic in-process API store; they do not measure natural-language memory quality, source truthfulness or FalkorDB performance.

## The important negative result

Certification does not currently scale with the solver. At 4 and 8 assertions, all 180 decisive API requests at each size were independently certified. At 16 and 32, 60/180 were certified at each size, with coverage varying by workload shape. At 64, 128 and 256, none of the 180 decisive requests per size received a certificate. The logical classifications still matched the expected constructed answers, and the API correctly returned BUDGET_EXCEEDED rather than claiming VERIFIED.

Untimed diagnostic reruns reproduced a derived-clause-budget refusal for all six generated-corpus failures. Representative scaling probes show the same derived-clause limit for 16-assertion chains/fan-out, followed by the initial-clause bound for larger chains/fan-out. Distractor-heavy inputs retain a short logical support, but their complete-snapshot encoding eventually exceeds that initial-clause bound too. See the separate diagnostic JSON files; those retries never replace primary observations.

This result identifies an engineering bottleneck worth discussing: the complete-snapshot solver remains useful beyond the range of the bounded resolution proof generator. Improving certificate generation, while preserving independent context checking, is future work. The benchmark did not alter limits or optimize the implementation to improve its score.

## Latency claims that match the data

- At four accepted assertions, direct classifier p50/p95 was 8.422/13.650 ms; solver-mode API was 16.577/23.588 ms; certificate-mode API was 17.911/26.244 ms. All decisive API certificates at that size verified.
- At 256 assertions, direct classifier p50/p95 was 22.512/38.040 ms; solver-mode API was 40.270/54.931 ms; certificate-mode API was 48.330/66.333 ms. **No decisive certificate verified at that size**, so its certificate-mode latency must not be described as verified-proof latency.
- Each size pools an equal mix of three structured workload shapes and three logical outcomes. The 128/256-assertion cases use capped vocabulary and redundant rules; they are not implication chains of those depths.
- Hardware: Intel Core i7-14650HX, 24 logical CPUs, approximately 16 GB RAM, Windows 11, Python 3.12.13 and Z3 5.3.1.0. Three sequential fresh worker processes, fixed seeds, discarded warmups, randomized measurement order. Raw samples and per-process medians are published.

## Control interpretation

The recomputing solver control answered the current question correctly in all 90 correction cycles. The deliberately stale query-only cache answered none correctly after the correction. That contrast illustrates stale-cache behavior by construction. It does **not** show a 100-point improvement over RAG, Mem0, Zep or any other real memory system, and it does not show the certificate layer improving the underlying solver's logical accuracy.

At concurrency 32, the local in-process API returned 162 successful responses and 126 HTTP 429 responses out of 288 requests. This demonstrates admission control under this specific synthetic burst, not a deployed service capacity estimate. Include refusals in the denominator.

## Artifacts

- [Full results and limitations](REPORT.md)
- [Measurement protocol](../../BENCHMARK_PROTOCOL.md)
- [Machine-readable summary](summary.json)
- [Manifest and raw-data checksums](manifest.json)
- [Raw observations](observations.csv)
- Figure: `latency-and-coverage.png` or the editable vector `latency-and-coverage.svg`.

The primary measured harness commit is recorded in manifest.json. The plotting and diagnosis tools are post-run analysis utilities and do not change the measured code or observations. Source commit and SHA256 hashes are published so the article can identify the precise implementation tested.
