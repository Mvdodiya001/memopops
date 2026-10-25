"""Generate blog figures from preserved raw benchmark data, without rerunning timings.

Run using a Python environment with matplotlib; it is not a service dependency.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    root = args.directory
    manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    for name, digest in {**manifest['dataset_sha256'], **manifest['result_sha256']}.items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest() != digest:
            raise SystemExit('Artifact checksum mismatch: '+name)
    summary = json.loads((root/'summary.json').read_text(encoding='utf-8'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import ScalarFormatter

    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':12,
                         'axes.labelcolor':'#303945','text.color':'#202b38','svg.hashsalt':'memopops-benchmark-v1'})
    fig, (timing, coverage) = plt.subplots(2,1,figsize=(11,8.3),gridspec_kw={'height_ratios':[1.15,1]})
    overview = summary['scaling_overview']
    sizes = [row['assertion_count'] for row in overview]
    for key, label, color in [('direct_solver','Classifier only','#335f84'),
                               ('api_solver','API · solver mode','#6b8b78'),
                               ('api_certificate','API · certificate mode (including refusals)','#af774b')]:
        medians = [row[key]['p50_ms'] for row in overview]
        p95 = [row[key]['p95_ms'] for row in overview]
        timing.plot(sizes, medians, marker='o',color=color,label=label,linewidth=1.8,markersize=4)
        timing.fill_between(sizes,medians,p95,color=color,alpha=.10)
    timing.set_xscale('log',base=2)
    timing.set_xticks(sizes)
    timing.xaxis.set_major_formatter(ScalarFormatter())
    timing.set_ylabel('Wall-clock latency (ms)')
    timing.set_xlabel('Accepted assertions')
    timing.set_title('Latency: median lines, median–p95 shading (not confidence intervals)',loc='left',pad=12)
    timing.legend(frameon=False,fontsize=9,loc='upper left')
    colors = ['#335f84','#6b8b78','#af774b']
    for index, family in enumerate(('chain','fanout','distractors')):
        cells = {row['assertion_count']:row for row in summary['scaling'] if row['phase']=='api' and row['mode']=='certificate' and row['family']==family}
        percentages = [100*cells[size]['verified_decisive']/cells[size]['decisive_requests'] for size in sizes]
        positions = [x+(index-1)*.24 for x in range(len(sizes))]
        coverage.bar(positions,percentages,width=.22,color=colors[index],label={'chain':'Chain','fanout':'Fan-out','distractors':'Distractor-heavy'}[family])
    coverage.set_xticks(range(len(sizes)),[str(size) for size in sizes])
    coverage.set_ylim(0,110)
    coverage.set_yticks([0,25,50,75,100])
    coverage.set_ylabel('Decisive requests with VERIFIED certificate (%)')
    coverage.set_xlabel('Accepted assertions')
    coverage.set_title('Certificate coverage under unchanged proof budgets',loc='left',pad=12)
    coverage.legend(frameon=False,fontsize=9,ncol=3,loc='upper right')
    for axis in (timing,coverage):
        axis.spines['top'].set_visible(False)
        axis.spines['right'].set_visible(False)
        axis.grid(axis='y',alpha=.15)
        axis.set_axisbelow(True)
    fig.suptitle('memopops: measured latency and proof coverage',fontsize=17,fontweight='semibold',x=.085,ha='left',y=.98)
    fig.text(.085,.025,'Synthetic workloads · 3 fresh processes · in-memory API store · no FalkorDB/network timing\n'
             'Large inputs use capped vocabulary with redundant rules. Fast budget refusals are not verified proofs.\n'
             'Measured source: '+summary['source_revision'][:12],fontsize=8.5,color='#56616e')
    fig.subplots_adjust(left=.09,right=.97,top=.91,bottom=.145,hspace=.45)
    fig.savefig(root/'latency-and-coverage.png',dpi=200,facecolor='white')
    fig.savefig(root/'latency-and-coverage.svg',facecolor='white',metadata={'Date':None})
    plt.close(fig)
    print(json.dumps({'figure':str(root/'latency-and-coverage.png'),'checksums_verified':True}))


if __name__ == '__main__': main()
