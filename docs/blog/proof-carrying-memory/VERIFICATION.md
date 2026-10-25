# Two-pass article verification

Completed 2026-10-25 by Saqlain / Codex. Scope: the blog article, its four figures and publishing kit. This is an evidence-based review, not a formal proof of the application or a repeat of the full benchmark. No production source, original measured artifacts, database state or configuration was changed.

## Pass 1: implementation, mathematics and measured evidence

Reviewed the actual implementation rather than treating historical planning documents as implemented behavior.

| Article claim | Evidence checked | Outcome |
| --- | --- | --- |
| Complete accepted-snapshot reasoning; consistency first; separate logical/solver-unknown outcomes | [solver.py](../../../src/memopops/solver.py), `classify` | Matches implementation |
| Explicit vocabulary and formula authoring | [api.py](../../../src/memopops/api.py), workspace initialization and query routes; [revisions.py](../../../src/memopops/revisions.py) | Matches implementation |
| Immutable revisions, source evidence and query dependency edges | [store.py](../../../src/memopops/store.py), `publish_revision`, `persist_query_result` | Matches implementation |
| Contradictory updates quarantined; only operators activate accepted memory | [api.py](../../../src/memopops/api.py), `publish_revision` | Matches implementation |
| Expected-head publication guards stale writes | [store.py](../../../src/memopops/store.py), expected-head predicate inside the publishing graph query | Implemented; this audit does not newly test live FalkorDB concurrency |
| Proof generation bounded; verified status requires independent math and context checks | [certificates.py](../../../src/memopops/certificates.py), [check.py](../../../packages/proofcheck/src/proofcheck/check.py), API query route | Matches implementation; clarified attempted generation |
| Unknown witness checking | API `check_witness_pair` path | Occurs in certificate mode; wording scoped explicitly |
| Dependency impact identifies recheck candidates | Store `get_revision_impact`; frontend [LiveApp.tsx](../../../apps/web/src/live/LiveApp.tsx) | Immediate parent revision, not all historical revisions; explicit new query required |

The [verification utility](verify_article.py) additionally ran these checks successfully:

- Verified all 19 recorded source checksums, allowing ordinary source-text checkout line endings where needed. Verified all six primary case/observation checksums **byte for byte**.
- Rebuilt the complete published `summary.json` from all **16,308 raw observations** and compared it for exact structural equality.
- Independently enumerated assignments for all **3,000 saved cases** with a new direct JSON truth-table interpreter, without importing the product evaluator or original benchmark oracle. All saved labels and observed classifications matched; cases were unique by exact formula/vocabulary fingerprint and balanced 750 per outcome.
- Recounted **90 lifecycle cycles**, each with 17 successful named checks; **600 rejected mutation probes** across 60 certificates; and **234 verified / six budget-exceeded** decisive requests in the 240-request generated-case subset.
- Recounted scaling coverage as **180/180, 180/180, 60/180, 60/180, 0/180, 0/180, 0/180** at 4, 8, 16, 32, 64, 128 and 256 assertions, respectively. Decisive classifications matched expected outcomes in these scaling requests.
- Replayed the article's exact positive and negative release policies through the real Z3 classifier and separate certificate checker. Initial facts gave **PROVED** with a context-matched valid certificate. Replacing the test result gave **REFUTED** with a context-matched valid certificate. Removing the explicit negative policy gave **UNKNOWN**, confirmed separately by truth-table enumeration.
- Checked worker orchestration in the measured harness: three sequential subprocess workers, declared seeds, discarded warmups and shuffled measurement schedules.

The original raw observations record witness-validation outcomes rather than every full witness assignment. The audit confirms those recorded outcomes and reviews the independent checking path; it does not freshly replay every original query or recheck unstored assignments. The newly replayed article examples are separate verification checks, not additional benchmark observations.

## Pass 2: interpretation, figures and publishing

Read the final article again for claims a reader might infer beyond what the implementation and experiments establish. Made these precision corrections:

1. Proof generation **attempts** a certificate and can exceed its budget; decisive classification alone is not a checked proof.
2. The current impact view concerns dependent answers at the **immediately preceding revision**. Finding candidates does not automatically rerun them.
3. Certified answers link to checked proof support; other answers conservatively link to the full snapshot. The article now describes both paths.
4. Revision numbers 12 and 13 are explicitly **illustrative**, not literal recorded runs or production revision identifiers.
5. Unknown witnesses are described within **certificate mode**, and Graphiti is described as a temporal graph framework.

Visually inspected all four delivered PNGs a second time. No clipped labels, overlapping text, missing mathematical symbols or misleading chart scales were found. The architecture assigns storage/traversal to FalkorDB and reasoning to Z3; the release walkthrough contains the negative policy needed for its refutation; the results figure separates the generated-case subset from scaling coverage. Its zero baseline, denominators and uncertified requests remain visible. No figure needed regeneration.

Confirmed all eight PNG/SVG hashes against `figure-metadata.json` and the figure's benchmark-summary checksum against the original file. All PNGs are 2,520 px wide; all SVGs parse successfully and retain their text labels without replacement characters. The four SVG text layers contain 24, 31, 42 and 44 labels, respectively. SVG text remains editable; its exact typography depends on installed fonts in a downstream editor. Upload the PNGs for the intended blog appearance and allow readers to enlarge the denser figures.

All local article and publishing-guide links resolve. Reopened the primary [Doyle/MIT](https://dspace.mit.edu/handle/1721.1/5733), [LRAT/arXiv](https://arxiv.org/abs/1612.02353), and [Graphiti](https://github.com/getzep/graphiti) references and checked the claims against their contents. The web fetcher could not retrieve the personal GitHub report page, so the report was separately fetched from the public `raw.githubusercontent.com` path through the available proxy with HTTP 200. Repository publication remains verifiable through Git.

## Result and reproduction

**The checked numerical claims and formal example are supported. The wording corrections above are incorporated. No unsupported novelty, universal-accuracy, factual-truth or production-performance claim remains in the reviewed article.** The two stated limitations remain material: bounded proof generation and synthetic/in-memory evaluation scope.

From the repository root:

```powershell
uv run --locked python docs/blog/proof-carrying-memory/verify_article.py
```

The actual audit used the existing environment directly:

```powershell
& .venv/Scripts/python.exe docs/blog/proof-carrying-memory/verify_article.py
```

Both commands invoke the same utility; no new dependencies are required. The final run returned `"status": "PASS"`. Its [saved machine-readable output](verification-results.json) records the checked counts and example outcomes. The qualitative source review, external-source reading and visual inspection are manual checks, separate from that automated output.
