"""Descriptive benchmark summaries; no unsupported deployment or competitor claims."""
from __future__ import annotations

from collections import Counter, defaultdict
import math
from pathlib import Path
from statistics import mean
from typing import Any


def quantile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    return sorted(values)[max(0, math.ceil(probability * len(values))-1)]


def latency(values: list[float]) -> dict[str, Any]:
    return {'n': len(values), 'p50_ms': quantile(values, .50), 'p95_ms': quantile(values, .95),
            'p99_ms': quantile(values, .99), 'min_ms': min(values) if values else None,
            'max_ms': max(values) if values else None, 'mean_ms': mean(values) if values else None}


def wilson(successes: int, total: int) -> list[float] | None:
    if total == 0:
        return None
    z = 1.959963984540054
    p = successes/total
    denominator = 1+z*z/total
    middle = (p+z*z/(2*total))/denominator
    margin = z*math.sqrt(p*(1-p)/total + z*z/(4*total*total))/denominator
    return [max(0.,middle-margin), min(1.,middle+margin)]


def summarize(rows: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, Any]:
    oracle = [row for row in rows if row['phase'] == 'oracle']
    correct = sum(row['correct'] for row in oracle)
    proofs = [row for row in rows if row['phase'] == 'proof']
    decisive = [row for row in proofs if row['expected'] in ('PROVED','REFUTED')]
    tamper = [row for row in rows if row['phase'] == 'tamper']
    groups = defaultdict(list)
    for row in rows:
        if row['phase'] in ('solver','api'):
            groups[(row['phase'],row['family'],row['assertion_count'],row.get('mode','solver'))].append(row)
    scaling = []
    for (phase,family,size,mode), group in sorted(groups.items()):
        seeds = sorted({row['seed'] for row in group})
        item = {'phase':phase,'family':family,'assertion_count':size,'mode':mode,
                'latency':latency([row['elapsed_ms'] for row in group]),
                'per_process_p50_ms':{str(seed):quantile([r['elapsed_ms'] for r in group if r['seed']==seed],.5) for seed in seeds},
                'outcomes':dict(Counter(row.get('actual') for row in group)),
                'http_statuses':dict(Counter(str(row['status_code']) for row in group if 'status_code' in row)),
                'proof_statuses':dict(Counter(str(row['proof_status']) for row in group if 'proof_status' in row))}
        relevant = [row for row in group if row['expected'] in ('PROVED','REFUTED')]
        if mode == 'certificate':
            item['decisive_requests'] = len(relevant)
            item['verified_decisive'] = sum(row.get('proof_status') == 'VERIFIED' for row in relevant)
            item['unknown_requests'] = len(group)-len(relevant)
            item['unknown_witnesses_verified'] = sum(row.get('witnesses_verified') is True for row in group if row['expected']=='UNKNOWN')
        scaling.append(item)
    lifecycle = [row for row in rows if row['phase']=='lifecycle']
    cycles = defaultdict(list)
    for row in lifecycle: cycles[(row['seed'],row['trial'])].append(row['correct'])
    controls = {}
    for mode in sorted({row['mode'] for row in rows if row['phase']=='control'}):
        selected = [row for row in rows if row['phase']=='control' and row['mode']==mode]
        controls[mode] = {'n':len(selected),'correct_current_answers':sum(row['correct'] for row in selected)}
    contention = []
    for level in sorted({row['concurrency'] for row in rows if row['phase']=='contention_request'}):
        selected = [row for row in rows if row['phase']=='contention_request' and row['concurrency']==level]
        batches = [row for row in rows if row['phase']=='contention_batch' and row['concurrency']==level]
        successful = [row for row in selected if row['status_code']==200]
        elapsed = sum(row['elapsed_ms'] for row in batches)
        contention.append({'concurrency':level,'requests':len(selected),'successful':len(successful),
            'http_statuses':dict(Counter(str(row['status_code']) for row in selected)),
            'successful_requests_per_second':len(successful)*1000/elapsed,
            'all_request_latency':latency([row['elapsed_ms'] for row in selected]),
            'successful_request_latency':latency([row['elapsed_ms'] for row in successful]),
            'batch_duration_ms':elapsed})
    unexpected = [row for row in rows if row.get('correct') is False and not
                  (row['phase']=='control' and row['mode']=='query_only_stale_cache')]
    unexpected.extend(row for row in rows if row['phase']=='oracle' and not row['witnesses_valid'] and row not in unexpected)
    unexpected.extend(row for row in rows if row['phase']=='api' and row.get('proof_status')=='FAILED' and row not in unexpected)
    overview = []
    sizes = sorted({row['assertion_count'] for row in rows if row['phase']=='api'})
    for size in sizes:
        direct = [row for row in rows if row['phase']=='solver' and row['assertion_count']==size]
        api = {mode:[row for row in rows if row['phase']=='api' and row['assertion_count']==size and row['mode']==mode] for mode in ('solver','certificate')}
        decisive_requests = [row for row in api['certificate'] if row['expected'] in ('PROVED','REFUTED')]
        overview.append({'assertion_count':size,'direct_solver':latency([r['elapsed_ms'] for r in direct]),
                         'api_solver':latency([r['elapsed_ms'] for r in api['solver']]),
                         'api_certificate':latency([r['elapsed_ms'] for r in api['certificate']]),
                         'decisive_requests':len(decisive_requests),
                         'verified_decisive':sum(r.get('proof_status')=='VERIFIED' for r in decisive_requests),
                         'certificate_statuses':dict(Counter(str(r.get('proof_status')) for r in decisive_requests))})
    return {'oracle':{'cases':len(oracle),'correct':correct,'accuracy':correct/len(oracle) if oracle else None,
            'wilson_95':wilson(correct,len(oracle)), 'expected_classes':dict(Counter(r['expected'] for r in oracle)),
            'actual_classes':dict(Counter(r['actual'] for r in oracle)), 'witness_failures':sum(not r['witnesses_valid'] for r in oracle)},
        'proofs':{'decisive_attempts':len(decisive),'statuses':dict(Counter(row['proof_status'] for row in decisive)),
                  'verified_certificate_bytes':{'n':sum('certificate_bytes' in row for row in decisive),
                      'p50':quantile([row['certificate_bytes'] for row in decisive if 'certificate_bytes' in row],.5),
                      'p95':quantile([row['certificate_bytes'] for row in decisive if 'certificate_bytes' in row],.95)},
                  'unknown':dict(Counter(row['proof_status'] for row in proofs if row['expected']=='UNKNOWN'))},
        'tampering':{'attempts':len(tamper),'accepted':sum(row['accepted'] for row in tamper),
                    'by_mutation':{name:{'attempts':sum(r['mutation']==name for r in tamper),
                        'accepted':sum(r['accepted'] for r in tamper if r['mutation']==name)} for name in sorted({r['mutation'] for r in tamper})}},
        'lifecycle':{'cycles':len(cycles),'passed_cycles':sum(all(values) for values in cycles.values()),'checks':len(lifecycle),
                     'failed_checks':sum(not r['correct'] for r in lifecycle)},
        'controls':controls,'scaling':scaling,'scaling_overview':overview,'contention':contention,
        'unexpected_failures':len(unexpected),'failure_examples':unexpected[:20],
        'raw_observations':len(rows),'source_revision':manifest['source_revision']}


def write_report(output: Path, summary: dict[str, Any], manifest: dict[str, Any]) -> None:
    o,p,t,l = (summary[key] for key in ('oracle','proofs','tampering','lifecycle'))
    interval = o['wilson_95']
    lines = ['# memopops benchmark results', '', f"Measured UTC: {manifest['measured_at_utc']}. Source commit: `{manifest['source_revision']}`.",
        '', '**Scope: synthetic, single-machine evaluation. The API uses an in-memory test store. FalkorDB/network performance and LLM quality were not measured.**',
        '', f"Environment: {manifest['hardware'].get('cpu')}; {manifest['hardware'].get('logical_cpus')} logical CPUs; Python {manifest['python']}; Z3 {manifest['packages']['z3-solver']}; {manifest['os']}.",
        '', f"Configuration: `{manifest['protocol']}`. Warmups are excluded. Each seed runs in a fresh process; workers run sequentially. Timings use nearest-rank percentiles. Pooled timing counts are repeated measurements, not new logical cases.",
        '', '## Logical classification', '', f"Independent raw-JSON truth-table agreement: **{o['correct']}/{o['cases']} ({100*o['accuracy']:.2f}%)**; witness failures: **{o['witness_failures']}**.",
        f"Expected class distribution: `{o['expected_classes']}`. Dataset cases are deduplicated across seeds. Descriptive Wilson 95% interval: {100*interval[0]:.3f}%–{100*interval[1]:.3f}%. This interval does not establish natural-language accuracy or a deployment error bound.",
        '', '## Certificates and mutation probes', '', f"Generated-corpus decisive attempts: {p['decisive_attempts']}; outcomes: `{p['statuses']}`. UNKNOWN witness checks: `{p['unknown']}`.",
        f"Tamper/context probes: {t['attempts']}; jointly accepted: {t['accepted']}. A mathematically valid certificate for a different context is correctly denied by the context check. Applicable evidence probes exclude certificates with no premises. These finite mutation probes do not establish resistance to every attack.",
        '', '## Scaling and latency', '', 'Each size below pools an equal mix of chain, fan-out and distractor-heavy constructions and PROVED/REFUTED/UNKNOWN questions. At 128/256 assertions, vocabulary/depth is capped and extra assertions are redundant rules: these are not implication chains of that depth.',
        '', '| Assertions | Direct solver p50 / p95 ms | API solver p50 / p95 ms | API certificate p50 / p95 ms | Decisive certificates verified |',
        '| --- | --- | --- | --- | --- |']
    for row in summary['scaling_overview']:
        metrics = [f"{row[key]['p50_ms']:.3f} / {row[key]['p95_ms']:.3f}" for key in ('direct_solver','api_solver','api_certificate')]
        lines.append(f"| {row['assertion_count']} | {' | '.join(metrics)} | {row['verified_decisive']}/{row['decisive_requests']} |")
    lines += ['', '**Certificate-mode latency includes refusals and budget limits. A fast request that did not generate a certificate is not a fast verified proof. Read latency together with coverage.** Complete topology/status/per-process data is in summary.json and the raw observations.',
        '', '## Corrections, history and concurrency guards', '', f"Lifecycle cycles: **{l['passed_cycles']}/{l['cycles']}**; named checks: {l['checks']}; failed checks: {l['failed_checks']}. These include quarantine, immutable historical proof checking, stale decision rejection, tenant/role isolation, idempotent query retry and a two-writer expected-head race. Store concurrency here is an in-memory test double, not evidence about FalkorDB's write transactions.",
        '', '| Controlled reader after correction | Correct current answers |', '| --- | --- |']
    for mode, value in summary['controls'].items(): lines.append(f"| {mode} | {value['correct_current_answers']}/{value['n']} |")
    lines += ['', 'The fresh solver is a same-reasoner recomputation control, not a competing memory product. The intentionally stale query-only cache demonstrates the failure mechanism it was designed to exhibit. Its failures are not a measured failure rate of RAG, Mem0, Zep or Letta.',
        '', '## In-process contention', '', '| Concurrent requests | Successes / requests | HTTP statuses | Successful requests/s | Successful p95 ms |', '| --- | --- | --- | --- | --- |']
    for row in summary['contention']:
        p95 = row['successful_request_latency']['p95_ms']
        lines.append(f"| {row['concurrency']} | {row['successful']}/{row['requests']} | {row['http_statuses']} | {row['successful_requests_per_second']:.1f} | {p95:.3f} |")
    lines += ['', 'This is a closed-loop local ASGI experiment: three batches of 32 solver-mode requests per level/process. Requests wait behind a client semaphore before timing starts. Throughput includes the full batch duration; 429s remain in counts and are not counted as successes. These are not network/FalkorDB QPS numbers.',
        '', '## Reproduction and artifacts', '', 'See ../../BENCHMARK_PROTOCOL.md for the predeclared protocol. Run the command stored in manifest.json after checking out its source revision. Use a fresh output path. All cases and credentials are synthetic; no user workspace was touched.',
        '', '- manifest.json: command, source/dependency/hardware metadata, dataset and observation hashes.', '- cases-*.jsonl: unique generated logic cases, oracle labels and seeds.', '- scaling-cases.json: explicit large-case constructions.', '- observations-*.jsonl and observations.csv: raw results including errors/refusals.', '- summary.json: descriptive aggregates, class counts, per-process medians and failure examples.',
        '', '## Claims and limitations', '', f"Unexpected failures observed: **{summary['unexpected_failures']}**. No measurements were discarded because they were slow or failed. Warmup failures are retained separately. Results are conditional on the sampled synthetic workloads, recorded hardware and application limits.",
        '', 'Supported: measured agreement with an independent finite truth-table oracle; observed certificate acceptance/rejection and coverage under fixed limits; observed revision behavior against a controlled test store; descriptive latency on this machine.',
        '', 'Not supported: elimination of hallucinations, factual truth of evidence, universal correctness, superiority to other memory systems, real database durability/transaction correctness, production throughput, or performance on natural-language memory benchmarks. Both configured database paths were unavailable during this run.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
