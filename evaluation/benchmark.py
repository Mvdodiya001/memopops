"""Reproducible synthetic benchmark; does not alter product limits or user workspaces."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from contextlib import asynccontextmanager
import copy
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
from random import Random
import subprocess
import sys
from time import perf_counter_ns
from typing import Any

import httpx

from evaluation.benchmark_cases import FAMILIES, SIZES, STATUSES, atom, binary, evaluate, negate, oracle, random_cases, scaling_case
from evaluation.lab_store import LabSnapshotStore, StoredAssertion
from memopops.api import create_app
from memopops.certificates import CertificateBudgetExceeded, generate_certificate
from memopops.formula import formula_hash, parse_formula
from memopops.solver import classify
from memopops.store import AssertionRecord, Snapshot, calculate_knowledge_hash
from proofcheck import check_certificate, check_witness_pair

WORKSPACE = 'benchmark'
TOKENS = {f'benchmark-{role}': {'workspace_id': WORKSPACE, 'role': role} for role in ('reader', 'writer', 'operator')}


def now_ms() -> float:
    return perf_counter_ns() / 1_000_000


def snapshot_for(case: dict[str, Any]) -> tuple[Snapshot, Any, dict[str, Any], dict[str, list[str]]]:
    ids = frozenset(case['atom_ids'])
    records = tuple(AssertionRecord(f'as_{index:04}', parsed, formula_hash(parsed))
                    for index, raw in enumerate(case['premises'])
                    for parsed in [parse_formula(raw, ids)])
    snapshot = Snapshot(WORKSPACE, 'rev_benchmark', calculate_knowledge_hash(records), ids, records)
    query = parse_formula(case['query'], ids)
    evidence = {record.id: [f'ev_{record.id}'] for record in records}
    context = {'workspace_id': WORKSPACE, 'revision_id': snapshot.revision_id,
               'knowledge_hash': snapshot.knowledge_hash, 'query_hash': formula_hash(query),
               'semantics_version': 'boolean-v1',
               'assertions': [{'id': record.id, 'formula_hash': record.formula_hash, 'evidence_ids': evidence[record.id]} for record in records]}
    return snapshot, query, context, evidence


def store_for(case: dict[str, Any]) -> LabSnapshotStore:
    """Trusted synthetic fixture creation is outside API request timing."""
    snapshot, _, _, _ = snapshot_for(case)
    store = LabSnapshotStore(workspace_id=WORKSPACE, empty=True)
    store.initialize_workspace(WORKSPACE, [{'id': name, 'label': name, 'meaning': 'Synthetic '+name, 'scope': 'benchmark'} for name in case['atom_ids']], 'benchmark_fixture')
    head = store.head
    excerpt = 'Synthetic benchmark premise; not real-world evidence.'
    digest = hashlib.sha256(excerpt.encode()).hexdigest()
    store._members[head] = tuple(StoredAssertion(record, 'benchmark_fixture', 'trusted_fixture',
        '2026-10-25T00:00:00Z', ({'id': f'ev_{record.id}', 'uri': 'fixture://benchmark', 'excerpt': excerpt,
        'observed_at': '2026-10-25T00:00:00Z', 'content_digest': digest},)) for record in snapshot.assertions)
    store._meta[head]['knowledge_hash'] = snapshot.knowledge_hash
    return store


@asynccontextmanager
async def api_client(store: LabSnapshotStore):
    app = create_app(store)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://benchmark') as client:
            yield client
    finally:
        app.state.solver_executor.shutdown()


async def request(client: httpx.AsyncClient, method: str, suffix: str, *, body=None, role='reader', workspace=WORKSPACE):
    return await client.request(method, f'/api/v1/workspaces/{workspace}{suffix}', json=body,
                                headers={'Authorization': 'Bearer benchmark-'+role})


def correctness(cases: list[dict[str, Any]], rows: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    evaluations = {}
    for index, case in enumerate(cases):
        snapshot, query, _, _ = snapshot_for(case)
        expected = oracle(case)  # Recompute from raw data, independently of serialized expected labels.
        started = now_ms()
        try:
            result = classify(snapshot.formulas, query)
            elapsed = now_ms() - started
            valid_witnesses = True
            required_models = {'PROVED': ('knowledge', 'query_true'), 'REFUTED': ('knowledge', 'query_false'),
                               'UNKNOWN': ('knowledge', 'query_true', 'query_false'), 'INCONSISTENT_MEMORY': ()}
            if result.result.value in required_models:
                valid_witnesses &= all(result.witnesses[name] is not None for name in required_models[result.result.value])
                if result.result.value == 'INCONSISTENT_MEMORY':
                    valid_witnesses &= all(witness is None for witness in result.witnesses.values())
            for name, required in (('knowledge', None), ('query_true', True), ('query_false', False)):
                witness = result.witnesses[name]
                if witness is not None:
                    valid_witnesses &= all(evaluate(raw, witness) for raw in case['premises'])
                    if required is not None:
                        valid_witnesses &= evaluate(case['query'], witness) is required
            rows.append({'phase': 'oracle', 'seed': seed, 'case_id': case['id'], 'expected': expected,
                         'actual': result.result.value, 'correct': result.result.value == expected,
                         'witnesses_valid': valid_witnesses, 'elapsed_ms': elapsed})
            evaluations[case['id']] = result
        except Exception as exc:
            rows.append({'phase': 'oracle', 'seed': seed, 'case_id': case['id'], 'expected': expected,
                         'actual': 'EXCEPTION', 'correct': False, 'witnesses_valid': False,
                         'elapsed_ms': now_ms() - started, 'error_type': type(exc).__name__})
        if (index + 1) % 250 == 0:
            print(f'seed={seed} oracle {index+1}/{len(cases)}', flush=True)
    return evaluations


def proof_checks(cases, evaluations, rows, seed, per_outcome=40):
    quotas = Counter()
    mutated_certificates = 0
    for case in cases:
        outcome = case['expected']
        if outcome not in STATUSES[:3] or quotas[outcome] >= per_outcome:
            continue
        quotas[outcome] += 1
        snapshot, query, context, evidence = snapshot_for(case)
        evaluation = evaluations.get(case['id'])
        row = {'phase': 'proof', 'seed': seed, 'case_id': case['id'], 'expected': outcome}
        if evaluation is None or evaluation.result.value != outcome:
            rows.append({**row, 'proof_status': 'NO_CORRECT_RESULT', 'correct': False})
            continue
        started = now_ms()
        try:
            if outcome == 'UNKNOWN':
                assertions = [{'id': record.id, 'formula': raw, 'evidence_ids': evidence[record.id]}
                              for record, raw in zip(snapshot.assertions, case['premises'])]
                report = check_witness_pair(assertions, case['query'], evaluation.witnesses['query_true'], evaluation.witnesses['query_false'])
                rows.append({**row, 'proof_status': 'WITNESSES_VALID' if report.logical_valid else 'FAILED',
                             'correct': report.logical_valid, 'check_ms': now_ms()-started})
                continue
            bundle = generate_certificate(snapshot, query, outcome, evaluation.witnesses['knowledge'], evidence)
            generated = now_ms()
            report = check_certificate(bundle, context)
            valid = report.logical_valid and report.context_binding == 'MATCHED'
            rows.append({**row, 'proof_status': 'VERIFIED' if valid else 'FAILED', 'correct': valid,
                         'generation_ms': generated-started, 'check_ms': now_ms()-generated,
                         'certificate_bytes': len(json.dumps(bundle, separators=(',', ':')).encode()),
                         'clause_count': len(bundle['clauses']), 'support_count': len(bundle['support_assertion_ids'])})
            if valid and mutated_certificates < 20:
                mutated_certificates += 1
                mutations = ['flip_result', 'query_hash', 'missing_witness', 'missing_clause', 'false_empty_id',
                             'invented_support', 'workspace_binding', 'revision_binding', 'trusted_context_binding']
                if bundle['assertions']:
                    mutations.append('evidence_binding')
                for mutation in mutations:
                    candidate, expected_context = copy.deepcopy(bundle), copy.deepcopy(context)
                    if mutation == 'flip_result': candidate['result'] = 'REFUTED' if outcome == 'PROVED' else 'PROVED'
                    elif mutation == 'query_hash': candidate['query_hash'] = '0'*64
                    elif mutation == 'missing_witness': candidate['knowledge_witness'] = {}
                    elif mutation == 'missing_clause': candidate['clauses'].pop(0)
                    elif mutation == 'false_empty_id': candidate['empty_clause_id'] = -1
                    elif mutation == 'invented_support': candidate['support_assertion_ids'] = ['as_nonexistent']
                    elif mutation == 'workspace_binding': candidate['workspace_id'] = 'another_workspace'
                    elif mutation == 'revision_binding': candidate['revision_id'] = 'another_revision'
                    elif mutation == 'trusted_context_binding': expected_context['knowledge_hash'] = '0'*64
                    elif mutation == 'evidence_binding': candidate['assertions'][0]['evidence_ids'] = ['ev_replaced']
                    try:
                        checked = check_certificate(candidate, expected_context)
                        accepted = checked.logical_valid and checked.context_binding == 'MATCHED'
                        rows.append({'phase': 'tamper', 'seed': seed, 'case_id': case['id'], 'mutation': mutation,
                                     'correct': not accepted, 'logical_valid': checked.logical_valid,
                                     'context_binding': checked.context_binding, 'accepted': accepted})
                    except Exception as exc:
                        rows.append({'phase': 'tamper', 'seed': seed, 'case_id': case['id'], 'mutation': mutation,
                                     'correct': False, 'accepted': False, 'error_type': type(exc).__name__})
        except CertificateBudgetExceeded:
            rows.append({**row, 'proof_status': 'BUDGET_EXCEEDED', 'correct': True, 'generation_ms': now_ms()-started})
        except Exception as exc:
            rows.append({**row, 'proof_status': 'FAILED', 'correct': False, 'error_type': type(exc).__name__})


def solver_scaling(rows, seed, samples, warmup):
    rng = Random(seed + 1)
    cells = [(size, family) for size in SIZES for family in FAMILIES]
    rng.shuffle(cells)
    for size, family in cells:
        cases = [scaling_case(size, family, status) for status in STATUSES[:3]]
        parsed = [snapshot_for(case)[:2] for case in cases]
        for index, case in enumerate(cases):
            snapshot, query = parsed[index]
            for _ in range(warmup):
                result = classify(snapshot.formulas, query)
                if result.result.value != case['expected']:
                    rows.append({'phase': 'warmup_error', 'seed': seed, 'correct': False, 'family': family, 'assertion_count': size})
        schedule = [index for index in range(3) for _ in range(samples)]
        rng.shuffle(schedule)
        for index in schedule:
            snapshot, query = parsed[index]
            started = now_ms()
            result = classify(snapshot.formulas, query)
            rows.append({'phase': 'solver', 'seed': seed, 'case_id': cases[index]['id'], 'family': family,
                         'assertion_count': size, 'expected': cases[index]['expected'], 'actual': result.result.value,
                         'correct': result.result.value == cases[index]['expected'], 'elapsed_ms': now_ms()-started})


async def api_scaling(rows, seed, samples, warmup):
    rng = Random(seed + 2)
    cells = [(size, family) for size in SIZES for family in FAMILIES]
    rng.shuffle(cells)
    for size, family in cells:
        cases = {status: scaling_case(size, family, status) for status in STATUSES[:3]}
        store = store_for(cases['PROVED'])
        async with api_client(store) as client:
            counter = 0
            async def ask(mode, outcome, measured):
                nonlocal counter
                counter += 1
                body = {'revision_id': store.head, 'query': cases[outcome]['query'], 'proof_mode': mode, 'idempotency_key': f'fresh-{counter}'}
                started = now_ms()
                response = await request(client, 'POST', '/queries', body=body)
                payload = response.json()
                elapsed = now_ms()-started
                correct = response.status_code == 200 and payload.get('result') == outcome
                if correct and mode == 'certificate':
                    correct = (payload.get('witnesses_verified') is True and payload.get('proof_status') == 'NOT_REQUESTED') if outcome == 'UNKNOWN' else payload.get('proof_status') in ('VERIFIED','BUDGET_EXCEEDED')
                if measured or not correct:
                    rows.append({'phase': 'api' if measured else 'warmup_error', 'seed': seed, 'family': family,
                        'assertion_count': size, 'mode': mode, 'expected': outcome, 'actual': payload.get('result'),
                        'correct': correct, 'status_code': response.status_code, 'proof_status': payload.get('proof_status'),
                        'witnesses_verified': payload.get('witnesses_verified'), 'elapsed_ms': elapsed,
                        'response_bytes': len(response.content), 'server_timings_ms': payload.get('timings_ms')})
            pairs = [(mode, outcome) for mode in ('solver', 'certificate') for outcome in STATUSES[:3]]
            rng.shuffle(pairs)
            for mode, outcome in pairs:
                for _ in range(warmup): await ask(mode, outcome, False)
            schedule = [pair for pair in pairs for _ in range(samples)]
            rng.shuffle(schedule)
            for mode, outcome in schedule: await ask(mode, outcome, True)
        print(f'seed={seed} api {family} assertions={size}', flush=True)


async def lifecycle(rows, seed, trials):
    for trial in range(trials):
        store = LabSnapshotStore(workspace_id=WORKSPACE, empty=True)
        async with api_client(store) as client:
            def record(name, actual, expected=True):
                rows.append({'phase': 'lifecycle', 'seed': seed, 'trial': trial, 'check': name,
                             'correct': actual == expected, 'actual': actual, 'expected': expected})
            try:
                definitions = [{'id': name, 'label': name, 'meaning': 'Synthetic '+name, 'scope': 'benchmark lifecycle'} for name in ('p', 'q', 'r')]
                initialized = await request(client, 'POST', '/initialize', body={'atoms': definitions}, role='operator')
                record('initialize', initialized.status_code, 201)
                p, q, r = atom('p'), atom('q'), atom('r')
                evidence = [{'uri': 'fixture://benchmark', 'excerpt': 'Synthetic lifecycle evidence', 'observed_at': '2026-10-25T00:00:00Z'}]
                def assertion(formula, ref): return {'client_ref': ref, 'formula': formula, 'evidence': evidence}
                async def change(mutations, key, head=None, role='operator'):
                    return await request(client, 'POST', '/revisions', role=role, body={'expected_revision': head or store.head,
                        'idempotency_key': key, 'reason': 'Synthetic lifecycle change', 'acceptance': 'trusted_fixture', 'mutations': mutations})
                accepted = await change([{'op': 'add', 'assertion': assertion(p, 'fact')}, {'op': 'add', 'assertion': assertion(binary('iff', p, q), 'rule')}], 'initial')
                record('initial_commit', accepted.status_code, 201)
                old_head = store.head
                raw = {'revision_id': old_head, 'idempotency_key': 'before', 'query': q, 'proof_mode': 'certificate'}
                first = (await request(client, 'POST', '/queries', body=raw)).json()
                record('initial_proved', first.get('result'), 'PROVED')
                record('initial_certificate', first.get('proof_status'), 'VERIFIED')
                duplicate = (await request(client, 'POST', '/queries', body=raw)).json()
                record('query_retry_identity', duplicate.get('query_id'), first['query_id'])
                bad = await change([{'op': 'add', 'assertion': assertion(negate(p), 'conflict')}], 'conflict')
                record('contradiction_quarantined', bad.json().get('status'), 'QUARANTINED')
                record('quarantine_keeps_head', store.head, old_head)
                corrected = await change([{'op': 'replace', 'target_assertion_id': accepted.json()['client_refs']['fact'], 'assertion': assertion(negate(p), 'correction')}], 'correction')
                record('correction_committed', corrected.status_code, 201)
                second = (await request(client, 'POST', '/queries', body={**raw, 'revision_id': store.head, 'idempotency_key': 'after'})).json()
                record('fresh_api_result', second.get('result'), 'REFUTED')
                record('fresh_api_certificate', second.get('proof_status'), 'VERIFIED')
                snapshot = store.load_snapshot(WORKSPACE, store.head)
                fresh = classify(snapshot.formulas, parse_formula(q, snapshot.atom_ids)).result.value
                rows.append({'phase': 'control', 'seed': seed, 'trial': trial, 'mode': 'fresh_solver', 'actual': fresh, 'expected': 'REFUTED', 'correct': fresh == 'REFUTED'})
                rows.append({'phase': 'control', 'seed': seed, 'trial': trial, 'mode': 'query_only_stale_cache', 'actual': first['result'], 'expected': 'REFUTED', 'correct': first['result'] == 'REFUTED'})
                decision = await request(client, 'POST', '/decisions', body={'expected_revision': old_head, 'query_id': first['query_id'],
                    'idempotency_key': 'late-decision', 'outcome': 'PROCEED', 'rationale': 'Synthetic stale reader decision'})
                record('stale_decision_rejected', decision.status_code, 409)
                old = await request(client, 'GET', '/queries/'+first['query_id']+'/certificate')
                record('historical_certificate_readable', old.status_code, 200)
                original_snapshot = store.load_snapshot(WORKSPACE, old_head)
                original_query = parse_formula(q, original_snapshot.atom_ids)
                memory = store.load_memory(WORKSPACE, old_head)
                context = {'workspace_id': WORKSPACE, 'revision_id': old_head, 'semantics_version': 'boolean-v1',
                    'knowledge_hash': original_snapshot.knowledge_hash, 'query_hash': formula_hash(original_query),
                    'assertions': [{'id': item['id'], 'formula_hash': item['formula_hash'], 'evidence_ids': sorted(e['id'] for e in item['evidence'])} for item in memory['assertions']]}
                proof = check_certificate(old.json(), context)
                record('historical_proof_still_valid', proof.logical_valid and proof.context_binding == 'MATCHED')
                foreign = await request(client, 'GET', '', workspace='another_tenant')
                record('tenant_boundary', foreign.status_code, 404)
                denied = await change([{'op': 'add', 'assertion': assertion(r, 'denied')}], 'writer-denied', role='writer')
                record('writer_activation_denied', denied.status_code, 403)
                race_head = store.head
                raced = await asyncio.gather(change([{'op': 'add', 'assertion': assertion(r, 'positive')}], 'race-positive', race_head),
                                             change([{'op': 'add', 'assertion': assertion(negate(r), 'negative')}], 'race-negative', race_head))
                record('two_writer_race', sorted(response.status_code for response in raced), [201, 409])
                record('race_head_advanced_once', len(store.list_revisions(WORKSPACE)), 4)
            except Exception as exc:
                rows.append({'phase': 'lifecycle', 'seed': seed, 'trial': trial, 'check': 'cycle_exception', 'correct': False, 'error_type': type(exc).__name__})
        if (trial + 1) % 10 == 0:
            print(f'seed={seed} lifecycle {trial+1}/{trials}', flush=True)


async def contention(rows, seed, batches=3):
    store = store_for(scaling_case(64, 'chain', 'PROVED'))
    async with api_client(store) as client:
        counter = 0
        for level in (1, 2, 8, 32):
            for batch in range(batches):
                gate = asyncio.Semaphore(level)
                async def ask():
                    nonlocal counter
                    async with gate:
                        counter += 1
                        body = {'revision_id': store.head, 'idempotency_key': f'contention-{counter}',
                                'query': atom('p063'), 'proof_mode': 'solver'}
                        started = now_ms()
                        response = await request(client, 'POST', '/queries', body=body)
                        elapsed = now_ms()-started
                        result = response.json().get('result')
                        rows.append({'phase': 'contention_request', 'seed': seed, 'concurrency': level, 'batch': batch,
                                     'status_code': response.status_code, 'actual': result, 'elapsed_ms': elapsed,
                                     'correct': (response.status_code == 200 and result == 'PROVED') or response.status_code == 429})
                        return response.status_code
                started = now_ms()
                statuses = await asyncio.gather(*(ask() for _ in range(32)))
                elapsed = now_ms()-started
                rows.append({'phase': 'contention_batch', 'seed': seed, 'concurrency': level, 'batch': batch,
                    'requests': len(statuses), 'successful': statuses.count(200), 'elapsed_ms': elapsed,
                    'successful_requests_per_second': statuses.count(200)*1000/elapsed, 'statuses': dict(Counter(statuses))})


def metadata() -> dict[str, Any]:
    def git(*args):
        return subprocess.check_output(['git', *args], text=True).strip()
    paths = sorted(set(Path('src/memopops').glob('*.py')) | set(Path('packages/proofcheck/src/proofcheck').glob('*.py')) |
                   set(Path('evaluation').glob('benchmark*.py')) | {Path('evaluation/lab_store.py'), Path('uv.lock')})
    files = {path.as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    hardware = {'cpu': platform.processor(), 'logical_cpus': os.cpu_count()}
    if platform.system() == 'Windows':
        command = "[pscustomobject]@{cpu=(Get-CimInstance Win32_Processor).Name;ram_bytes=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory}|ConvertTo-Json -Compress"
        try:
            hardware.update(json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',command],text=True,timeout=15)))
        except (OSError, ValueError, subprocess.SubprocessError): pass
    return {'measured_at_utc': datetime.now(timezone.utc).isoformat(), 'source_revision': git('rev-parse','HEAD'),
            'git_dirty': bool(git('status','--porcelain')), 'python': platform.python_version(), 'os': platform.platform(),
            'hardware': hardware, 'packages': {name: importlib.metadata.version(name) for name in ('z3-solver','fastapi','pydantic','httpx','falkordb')},
            'source_sha256': files, 'database_scope': 'unavailable: configured cloud DNS failure; local connection refused',
            'api_store': 'synthetic LabSnapshotStore; no network or FalkorDB costs'}


def worker(args):
    os.environ['MEMOPOPS_AUTH_TOKENS'] = json.dumps(TOKENS)
    cases = [json.loads(line) for line in args.cases_file.read_text(encoding='utf-8').splitlines()]
    rows = []
    started = now_ms()
    try:
        evaluations = correctness(cases, rows, args.seed)
        print(f'seed={args.seed} proof checks', flush=True)
        proof_checks(cases, evaluations, rows, args.seed)
        print(f'seed={args.seed} solver scaling', flush=True)
        solver_scaling(rows, args.seed, args.solver_samples, args.warmup)
        asyncio.run(api_scaling(rows, args.seed, args.api_samples, args.warmup))
        asyncio.run(lifecycle(rows, args.seed, args.lifecycle_trials))
        asyncio.run(contention(rows, args.seed))
    finally:
        args.output.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows), encoding='utf-8')
    print(f'seed={args.seed} finished rows={len(rows)} elapsed_s={(now_ms()-started)/1000:.1f}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seeds', type=int, nargs='+', default=[20261025,20261026,20261027])
    parser.add_argument('--cases-per-seed', type=int, default=1000)
    parser.add_argument('--solver-samples', type=int, default=30)
    parser.add_argument('--api-samples', type=int, default=10)
    parser.add_argument('--warmup', type=int, default=5)
    parser.add_argument('--lifecycle-trials', type=int, default=30)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--seed', type=int, help=argparse.SUPPRESS)
    parser.add_argument('--cases-file', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if min(args.cases_per_seed,args.solver_samples,args.api_samples,args.lifecycle_trials) < 1 or args.warmup < 0 or args.cases_per_seed % 4:
        parser.error('Positive counts required; correctness cases must be divisible by four; warmup >=0')
    if len(set(args.seeds)) != len(args.seeds): parser.error('Seeds must be distinct')
    if args.worker:
        worker(args)
        return
    if args.output.exists(): parser.error('Output directory already exists; choose a fresh path to preserve earlier results')
    args.output.mkdir(parents=True)
    manifest = metadata()
    manifest['protocol'] = {key: value for key,value in vars(args).items() if key not in ('worker','seed','cases_file','output')}
    manifest['command'] = ['python','-m','evaluation.benchmark',*sys.argv[1:]]
    manifest['dataset_sha256'] = {}
    seen: set[str] = set()
    all_rows = []
    for seed in args.seeds:
        cases = random_cases(seed, args.cases_per_seed, seen)
        case_path = args.output/f'cases-{seed}.jsonl'
        case_path.write_text(''.join(json.dumps(case,sort_keys=True)+'\n' for case in cases),encoding='utf-8')
        manifest['dataset_sha256'][case_path.name] = hashlib.sha256(case_path.read_bytes()).hexdigest()
        row_path = args.output/f'observations-{seed}.jsonl'
        command = [sys.executable,'-m','evaluation.benchmark','--worker','--seed',str(seed),'--cases-file',str(case_path),
                   '--output',str(row_path),'--solver-samples',str(args.solver_samples),'--api-samples',str(args.api_samples),
                   '--warmup',str(args.warmup),'--lifecycle-trials',str(args.lifecycle_trials)]
        print(f'Starting fresh worker seed={seed} cases={len(cases)}',flush=True)
        result = subprocess.run(command)
        if result.returncode or not row_path.exists():
            manifest['worker_failure'] = {'seed':seed,'exit_code':result.returncode}
            (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
            raise SystemExit('Worker failed; partial artifacts retained')
        all_rows.extend(json.loads(line) for line in row_path.read_text(encoding='utf-8').splitlines())
    scale = [scaling_case(size,family,status) for size in SIZES for family in FAMILIES for status in STATUSES[:3]]
    (args.output/'scaling-cases.json').write_text(json.dumps(scale,indent=2)+'\n',encoding='utf-8')
    manifest['unique_correctness_cases'] = len(seen)
    manifest['result_sha256'] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in args.output.glob('observations-*.jsonl')}
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    fields = sorted({key for row in all_rows for key in row})
    with (args.output/'observations.csv').open('w',newline='',encoding='utf-8') as stream:
        writer = csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        writer.writerows({key: json.dumps(value,sort_keys=True) if isinstance(value,(dict,list)) else value for key,value in row.items()} for row in all_rows)
    from evaluation.benchmark_report import summarize, write_report
    summary = summarize(all_rows, manifest)
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    write_report(args.output, summary, manifest)
    print(json.dumps({'output':str(args.output),'oracle':summary['oracle'],'unexpected_failures':summary['unexpected_failures']}),flush=True)
    if summary['unexpected_failures']: raise SystemExit(1)


if __name__ == '__main__': main()
