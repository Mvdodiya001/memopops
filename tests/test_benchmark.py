from collections import Counter

import pytest

from evaluation.benchmark_cases import atom, binary, negate, oracle, random_cases, scaling_case
from evaluation.benchmark_report import quantile, summarize, wilson


@pytest.mark.parametrize(('premises','query','expected'), [
    ([],atom('q'),'UNKNOWN'), ([atom('p'),binary('implies',atom('p'),atom('q'))],atom('q'),'PROVED'),
    ([negate(atom('p'))],atom('p'),'REFUTED'), ([atom('p'),negate(atom('p'))],atom('q'),'INCONSISTENT_MEMORY'),
    ([binary('iff',atom('p'),atom('q')),negate(atom('p'))],atom('q'),'REFUTED'),
])
def test_independent_benchmark_oracle(premises,query,expected):
    assert oracle({'atom_ids':['p','q'],'premises':premises,'query':query}) == expected


def test_generated_corpus_is_reproducible_balanced_and_deduplicated_across_seeds():
    seen = set()
    first = random_cases(123, 40, seen)
    second = random_cases(456, 40, seen)
    assert first == random_cases(123, 40)
    assert Counter(case['expected'] for case in first) == dict.fromkeys(('PROVED','REFUTED','UNKNOWN','INCONSISTENT_MEMORY'),10)
    assert not ({case['id'] for case in first} & {case['id'] for case in second})
    assert len(seen) == 80


@pytest.mark.parametrize('family', ['chain','fanout','distractors'])
@pytest.mark.parametrize('status', ['PROVED','REFUTED','UNKNOWN'])
def test_small_scaling_constructions_agree_with_oracle(family,status):
    case = scaling_case(4,family,status)
    assert oracle(case) == status
    large = scaling_case(256,family,status)
    assert len(large['premises']) == 256 and len(large['atom_ids']) <= 128


def test_summary_does_not_hide_budget_limits_or_count_expected_stale_control_as_product_failure():
    rows = [
        {'phase':'oracle','seed':1,'case_id':'one','expected':'PROVED','actual':'PROVED','correct':True,'witnesses_valid':True},
        {'phase':'api','seed':1,'family':'chain','assertion_count':4,'mode':'solver','expected':'PROVED','actual':'PROVED','correct':True,'status_code':200,'proof_status':'NOT_REQUESTED','elapsed_ms':1},
        {'phase':'api','seed':1,'family':'chain','assertion_count':4,'mode':'certificate','expected':'PROVED','actual':'PROVED','correct':True,'status_code':200,'proof_status':'BUDGET_EXCEEDED','elapsed_ms':3},
        {'phase':'solver','seed':1,'family':'chain','assertion_count':4,'mode':'solver','expected':'PROVED','actual':'PROVED','correct':True,'elapsed_ms':.5},
        {'phase':'control','seed':1,'trial':0,'mode':'query_only_stale_cache','correct':False},
        {'phase':'contention_request','seed':1,'concurrency':32,'status_code':200,'correct':True,'elapsed_ms':2},
        {'phase':'contention_request','seed':1,'concurrency':32,'status_code':429,'correct':True,'elapsed_ms':1},
        {'phase':'contention_batch','seed':1,'concurrency':32,'elapsed_ms':4},
    ]
    summary = summarize(rows, {'source_revision':'test'})
    assert summary['unexpected_failures'] == 0
    assert summary['scaling_overview'][0]['verified_decisive'] == 0
    assert summary['scaling_overview'][0]['decisive_requests'] == 1
    assert summary['contention'][0]['successful_requests_per_second'] == 250
    assert summary['contention'][0]['http_statuses'] == {'200':1,'429':1}
    assert summary['contention'][0]['successful_request_latency']['n'] == 1
    assert summary['contention'][0]['all_request_latency']['n'] == 2
    rows.append({'phase':'control','seed':1,'trial':1,'mode':'fresh_solver','correct':False})
    assert summarize(rows, {'source_revision':'test'})['unexpected_failures'] == 1


def test_statistics_handle_small_and_empty_samples():
    assert quantile([1,2,3,4],.95) == 4
    assert quantile([],.5) is None
    assert wilson(0,0) is None
    low, high = wilson(100,100)
    assert .96 < low < .97 and high == pytest.approx(1)
