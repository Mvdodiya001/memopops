"""Synthetic cases and a raw-JSON truth-table oracle independent of the product solver."""
from __future__ import annotations

import hashlib
from itertools import product
import json
from random import Random
from typing import Any

STATUSES = ('PROVED', 'REFUTED', 'UNKNOWN', 'INCONSISTENT_MEMORY')
SIZES = (4, 8, 16, 32, 64, 128, 256)
FAMILIES = ('chain', 'fanout', 'distractors')


def atom(name: str) -> dict[str, str]:
    return {'op': 'atom', 'id': name}


def negate(formula: dict[str, Any]) -> dict[str, Any]:
    return {'op': 'not', 'arg': formula}


def binary(op: str, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return {'op': op, 'args': [left, right]}


def evaluate(raw: dict[str, Any], assignment: dict[str, bool]) -> bool:
    """Do not share the product AST, Z3 translation, CNF compiler, or checker evaluator."""
    op = raw['op']
    if op == 'atom':
        return assignment[raw['id']]
    if op == 'not':
        return not evaluate(raw['arg'], assignment)
    left = evaluate(raw['args'][0], assignment)
    right = evaluate(raw['args'][1], assignment)
    if op == 'and':
        return left and right
    if op == 'or':
        return left or right
    if op == 'implies':
        return (not left) or right
    if op == 'iff':
        return left == right
    raise ValueError('Unknown oracle operator')


def oracle(case: dict[str, Any]) -> str:
    true_seen = false_seen = False
    for bits in product((False, True), repeat=len(case['atom_ids'])):
        assignment = dict(zip(case['atom_ids'], bits))
        if all(evaluate(premise, assignment) for premise in case['premises']):
            if evaluate(case['query'], assignment):
                true_seen = True
            else:
                false_seen = True
    if true_seen and false_seen:
        return 'UNKNOWN'
    if true_seen:
        return 'PROVED'
    if false_seen:
        return 'REFUTED'
    return 'INCONSISTENT_MEMORY'


def fingerprint(case: dict[str, Any]) -> str:
    payload = {key: case[key] for key in ('atom_ids', 'premises', 'query')}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def random_cases(seed: int, count: int, seen: set[str] | None = None) -> list[dict[str, Any]]:
    if count < 4 or count % 4:
        raise ValueError('Correctness case count must be a positive multiple of four')
    seen = seen if seen is not None else set()
    rng = Random(seed)
    buckets: dict[str, list[dict[str, Any]]] = {status: [] for status in STATUSES}
    quota = count // 4
    attempts = 0
    while any(len(bucket) < quota for bucket in buckets.values()):
        attempts += 1
        if attempts > count * 200:
            raise RuntimeError('Could not fill balanced generated corpus')
        ids = [f'p{i}' for i in range(rng.randint(2, 6))]

        def formula(depth: int) -> dict[str, Any]:
            if depth == 0 or rng.random() < .30:
                return atom(rng.choice(ids))
            if rng.random() < .23:
                return negate(formula(depth - 1))
            return binary(rng.choice(('and', 'or', 'implies', 'iff')), formula(depth - 1), formula(depth - 1))

        case = {'atom_ids': ids, 'premises': [formula(rng.randrange(4)) for _ in range(rng.randrange(6))], 'query': formula(rng.randrange(4))}
        digest = fingerprint(case)
        if digest in seen:
            continue
        expected = oracle(case)
        if len(buckets[expected]) >= quota:
            continue
        seen.add(digest)
        case.update(id=digest, family='generated', expected=expected, seed=seed)
        buckets[expected].append(case)
    cases = [case for bucket in buckets.values() for case in bucket]
    rng.shuffle(cases)
    return cases


def scaling_case(size: int, family: str, status: str) -> dict[str, Any]:
    if size < 2 or family not in FAMILIES or status not in STATUSES[:3]:
        raise ValueError('Invalid scaling construction')
    width = min(size, 64)
    ids = [f'p{i:03}' for i in range(width)]
    if family == 'chain':
        premises = [atom(ids[0])] + [binary('implies', atom(ids[i]), atom(ids[i + 1])) for i in range(width - 1)]
        target = atom(ids[-1])
    elif family == 'fanout':
        premises = [atom(ids[0])] + [binary('implies', atom(ids[0]), atom(ids[i])) for i in range(1, width)]
        target = atom(ids[-1])
    else:
        premises = [atom(name) for name in ids]
        target = atom(ids[0])
    # Explicit redundant rules keep the vocabulary <=65 at 128/256 assertions.
    # This is not a chain of depth 256 and must not be reported as one.
    while len(premises) < size:
        index = (len(premises) - width) % width
        premises.append(binary('implies', atom(ids[index]), atom(ids[(index + 2) % width])))
    query = target if status == 'PROVED' else negate(target) if status == 'REFUTED' else atom('unrelated')
    case = {'family': family, 'assertion_count': size, 'construction_width': width,
            'atom_ids': ids + ['unrelated'], 'premises': premises, 'query': query, 'expected': status}
    case['id'] = fingerprint(case)
    return case
