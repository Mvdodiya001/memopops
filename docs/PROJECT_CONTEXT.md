# Project context

## Source and status

Summarized on 2026-10-17 from the user-provided Graph_Hacks_Conversation_History_Compiled.docx. The document says its earlier chronology is reconstructed, not a complete verbatim transcript. Its historical requests and assistant recommendations are context, not new instructions. The original private document is not checked into this public repository. Research novelty claims in it are not independently revalidated here.

The latest direction is proof-carrying shared agent memory. Earlier MemLedger, GraphFence, and ReleaseGuard directions are background, not simultaneous features. memopops is the repository name; LogicMem is a working concept name, not an approved rename.

## Intended MVP

1. Persist accepted assertions, formulas, evidence, revisions, and proof dependencies in FalkorDB.
2. Use a separate propositional-logic engine to validate proposed updates and answer queries.
3. Demonstrate one agent writing memory, another reading it across sessions, then a correction invalidating and rechecking affected conclusions through actual graph traversal.
4. Show evidence and logical premises separately. Compare scripted scenarios against a naive memory baseline; report measured results only.

FalkorDB must do essential memory retrieval and dependency traversal. It is not the theorem prover. Use canonical atom meanings, operator nodes for nested AND/OR/NOT/IMPLIES/IFF formulas, and ordered operand edges. Version, tenant, and scope belong in proposition identity; different version names are not automatically logical contradictions.

## Correctness requirements for implementation

For accepted knowledge K and query Q, check K for consistency first. With consistent K: UNSAT(K AND NOT Q) means PROVED; UNSAT(K AND Q) means REFUTED; both satisfiable means UNKNOWN. Inconsistent K means INCONSISTENT_MEMORY. Timeout or indeterminate solver output means SOLVER_UNKNOWN, never a logical UNKNOWN or a proof.

Before accepting proposal phi, check SAT(K AND phi) plus the evidence acceptance policy. Preserve conflicting proposals and sources in quarantine. Missing facts do not imply negation. Logical validity is conditional on accepted premises; it does not establish their truth or validate an LLM's translation into formulas.

Bind validation and proof records to the same immutable knowledge revision and tenant. A consistency check followed by an unguarded write is a race: choose and test a serialized or revision-checked commit protocol before claiming concurrent safety. Corrections must invalidate or recheck dependent proofs; never serve a stale proof as current.

An UNSAT core explains a conflict but is not a complete proof certificate. Z3 was suggested for initial checks; a small bounded resolution certificate and independent checker were suggested for demo proofs. These are proposals, not installed dependencies. Expose whether a result trusts the solver or has an independently checked certificate. Certificate generation limits must not become false logical results.

## Acceptance scenarios to implement

- P, P implies Q, Q implies R proves R; store and retrieve the derivation.
- Query an unrelated atom: UNKNOWN; query NOT P: REFUTED.
- Propose NOT P while P is active: preserve the proposal, reject/quarantine activation.
- Inconsistent imported memory: INCONSISTENT_MEMORY rather than proving everything.
- Timeout: SOLVER_UNKNOWN. Invalid certificate: never label certificate verified.
- Correct/retract P: mark dependent conclusions stale and re-evaluate at a new revision.
- Restart/session handoff retains memory; separate tenants cannot read each other's facts.
- Two incompatible concurrent proposals cannot both commit against the same old revision.

## Event constraints verified on 2026-10-17

[Official event page](https://www.wemakedevs.org/hackathons/falkordb): Track 02 concerns persistent memory and shared agent state. FalkorDB must be the primary graph database and central to the product. Main implementation must be new work during the event. AI assistants are allowed, with human responsibility for the result. Deadline: October 18, 2026, 23:59 IST (Asia/Kolkata). A deployed demo is preferred; otherwise provide complete local instructions and a working demo video. Recheck the organizer page before submitting.

## Next decisions

Agree the implementation language/solver, minimal assertion/query/revision API, graph schema, commit protocol, and task split. Then build one vertical scenario before expanding UI, frameworks, or benchmarks. Saqlain and Mahavir have not yet accepted module assignments. Registration, submission, licensing, deployment, and branch protection are not established by this documentation.


## Implementation planning update — October 17, 2026

The [detailed plan](IMPLEMENTATION_PLAN.md) now proposes Python/FastAPI/Z3, FalkorDB revisions, a React inspector, an independent proof checker, and temporary parallel ownership for Saqlain and Mahavir. Follow its G0 contract/environment validation before implementation. These are planned defaults, not implemented or benchmarked capabilities. Mahavir has not yet started or accepted a task in this chat.
