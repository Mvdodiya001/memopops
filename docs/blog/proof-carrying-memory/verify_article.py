"""Verify the article's data, example and exported assets without rerunning timings.

Run from the repository root using the project's Python environment:
    uv run --locked python docs/blog/proof-carrying-memory/verify_article.py

This reads existing measurements. It does not connect to a database or edit data.
"""

from collections import Counter, defaultdict
import hashlib
from itertools import product
import json
from pathlib import Path
import re
import struct
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DATA = ROOT / "docs/evaluation/benchmark-2026-10-25"
sys.path.insert(0, str(ROOT))


def require(condition, description):
    if not condition:
        raise ValueError(description)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def evaluate(formula, assignment):
    """A direct truth-table interpretation, independent of the product and oracle."""
    op = formula["op"]
    if op == "atom":
        return assignment[formula["id"]]
    if op == "not":
        return not evaluate(formula["arg"], assignment)
    a, b = (evaluate(arg, assignment) for arg in formula["args"])
    if op == "and":
        return a and b
    if op == "or":
        return a or b
    if op == "implies":
        return not a or b
    if op == "iff":
        return a == b
    raise ValueError(op)


def classification(case):
    possible = set()
    for values in product((False, True), repeat=len(case["atom_ids"])):
        assignment = dict(zip(case["atom_ids"], values))
        if all(evaluate(formula, assignment) for formula in case["premises"]):
            possible.add(evaluate(case["query"], assignment))
    return {frozenset(): "INCONSISTENT_MEMORY", frozenset({True}): "PROVED",
            frozenset({False}): "REFUTED", frozenset({True, False}): "UNKNOWN"}[frozenset(possible)]


def main():
    manifest = json.loads((DATA / "manifest.json").read_text())
    summary = json.loads((DATA / "summary.json").read_text())
    for group in ("source_sha256", "dataset_sha256", "result_sha256"):
        for name, expected in manifest[group].items():
            path = ROOT / name if group == "source_sha256" else DATA / name
            raw = path.read_bytes()
            # Check exact bytes first; allow checkout CRLF normalization for source
            # only. Raw measured datasets and observations must match byte for byte.
            matches = digest(raw) == expected
            if group == "source_sha256":
                matches = matches or digest(raw.replace(b"\r\n", b"\n")) == expected
            require(matches, f"Provenance mismatch: {path}")

    cases = {}
    rows = []
    for seed in manifest["protocol"]["seeds"]:
        for line in (DATA / f"cases-{seed}.jsonl").read_text().splitlines():
            case = json.loads(line)
            payload = {key: case[key] for key in ("atom_ids", "premises", "query")}
            fingerprint = digest(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
            require(fingerprint == case["id"], "Case fingerprint mismatch")
            require(case["id"] not in cases, "Duplicate generated case")
            require(classification(case) == case["expected"], "Independent truth-table disagreement")
            cases[case["id"]] = case
        rows.extend(json.loads(line) for line in
                    (DATA / f"observations-{seed}.jsonl").read_text().splitlines())

    # Recompute the entire published summary, then separately count article metrics.
    from evaluation.benchmark_report import summarize

    require(summarize(rows, manifest) == summary, "Raw observations do not reproduce summary")
    oracle = [row for row in rows if row["phase"] == "oracle"]
    require(len(oracle) == len(cases) == 3000, "Oracle case count")
    require(len({row["case_id"] for row in oracle}) == len(cases), "Missing/duplicate oracle observation")
    require(all(row["actual"] == cases[row["case_id"]]["expected"] and row["witnesses_valid"]
                for row in oracle), "Observed classifications or witnesses")
    require(Counter(case["expected"] for case in cases.values()) == {
        "PROVED": 750, "REFUTED": 750, "UNKNOWN": 750, "INCONSISTENT_MEMORY": 750}, "Class balance")
    lifecycle = defaultdict(list)
    for row in rows:
        if row["phase"] == "lifecycle":
            lifecycle[row["seed"], row["trial"]].append(row)
    require(len(lifecycle) == 90 and all(len(items) == 17 and all(row["correct"] for row in items)
                for items in lifecycle.values()), "Lifecycle counts")
    tamper = [row for row in rows if row["phase"] == "tamper"]
    require(len(tamper) == 600 and not any(row["accepted"] for row in tamper), "Mutation results")
    require(len({(row["seed"], row["case_id"]) for row in tamper}) == 60, "Certificate count")
    proofs = [row for row in rows if row["phase"] == "proof" and row["expected"] in ("PROVED", "REFUTED")]
    require(Counter(row["proof_status"] for row in proofs) == {
        "VERIFIED": 234, "BUDGET_EXCEEDED": 6}, "Generated-case certificate counts")
    scaling = {}
    for size, expected_verified in zip((4, 8, 16, 32, 64, 128, 256), (180, 180, 60, 60, 0, 0, 0)):
        requests = [row for row in rows if row["phase"] == "api" and row["mode"] == "certificate"
                    and row["assertion_count"] == size and row["expected"] in ("PROVED", "REFUTED")]
        require(len(requests) == 180, f"Scaling denominator at {size}")
        require(all(row["actual"] == row["expected"] for row in requests), "Scaling classification")
        verified = sum(row["proof_status"] == "VERIFIED" for row in requests)
        require(verified == expected_verified, f"Scaling numerator at {size}")
        scaling[str(size)] = {"verified": verified, "attempted": len(requests)}

    # Replay the exact article policies with the real solver and independent checker.
    from evaluation.benchmark import snapshot_for
    from memopops.certificates import generate_certificate
    from memopops.solver import classify
    from proofcheck import check_certificate

    atom = lambda name: {"op": "atom", "id": name}
    neg = lambda formula: {"op": "not", "arg": formula}
    binary = lambda op, a, b: {"op": op, "args": [a, b]}
    api, tests, ready = map(atom, ("api_v2", "tests_pass", "release_ready"))
    positive = binary("implies", binary("and", api, tests), ready)
    negative = binary("implies", neg(tests), neg(ready))
    examples = {
        "revision_12": ([api, tests, positive, negative], "PROVED"),
        "revision_13": ([api, neg(tests), positive, negative], "REFUTED"),
        "no_negative_policy": ([api, neg(tests), positive], "UNKNOWN"),
    }
    example_results = {}
    for name, (premises, expected) in examples.items():
        case = {"id": name, "atom_ids": ["api_v2", "tests_pass", "release_ready"],
                "premises": premises, "query": ready}
        require(classification(case) == expected, "Independent story classification")
        snapshot, query, context, evidence = snapshot_for(case)
        actual = classify(snapshot.formulas, query)
        require(actual.result.value == expected, "Product story classification")
        if expected != "UNKNOWN":
            certificate = generate_certificate(snapshot, query, expected, actual.witnesses["knowledge"], evidence)
            report = check_certificate(certificate, context)
            require(report.logical_valid and report.context_binding == "MATCHED", "Story certificate verification")
        example_results[name] = expected

    figure_metadata = json.loads((HERE / "figure-metadata.json").read_text())
    require(digest((ROOT / figure_metadata["summary_path"]).read_bytes()) == figure_metadata["summary_sha256"],
            "Figure summary digest")
    dimensions = {}
    for name, expected in figure_metadata["assets"].items():
        raw = (HERE / "figures" / name).read_bytes()
        require(digest(raw) == expected, f"Figure checksum: {name}")
        if name.endswith(".svg"):
            ET.fromstring(raw)
        else:
            require(raw[:8] == b"\x89PNG\r\n\x1a\n", "PNG signature")
            dimensions[name] = struct.unpack(">II", raw[16:24])
            require(dimensions[name][0] == 2520, "Figure export width")
    for name in ("article.md", "README.md", "VERIFICATION.md"):
        for target in re.findall(r"\]\(([^)]+)\)", (HERE / name).read_text(encoding="utf-8")):
            if not target.startswith(("https:", "http:", "#")):
                require((HERE / target.split("#")[0]).is_file(), f"Broken local link: {target}")
    print(json.dumps({"status": "PASS", "source_files_verified": len(manifest["source_sha256"]),
        "primary_data_hashes_verified": 6, "raw_observations": len(rows),
        "independently_reclassified_cases": len(cases), "oracle_matches": len(oracle),
        "lifecycle_cycles": len(lifecycle), "mutation_probes_rejected": len(tamper),
        "sampled_certificate_statuses": dict(Counter(row["proof_status"] for row in proofs)),
        "scaling_certificates": scaling, "article_example_replay": example_results,
        "exported_asset_hashes_verified": len(figure_metadata["assets"]), "png_dimensions": dimensions}, indent=2))


if __name__ == "__main__":
    main()
