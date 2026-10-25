# A workspace for facts, rules and decisions

memopops stores evidence-backed propositional knowledge shared by people and agents. Use it for a bounded project policy: what the team accepts, which rules follow from those premises, and which conclusions need rechecking after a correction. FalkorDB stores the revisions and dependencies; Z3 classifies a question and the independent checker validates supported certificates.

## Start with your own database

Requires Python 3.12, uv, Node.js 24/npm, and a running local or managed FalkorDB. Docker is optional when you already have a database.

1. Preserve an existing private configuration. For a new checkout, copy `.env.example` to `.env`.
2. Set the actual FalkorDB host, port, username, password and TLS requirement from your provider. A hostname from an expired deployment will not work. Keep all values private.
3. Set `MEMOPOPS_AUTH_TOKENS` to distinct reader/writer/operator identities assigned to your own workspace ID. The JSON keys are the bearer tokens. Readers query memory; operators initialize and change accepted memory. A writer cannot activate claims. Use fresh private tokens outside a disposable local demo.
4. Install locked dependencies and start the API from the repository root:

```powershell
uv sync --locked --group dev
uv run --locked python -m memopops --env-file .env --port 8001
```

In another terminal:

```powershell
npm --prefix apps/web ci
$env:MEMOPOPS_API_ORIGIN = 'http://127.0.0.1:8001'
npm --prefix apps/web run dev
```

Open `http://127.0.0.1:5173`. Tokens stay in page memory and are not placed in URLs or browser storage. Exported environment settings override the configuration file; clear stale exported settings if you intentionally change databases. The API binds to loopback. No model API key is needed for the explicit logic workflow.

## Define your vocabulary

Enter the workspace ID assigned to your operator token and paste that token without the `Bearer` prefix. Before connecting, expand **Create your own workspace**. Define proposition IDs, readable labels, precise meanings and scopes. Initialization creates an empty knowledge revision, not invented observations.

For example:

| ID | Label | Meaning | Scope |
| --- | --- | --- | --- |
| `tests_pass` | Tests pass | Every required test in the reviewed test report passed | Orion version 3 |
| `approved` | Approved | The version is approved under the recorded test-only policy | Orion version 3 |
| `docs_signed` | Documentation signed | The designated reviewer signed the version's documentation | Orion version 3 |

IDs use lowercase letters, digits and underscores and start with a letter. Define the complete vocabulary first: this version deliberately freezes proposition meanings and membership after initialization. To change the meaning, create a separately scoped workspace. Initializing again with the identical definitions is safe; different definitions cannot overwrite a workspace or reset its history. An operator token cannot initialize another tenant's workspace.

## Add facts and explicit policies

Choose **Manage facts and rules** or **List**. Add a proposition using the atom selector, or expand **Write a rule or compound expression**. Provide a source URI, an excerpt, its observation time and a reason. Observation time is converted from local time to UTC. Evidence is provenance, not a guarantee of factual accuracy.

The expression field overrides the atom and negation controls when filled:

| Notation | Meaning |
| --- | --- |
| `!p` | not p |
| `p & q` | p and q |
| `p \| q` | p or q |
| `p -> q` | p implies q |
| `p <-> q` | p is equivalent to q |

Unicode `¬ ∧ ∨ → ↔` is also accepted. Precedence is not, and, or, implication, equivalence; implication groups to the right. Prefer parentheses for a policy such as `(api_v2 & tests_pass) -> release_ready`. The client compiles this notation deterministically into the same bounded AST checked by the server. It does not silently translate natural language into accepted logic.

For the test-only policy example, add sourced `tests_pass` and the separately sourced rule `tests_pass <-> approved`. This policy says test passage is both necessary and sufficient; only use equivalence when that stronger policy is actually intended. An implication alone expresses sufficiency.

## Ask, correct and recheck

In **Queries**, ask `approved`, or enter a compound **Query expression** under **Advanced formula**. Decisive results receive VERIFIED only when the independent checker accepts their certificate and context. With no premise about `docs_signed`, asking it produces UNKNOWN; absence is not negation. Solver limits and certificate limits retain distinct statuses.

Saved questions reopen with their original revision and proof. Selecting an older question pins that revision; use the current-revision control before asking about today's state. Historical proof validity does not imply current applicability. Query-history pages are bounded and use a time/ID cursor rather than an unstable offset.

New records retain the submitted question and a small history summary, so listing questions does not fetch their full certificates. Older records remain readable; if an older record did not save its expression, the interface labels that detail unavailable rather than inventing a question.

To correct a known obsolete observation, choose **Replace an outdated claim**, select that claim, enter its replacement and new evidence, and explain the correction. Replacing `tests_pass` with `!tests_pass` under the equivalence policy makes `approved` REFUTED. Under only `tests_pass -> approved`, failing tests would instead leave approval UNKNOWN: the inverse does not follow from an implication.

To withdraw a claim without asserting its opposite, choose **Retract a claim** and give a reason. Retraction creates a new revision and keeps prior evidence in history; it does not require fabricated new evidence. Adding a contradiction alongside an accepted claim quarantines the candidate. Inspect its submitted formulas and sources, then make an explicit correction if appropriate. No automated “newest text wins” rule promotes it.

## API additions

- `POST /api/v1/workspaces/{workspace}/initialize`: operator only; `{ "atoms": [{ "id", "label", "meaning", "scope" }] }`, 1–128 unique propositions. Returns the initial revision. Existing different vocabularies return 409.
- `GET /api/v1/workspaces/{workspace}/memory`: adds full `atoms` definitions while retaining `atom_ids` for existing clients.
- `GET /api/v1/workspaces/{workspace}/queries?limit=25&before={query_id}`: up to 50 saved-query summaries per page, current/historical freshness and `next_cursor`. It does not include certificate bodies or tokens.
- Existing revision/query/certificate routes and Boolean AST semantics are unchanged.

## Boundaries

This is a propositional knowledge service, not a general conversation-memory replacement. It does not reason about quantifiers, numbers or time automatically; scope those meanings explicitly. It does not verify sources or an LLM's interpretation. No automatic ingestion, vector search, managed identity service or credential rotation is claimed. The vocabulary is fixed, assertions remain bounded at 256 active claims, and formulas retain the 64-node/16-level limits.

The October 25 custom-workspace lifecycle is covered by API, solver/checker, browser and store-adapter regressions. The old supplied cloud hostname no longer resolves, so the new initialization/history Cypher still needs rehearsal against a reachable FalkorDB deployment. Earlier cloud checks for the October 18 implementation do not establish validation of the new persistence paths.
