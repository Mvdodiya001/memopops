"""Render original blog figures; benchmark numbers come from the frozen summary.

Run with an existing Python + matplotlib environment. No product dependency changes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch

HERE = Path(__file__).resolve().parent
SUMMARY = HERE.parents[1] / "evaluation/benchmark-2026-10-25/summary.json"
OUT = HERE / "figures"
INK = "#203D4D"
TEAL = "#25837B"
RUST = "#B36F48"
GRAY = "#5D6F77"
LINE = "#D8E1E0"
PAPER = "#FCFBF7"
MINT = "#EAF3EE"
SAND = "#F8EEE4"
BLUE = "#EEF2F5"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "text.color": INK,
    "svg.fonttype": "none", "savefig.facecolor": PAPER,
})


def canvas(height, kicker, title, subtitle):
    fig = plt.figure(figsize=(14, height), facecolor=PAPER)
    ax = fig.add_axes([0, 0, 1, 1], xlim=(0, 14), ylim=(0, height))
    ax.axis("off")
    text(ax, .55, height - .42, kicker.upper(), 10, TEAL, weight="bold")
    text(ax, .55, height - .97, title, 25, family="DejaVu Serif")
    text(ax, .55, height - 1.43, subtitle, 11, GRAY)
    return fig, ax


def text(ax, x, y, value, size=12, color=INK, **kwargs):
    return ax.text(x, y, value, fontsize=size, color=color, va="center", **kwargs)


def box(ax, x, y, w, h, fill="white", edge=LINE, radius=.14):
    patch = FancyBboxPatch((x, y), w, h,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        linewidth=1.05, edgecolor=edge, facecolor=fill)
    ax.add_patch(patch)
    return patch


def arrow(ax, start, end, color=TEAL, curve=0, dashed=False):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>",
        mutation_scale=12, linewidth=1.5, color=color,
        linestyle="--" if dashed else "-",
        connectionstyle=f"arc3,rad={curve}"))


def pill(ax, x, y, label, color=TEAL, fill=MINT, width=1.45):
    box(ax, x, y, width, .35, fill, edge=fill, radius=.16)
    text(ax, x + width/2, y + .175, label, 8.5, color, ha="center", weight="bold")


def footer(ax, note):
    ax.plot([.55, 13.45], [.45, .45], color=LINE, linewidth=.8)
    text(ax, .55, .23, note, 8.5, GRAY)
    text(ax, 13.45, .23, "memopops", 9, TEAL, ha="right", weight="bold")


def save(fig, name):
    for ext in ("png", "svg"):
        path = OUT / f"{name}.{ext}"
        fig.savefig(path, dpi=180, metadata={"Creator": "memopops blog figures"})
        if ext == "svg":
            # Clean generated path whitespace without touching measured artifacts.
            path.write_text("\n".join(line.rstrip() for line in
                path.read_text(encoding="utf-8").splitlines()) + "\n", encoding="utf-8", newline="\n")
    plt.close(fig)


def hero():
    fig, ax = canvas(6.7, "The idea", "A memory should remember its reasons",
        "An answer is more useful when its premises, evidence and revision travel with it.")
    # Reasons on the left, a conclusion in the centre, and an inspectable record.
    box(ax, .6, 3.47, 3.25, 1.08, MINT)
    text(ax, .85, 4.19, "ACCEPTED FACTS", 9, TEAL, weight="bold")
    text(ax, .85, 3.82, "API v2 active · tests pass", 12)
    box(ax, .6, 1.98, 3.25, 1.08, BLUE)
    text(ax, .85, 2.7, "ACCEPTED POLICY", 9, TEAL, weight="bold")
    text(ax, .85, 2.33, "Both hold → release ready", 11.5)
    arrow(ax, (3.85, 4.01), (5.05, 3.35))
    arrow(ax, (3.85, 2.52), (5.05, 3.03))
    ax.add_patch(Circle((5.6, 3.2), .49, facecolor=MINT, edgecolor=TEAL, linewidth=1.6))
    text(ax, 5.6, 3.2, "∴", 30, TEAL, ha="center")
    text(ax, 5.6, 2.35, "release_ready", 12, ha="center", weight="bold")
    text(ax, 5.6, 1.95, "follows at revision 12", 10, GRAY, ha="center")
    arrow(ax, (6.12, 3.2), (7.42, 3.2))
    box(ax, 7.45, 1.42, 5.85, 3.57)
    text(ax, 7.76, 4.57, "A REVISION-BOUND ANSWER", 10, TEAL, weight="bold")
    pill(ax, 11.49, 4.38, "VERIFIED", width=1.47)
    rows = [("Question", "Is this release ready?"),
            ("Premises", "Facts + explicit release policy"),
            ("Evidence", "Attached source records"),
            ("Context", "This workspace · revision 12"),
            ("Certificate", "Checked by a separate program")]
    for i, (label, value) in enumerate(rows):
        y = 3.96 - i * .48
        text(ax, 7.78, y, label, 10, GRAY)
        text(ax, 9.17, y, value, 10.5)
    footer(ax, "Illustrative policy. A checked consequence is conditional on the accepted premises.")
    save(fig, "01-memory-with-reasons")


def architecture():
    fig, ax = canvas(5.6, "The architecture", "From a sourced claim to a checked answer",
        "The graph keeps the relationships. The solver reasons over the complete accepted snapshot.")
    labels = [
        ("01", "Sourced input", "Explicit formula\n+ evidence\nOperator acceptance", SAND),
        ("02", "Revision graph", "FalkorDB\nAssertions · sources\nDependencies · history", MINT),
        ("03", "Logical query", "Z3\nConsistency first\nThen test the question", BLUE),
        ("04", "Proof check", "Bounded certificate\nSeparate checker\nVerify context + steps", MINT),
        ("05", "Saved answer", "Result + revision\nPremise references\nCertificate status", SAND),
    ]
    for i, (n, title, body, fill) in enumerate(labels):
        x = .55 + 2.64*i
        box(ax, x, 1.75, 2.34, 1.95, fill)
        text(ax, x+.2, 3.4, n, 10, TEAL, weight="bold")
        text(ax, x+.2, 2.98, title, 13, weight="bold")
        text(ax, x+.2, 2.32, body, 10, GRAY, linespacing=1.65)
        if i < 4:
            arrow(ax, (x+2.36, 2.77), (x+2.62, 2.77))
    arrow(ax, (12.25, 1.68), (4.33, 1.68), curve=-.13, color=GRAY, dashed=True)
    text(ax, 8.3, .92, "Result and premise dependencies are recorded in the graph", 10, GRAY, ha="center")
    footer(ax, "Certificate mode shown. The solver also has an explicit solver-only mode; proof budgets can be exceeded.")
    save(fig, "02-architecture")


def revisions():
    fig, ax = canvas(8.0, "The construction, step by step", "When a premise changes, revisit the answer",
        "One release, two immutable revisions. The policy is explicit in both.")
    box(ax, .55, 5.37, 12.9, .72, BLUE)
    text(ax, .8, 5.73,
         "Policy:  (API v2 ∧ tests pass) → ready       and       ¬tests pass → ¬ready", 12)
    for x, n, title, body, fill, tag in [
        (.55, "01", "Accept the starting facts", "Revision 12\nAPI v2 active\nTests pass", MINT, "PROVED: ready"),
        (4.95, "02", "Check and save the answer", "Question: release ready?\nSolver finds the consequence\nCertificate checks successfully", MINT, "BOUND TO REVISION 12"),
        (9.35, "03", "Receive a correction", "New source: tests failed\nReplace the old test assertion\nPublish revision 13 atomically", SAND, "NEW HEAD: 13"),
        (.55, "04", "Find affected answers", "Follow premise-use edges\nLocate recheck candidates\nDo not infer a new answer yet", BLUE, "DEPENDENCY TRAVERSAL"),
        (4.95, "05", "Ask at the new revision", "Recheck all accepted assertions\nThe negative policy applies\nReady is now refuted", SAND, "REFUTED: ready"),
        (9.35, "06", "Keep both explanations", "Revision 12: old proof retained\nRevision 13: current answer\nEach record keeps its context", MINT, "HISTORY PRESERVED"),
    ]:
        y = 3.1 if int(n) < 4 else .95
        box(ax, x, y, 4.1, 1.96, fill)
        text(ax, x+.22, y+1.68, n, 10, TEAL, weight="bold")
        text(ax, x+.7, y+1.68, title, 11.5, weight="bold")
        text(ax, x+.22, y+.98, body, 10, GRAY, linespacing=1.65)
        pill(ax, x+.22, y+.18, tag, color=RUST if fill == SAND else TEAL,
             fill="white", width=3.66)
    footer(ax, "A missing positive premise alone does not prove a negative. Refutation here needs the stated negative policy.")
    save(fig, "03-revision-walkthrough")


def results(s):
    fig, ax = canvas(8.15, "What we measured", "Strong small-case checks. A clear proof budget.",
        "Synthetic propositional problems · three fresh worker processes · in-memory API store")
    cards = [
        (f"{s['oracle']['correct']:,} / {s['oracle']['cases']:,}", "Logical classifications",
         "Matched a separate exhaustive\ntruth-table evaluator"),
        (f"{s['lifecycle']['passed_cycles']} / {s['lifecycle']['cycles']}", "Revision lifecycle cycles",
         "Passed controlled correction\nand revision-guard checks"),
        (f"{s['tampering']['attempts'] - s['tampering']['accepted']} / {s['tampering']['attempts']}",
         "Mutation probes rejected", "Tested proof corruption and\ncertificate-context mismatches"),
    ]
    for i, (number, title, body) in enumerate(cards):
        x = .55 + 4.4*i
        box(ax, x, 4.72, 4.1, 1.62, MINT)
        text(ax, x+.22, 5.96, number, 25, TEAL, weight="bold")
        text(ax, x+.22, 5.43, title, 11.5, weight="bold")
        text(ax, x+.22, 5.0, body, 9.5, GRAY, linespacing=1.45)
    text(ax, .65, 4.24, "Certificate coverage in the separate scaling workloads", 14, weight="bold")
    text(ax, .65, 3.88, "Verified decisive requests out of 180 per size; equal mix of three workload shapes", 10, GRAY)
    chart = fig.add_axes([.078, .192, .59, .25], facecolor=PAPER)
    sizes = [row['assertion_count'] for row in s['scaling_overview']]
    good = [row['verified_decisive'] for row in s['scaling_overview']]
    totals = [row['decisive_requests'] for row in s['scaling_overview']]
    chart.bar(range(len(sizes)), totals, color="#E6E9E6", width=.58)
    chart.bar(range(len(sizes)), good, color=TEAL, width=.58)
    for i, value in enumerate(good):
        chart.text(i, totals[i]+9, str(value), ha="center", fontsize=10, color=INK, weight="bold")
    chart.set(xticks=range(len(sizes)), xticklabels=sizes, ylim=(0, 214), yticks=[0, 90, 180])
    chart.tick_params(axis="both", colors=GRAY, labelsize=10, length=0, pad=8)
    chart.set_xlabel("Accepted assertions in the workspace", fontsize=10, color=GRAY, labelpad=9)
    for spine in chart.spines.values():
        spine.set_visible(False)
    chart.set_axisbelow(True)
    chart.grid(axis="y", color=LINE, linewidth=.6)
    box(ax, 10.0, 1.3, 3.42, 2.22, SAND)
    text(ax, 10.22, 3.17, "A different sample", 11.5, weight="bold")
    verified = s['proofs']['statuses']['VERIFIED']
    attempted = s['proofs']['decisive_attempts']
    text(ax, 10.22, 2.74, f"{verified} / {attempted} certified", 15, RUST, weight="bold")
    text(ax, 10.22, 2.0,
         "Small generated-case subset.\nThis rate does not describe\nthe scaling workloads.\nGray bars = uncertified requests.",
         9.5, GRAY, linespacing=1.65)
    text(ax, .65, .77, "At 64+ assertions in these workloads, classifications remained correct but no decisive certificate verified.", 10, RUST)
    footer(ax, "Source: benchmark-2026-10-25/summary.json · Finite test results; no live FalkorDB or language-model benchmark.")
    save(fig, "04-measured-results")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = SUMMARY.read_bytes()
    s = json.loads(data)
    hero()
    architecture()
    revisions()
    results(s)
    metadata = {
        "summary_path": str(SUMMARY.relative_to(HERE.parents[2])).replace("\\", "/"),
        "summary_sha256": hashlib.sha256(data).hexdigest(),
        "measured_source_revision": s["source_revision"],
        "matplotlib_version": matplotlib.__version__,
        "assets": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(OUT.iterdir()) if p.suffix in {".png", ".svg"}},
    }
    (HERE / "figure-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Rendered four PNG/SVG pairs; benchmark source {s['source_revision'][:7]}.")


if __name__ == "__main__":
    main()
