"""Untimed, separately labelled diagnosis of observed proof-budget refusals."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.benchmark import snapshot_for
from evaluation.benchmark_cases import scaling_case
from memopops.certificates import CertificateBudgetExceeded, generate_certificate
from memopops.solver import classify


def probe(case):
    snapshot, query, _, evidence = snapshot_for(case)
    answer = classify(snapshot.formulas, query)
    try:
        generate_certificate(snapshot, query, answer.result.value, answer.witnesses['knowledge'], evidence)
        return {'status': 'GENERATED', 'reason': ''}
    except CertificateBudgetExceeded as exc:
        return {'status': 'BUDGET_EXCEEDED', 'reason': str(exc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    root = args.directory
    cases = {case['id']: case for path in root.glob('cases-*.jsonl') for line in path.read_text().splitlines() for case in [json.loads(line)]}
    rows = [json.loads(line) for path in root.glob('observations-*.jsonl') for line in path.read_text().splitlines()]
    failures = [row for row in rows if row['phase'] == 'proof' and row['proof_status'] == 'BUDGET_EXCEEDED']
    generated = [{'case_id': row['case_id'], 'seed': row['seed'], **probe(cases[row['case_id']])} for row in failures]
    scaling = [{'assertion_count': size, 'family': family, 'outcome': 'PROVED', **probe(scaling_case(size, family, 'PROVED'))}
               for size in (4, 8, 16, 32, 64, 128, 256) for family in ('chain', 'fanout', 'distractors')]
    for filename, results in (('budget-diagnostics.json', generated), ('scaling-budget-diagnostics.json', scaling)):
        (root/filename).write_text(json.dumps({'scope': 'Untimed post-run diagnosis, never mixed into primary measurements or coverage.', 'results': results}, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'generated_refusals_diagnosed': len(generated), 'scaling_probes': len(scaling)}))


if __name__ == '__main__': main()
