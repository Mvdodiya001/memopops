# Frontend visualization and recording plan

Status: frontend implementation delivered in S-20261018-04 after user authorization. See the [frontend guide](../FRONTEND_GUIDE.md) and Saqlain's log for usage, verification, and live-service limitations. Planning owner: Saqlain. Planning task: S-20261018-03. Audited planning base: `8172f64` on October 18, 2026. The specification below preserves the intended design and optional enhancements.

## 1. Product direction and scope

Build a calm, precise visual workspace that answers three questions immediately:

1. What does the agent currently know, and where did that knowledge come from?
2. Which accepted premises support its answer and decision?
3. When a premise changes, what must be reconsidered?

The visual centerpiece is the transition from a supported release decision to a correction and a new decision. Keep a stable graph on screen while the selected revision, supporting assertions, and decision change. A judge should understand the contribution without reading JSON, then be able to inspect the records behind every statement.

Use the existing React/TypeScript/Vite application. Implement presentation, read adapters, graph projection, artifact import, and browser tests. Preserve the API, FalkorDB schema, solver, checker, Gemini adapter, agent behavior, and terminal runner. Existing query and operator forms retain their behavior. New observer and replay views perform reads only.

**Recommended navigation:** Run walkthrough · Memory graph · Queries · History. Retain the memory list as a List/Graph switch within Memory graph. Keep quarantine accessible there and as a walkthrough chapter. Avoid a separate generic dashboard of unrelated statistics.

**Delivery order:** coherent live graph first; recorded walkthrough second; recording polish third. Do not begin with particle effects, a 3D graph, or a new UI framework.

## 2. What the latest implementation actually provides

Read these files again if main has advanced: `scripts/demo_video.py`, `agents/session.py`, `apps/web/src/live/LiveApp.tsx`, `apps/web/src/api/client.ts`, `src/memopops/api.py`, `src/memopops/store.py`, and `docs/submission/GRAPH_MODEL.md`. Earlier architectural plans contain proposals superseded by implementation.

| Existing capability | Consequence for this plan |
| --- | --- |
| Nine demo scenes: preflight, memory, reader, uncertain, writer, correction, resume, verify, graph | Use this order for the walkthrough. A scene is complete only when supported by its recorded outcome. |
| Baseline revision is discovered and validated at runtime | Never hardcode `rev_001` or assume the next revision is `rev_002`. Show actual IDs with optional Baseline/Corrected aliases. |
| Reader/writer journals and a summary are written to the take directory | A browser can import these with a file picker, without adding a backend service. |
| Read endpoints expose memory, workspace head, history, quarantine, impact, and individual query results | These support a live graph and enrichment of imported runs. |
| No live agent event stream, query-list route, or decision-list route | Polling cannot discover all terminal calls or every new decision. Do not pretend otherwise. |
| `reader.json` is resumed in the same runner process | Describe this as a resumed journal/session. It is not a demonstrated database or operating-system restart. |
| Live Gemini calls can fall back to scripted behavior | Label the actual recorded mode per scene where known; a request for live mode is insufficient. |
| Graph scene saves Cypher and row counts, not the complete result rows | Show recorded row counts and query text. Obtain visual records from the API/journals; do not invent raw graph rows. |
| Formula AST is stored as canonical JSON in a Formula node | Formula syntax diagrams are derived views, not persisted operator nodes. |
| Current UI polls readiness, but not all changing workspace data | Head, history, and quarantine observation need a deliberate refresh policy. |

Observed baseline in this planning task: **154 pytest tests passed; 40 independent checker tests passed; 8 web tests passed; TypeScript check and production build passed; 4/4 lab acceptance cases passed.** This is not an exhaustive code audit, a new browser visual check, or a live FalkorDB/Gemini validation. Record fresh results after implementation.

## 3. Hackathon story and design references

The event emphasizes agents acting on connected context and persistent shared memory. Track 02 is the clearest fit. Show FalkorDB's contribution through revision membership, provenance, stored query support, and dependency impact. Explain the distinct roles: FalkorDB stores/retrieves relationships; the logic engine answers the formal query; the independent checker checks the certificate. The frontend makes those outputs inspectable. [Official event brief](https://www.wemakedevs.org/hackathons/falkordb).

The official deadline is October 18, 2026, 23:59 IST. A working video and complete local setup remain necessary when deployment is omitted. Timebox UI work so recording, upload, and submission still have a protected buffer. This plan does not publish or deploy anything. [Official FAQ](https://www.wemakedevs.org/hackathons/falkordb).

Apply Apple's emphasis on comfortable information density, a spacious content area, familiar controls, and keyboard access. Use brief, optional motion that communicates a change and does not delay interaction. These are principles adapted to this web app; the precise layout and tokens below are our design decisions. Sources: [Designing for macOS](https://developer.apple.com/design/human-interface-guidelines/designing-for-macos), [Motion](https://developer.apple.com/design/human-interface-guidelines/motion).

## 4. Visual specification

### 4.1 Overall character

Make this feel like a carefully designed research/productivity application: warm neutral canvas, crisp white content, restrained blue selection, precise typography, and generous space around the graph. Preserve the useful foundation in `global.css`.

| Element | Specification |
| --- | --- |
| Canvas / panel / sidebar | `#F5F5F7` / `#FFFFFF` / `#EFEFF2` |
| Main / secondary text | `#1D1D1F` / `#5C5C63` |
| Selected/focus color | Existing `#2457A7`; pale blue surface behind selection |
| Positive / attention / blocked | Existing muted green, ochre, and red tokens; always include words and an icon |
| Typography | System font stack; 30–32px page title, 21–24px section title, 16px body, 13–14px supporting metadata; monospace only for IDs/formulas/code |
| Spacing | 4/8/12/16/24/32/48px scale; 24–32px panel padding |
| Controls | 36–40px desktop height; at least 44px targets in narrow/touch layouts |
| Corners | 12–16px content panels; 8px controls; pill only for short statuses |
| Borders / elevation | 1px neutral boundary; very light shadow for floating inspector or popover only |
| Icons | Small consistent inline SVG strokes, paired with text where meaning is ambiguous |

No neon accents, decorative gradients, glass over text, giant marketing headings, glowing wires, fake avatars, or constantly moving backgrounds. Avoid duplicating the same data in several statistic cards. Numbers appear only when they answer something useful, such as "4 accepted assertions" or "1 affected result".

Check actual contrast in the browser, particularly muted node labels and status backgrounds. Do not rely on this token list as proof of accessibility.

### 4.2 Desktop composition

Target a 1920×1080 recording, with a 1440×900 layout also verified. At 1440px, use roughly 184px navigation, a flexible center, and a 300px inspector. At 1920px, allow about 208px navigation and a 340px inspector. The graph gets most of the remaining width. Constrain prose to readable lines instead of stretching cards across empty space.

```text
┌───────────────────────────────────────────────────────────────────────────┐
│ memopops     Shared memory, with reasons.      workspace · data source     │
├─────────────┬──────────────────────────────────────────────┬──────────────┤
│ Walkthrough │ Release readiness                            │ Selected     │
│ Memory graph│ Baseline → Corrected       Revision / Follow │ record       │
│ Queries     ├──────────────────────────────────────────────┤              │
│ History     │ Chapter title + one sentence of explanation  │ Formula      │
│             │                                              │ Source       │
│ Connection  │       Stable, readable relationship graph    │ Revision     │
│ Last checked│                                              │ Support      │
│             │                                              │              │
│             ├──────────────────────────────────────────────┤ Exact IDs    │
│             │ Observed outcome · proof · revision          │ Details ▸    │
│             │ Previous   1 2 3 4 5 6 7 8 9   Next          │              │
└─────────────┴──────────────────────────────────────────────┴──────────────┘
```

Under 1200px, make the inspector an explicit drawer so the graph remains useful. Under 760px, use a stacked layout with an accessible relationship list as the default; keep graph access optional. No horizontal scrolling of the whole page. Focus mode collapses navigation and inspector, but retains title, source, actual mode, revision, and error indicators.

### 4.3 Motion and graph stability

- Use 160–220ms opacity/selection transitions; use at most 300ms for an intentional revision comparison transition.
- Keep unchanged nodes in the same positions. Do not rerun a random force layout after every refresh.
- Highlight supported edges on selection; a one-time reveal can explain the recorded path. Call it a support-path illustration, not a trace of the database engine's execution order.
- Disable movement under `prefers-reduced-motion`. All state remains understandable from text, stroke, and icons.
- Never loop a pulse on a persisted record to imply an agent is still executing. Loading belongs to the request indicator.
- Presentation navigation is manual by default; optional timed playback is a later enhancement, not an MVP requirement.

## 5. Two data experiences, with explicit provenance

### A. Live memory observer

Connect through the existing authentication flow. Show the selected immutable revision and poll for workspace head/quarantine changes. This can run alongside the terminal, but it does not observe every tool call.

Header: `Live API · Last checked 14:32:10 · Revision <actual ID>`. A recent HTTP response is not evidence that the model is active. On failure, preserve the last valid graph with `Last successful read … · Refresh failed`; never leave an unqualified green connected status.

### B. Recorded run walkthrough

Use a standard `<input type="file" multiple>` to import explicitly selected files from one existing take directory. No automatic filesystem access, local HTTP file server, directory watcher, upload, or automatic execution. A normal multi-file picker is sufficient for the MVP.

Header: `Recorded run · Take <value> · <actual model mode or unavailable>`. Importing a completed run provides a deterministic, polished recording experience. It must remain labelled as a recorded walkthrough even when historical details are enriched through a live API.

The imported run is not cryptographically authenticated. A displayed service/checker outcome is a reported result from that source, not a new independent verification performed by JavaScript.

### Import contract

| File | Treatment |
| --- | --- |
| `summary.json` | Required. Workspace, take, requested mode, fallback flag, baseline ID, and available scene results. Validate before replacing the active run. |
| `reader.json` | Optional but strongly recommended. Contains both initial and resumed reader events in the final file. |
| `reader-docs.json` | Optional uncertainty-session events and local abstention. |
| `writer.json` | Optional writer events and actual recorded journal mode. |
| `gemini-transcript.json` | Optional detail-only tool transcript. Do not use as the authoritative chronology of service outcomes. |
| `graph-queries.cypher` | Optional text display; never execute imported Cypher from the browser. |
| `certificate-<baseline>.json`, `certificate-tampered.json` | Optional download/details. Parsing an imported certificate is not verification. |

Bound imports: at most 12 files, 5 MiB per file, 20 MiB total; at most 2,000 normalized events; formula depth at most 64 for rendering. Reject oversize input before reading it. Validate known fields and enum values, bound string lengths, render strings as text, and ignore unknown fields. Do not recursively render arbitrary objects. Duplicate filenames, malformed JSON, mismatched workspace IDs, contradictory query/revision bindings, or repeated conflicting records produce actionable errors. Keep the previous valid run if a new import fails.

Files have no shared signed run identifier. Enforce the available workspace, baseline, query, and revision consistency checks; disclose that consistency checks cannot prove all files came from one execution. Display filenames in the source details. Never infer a filename's date as event time.

Do not store imports or bearer tokens in localStorage, URLs, analytics, or logs. Use in-memory state, explicit Replace/Clear actions, and revoke object URLs used for downloads. Display only allowlisted fields; raw transcript text is excluded from the main presentation and receives a review step before showing it in a recording.

### Record semantics that the importer must handle

1. `summary.scenes.reader.mode`, `uncertain.mode`, and `resume.mode` describe those scene modes. `requested_model_mode` does not. Writer mode may come from `writer.json`; without it say `Mode unavailable`. Operator/checker/database chapters are not model generations.
2. A final reader journal's top-level mode may describe the resumed run, so do not apply it to earlier events. Use scene-specific metadata where available and show uncertainty where mapping is ambiguous.
3. `inspect_memory` events contain assertion IDs/formulas and atom IDs, but not evidence excerpts or the complete memory response. An offline graph can show the recorded assertion snapshot; evidence requires a matching API response. Missing evidence is labelled unavailable.
4. Query events contain result/proof status/support IDs, but not the complete query formula or certificate. Load the existing query-by-ID route for enrichment. Use explicit demo chapter labels only as scenario labels; do not invent missing result fields.
5. Reader and resumed events share an array; preserve original event order. Associate chapters using summary query IDs and actual revision IDs. An unmatched event stays in an `Other recorded events` list. Do not guess scene boundaries from a fixed event count.
6. Session events lack a reliable global timestamp stream. Chapter order comes from the runner, and event order comes from each journal. Show step numbers, not invented wall-clock times, durations, concurrent lanes, or precise cross-file interleaving.
7. Decision event `outcome` may be `PROCEED` or `BLOCK` because the persisted local decision overwrites the initial `ok` key. Interpret events by tool plus validated fields; do not assume all successful events have `outcome: ok`.
8. An abstention is local journal data with `persisted: false` on its event. No Decision node should be invented for it. Likewise a journal decision's old `status: current` is not proof it is still the current database decision.
9. Partial runs are allowed. Chapters absent from the summary show `Not recorded`. A summary recorded after a scene and a journal saved mid-scene can differ; label extra journal events as partial, not completed chapters.
10. Graph `row_counts` are recorded results of two Cypher queries, not graph node counts. The summary's verifier exits are reported CLI outcomes; success requires the valid exit to be 0 and tampered exit to be 1. Any other combination is a failed/incomplete check, not a celebratory success screen.

## 6. Screen-by-screen specification

### 6.1 Connection and run selection

Retain the existing connection form and explicit development fixture entry. Add a concise choice between `Connect to memory` and `Open recorded run`. Keep the token field masked, in memory, and off the recording once connected. Import should work without API availability; API enrichment is optional and uses the existing workspace authorization.

After connection, discover the actual head before selecting a default revision. Honor an explicitly requested historical URL revision. If that revision is unavailable, show the error and an explicit `Open current revision` action. Never silently substitute a different revision under the same heading.

On opening a run, show a compact readiness panel: chapters present, files loaded, missing details, actual per-scene mode, and whether the selected API workspace matches. Choose `Open walkthrough` only after validation succeeds.

### 6.2 Memory graph

Title `Accepted memory`, subtitle `Assertions and the records behind them`. Controls: revision selector, Follow head toggle, List/Graph segmented switch, Fit, zoom in/out, and optional `Show formulas` / `Show evidence` switches. The initial camera is stable and fills the canvas without cropping labels.

Default structure: Revision → Assertions → Evidence, with formula text inside assertion cards. Expand `Show formulas` to reveal a separate Formula presentation node for each assertion's encoded AST. Keep relationship direction faithful to storage even when columns arrange edges for readability.

Assertion cards show a readable formula label, short ID, and source count. Selecting a card highlights its incident relationships and opens the inspector with full formula, actual IDs, source excerpt/URI, and revision membership. An ID-derived human label is a display transformation, not an externally validated atom meaning. Existing `accepted_at_revision` normalization represents the selected snapshot, so label it `Included in this revision`, not `First accepted here`.

A query selected from a known query ID can add its QueryResult card and support overlay. No query-list endpoint exists; use IDs from imported journals, impact results, the current browser query result, or an explicit `Open query ID` input. Never poll guessed IDs.

Quarantine sits in a visually distinct section below/alongside accepted memory. It has a `BASED_ON` link to the baseline revision, no `INCLUDES` edge. Show the submitted mutation and validation reason. An exact minimal conflict core is unavailable and must not be drawn.

### 6.3 Run walkthrough: nine chapters

Each chapter contains a short title, one explanatory sentence, an evidence-backed outcome, the relevant graph focus, and optional details. Source, scene mode, and actual revision remain visible in focus mode. A fixed bottom strip provides Previous/Next and chapter selection; arrow keys work outside input controls. Future chapters are visibly unavailable until recorded.

| Chapter | Visual action | Required evidence / truthful fallback |
| --- | --- | --- |
| 0. Ready | Compact preflight summary, baseline revision, readiness result | `summary.scenes.preflight`; it was readiness at the time of the run, not current availability |
| 1. Shared memory | Reveal baseline membership and recorded formulas; select one evidence source if loaded | Summary counts plus matching memory/journal data; counts alone cannot create nodes |
| 2. A supported answer | Query card beside its support graph; result and certificate badges; release decision below | Reader summary/journal/query response; distinguish reported proof status from independently rerun verification |
| 3. Missing knowledge | `docs_signed` chapter with `Unknown` and `Abstained`; quiet neutral/ochre treatment | Uncertain scene/event; no fabricated negative premise or persisted decision |
| 4. A conflicting observation | Writer request → access denial; separate operator submission → quarantined proposal | Writer events plus summary quarantine outcome; depict the two different roles explicitly |
| 5. Correct the premise | Before/after revision comparison; removed assertion ghosted on the historical side, replacement on corrected side | Correction revision, parent memory, current memory, and impact response; dynamic IDs |
| 6. Recheck before acting | Old query remains valid for its old snapshot; conflict event if present; new query/result/hold decision | Resume events/summary; if no stale attempt occurred, omit that substep rather than fabricate it |
| 7. Check the certificate | Two plain result rows: original CLI exit 0, modified CLI exit 1 | Verify summary. Caption `Recorded independent checker results`; terminal cutaway supplies the actual command output |
| 8. Why a graph | Highlight membership/provenance/support and affected result; expandable Cypher and recorded row counts | Graph scene plus API projection; if skipped, show `Graph query scene not recorded` |

The chapter strip is narrative organization, not a claim that every model followed an identical call sequence. Tool lists show actual events with a concise outcome and a disclosure for details. Avoid a chat-style stream or invented internal reasoning. A model-supplied rationale is labelled as such and is never treated as proof.

### 6.4 Queries and proof support

Keep the current query form and error handling. Enhance the result with three independent fields: Logical result · Certificate status · Revision context. Example: `Follows from memory · Certificate verified by service · Historical revision`. Use existing accurate result copy where possible.

Show supported assertions in the shared GraphCanvas. `USES_PREMISE` is a dependency relationship, not a formal proof-step derivation. For UNKNOWN, do not highlight a decisive proof path. For full-snapshot dependency basis, label `Snapshot dependency`, not `Checked proof support`. Offer certificate download only when available; do not implement a second checker in JavaScript.

If query submission is in flight and the selected revision/workspace changes, cancel or discard its UI result for the new selection. Every result render checks workspace, revision, and query identity. A user-initiated query can still POST through the existing form; selecting a graph node or replay chapter must never submit one.

### 6.5 History and impact comparison

Choose the selected revision's actual parent, not merely the previous loaded list item. Read both immutable snapshots, compute ID-set differences, and display Added / Removed / Unchanged. A semantic replacement is two membership changes unless an explicit record supports the replacement relationship. Do not match by nearly equal labels.

Maintain common node positions across the two revisions. Show a short impact table with query ID, original revision, dependency basis, and changed support. Wording: `Affected result — recheck at the new revision`. An affected result is not automatically false, and a historical certificate does not become mathematically invalid for its original premises.

The impact API covers the selected revision's immediate parent results according to its implementation. Do not call it an exhaustive transitive impact analysis across all history. Show loaded count versus `total_count`; expose `Load more` when `next_cursor` exists. Quarantine lists have a bound without a cursor; at the bound, say `Showing up to 50 proposals` instead of suggesting a global total.

## 7. Graph projection and algorithms

Use deterministic SVG with HTML/SVG-accessible controls, not a physics engine. This demo has a small graph and needs readable labels and stable composition. Reconsider a layout dependency only if actual supported data demonstrates a need; do not introduce a new dependency preemptively.

### Data model

Create pure view-model functions before React components. Suggested types:

```ts
type SourceKind = "api" | "recorded-artifact" | "derived";
type GraphNode = {
  key: string; // namespaced stable presentation ID; never mislabel as a DB ID
  kind: "revision" | "assertion" | "formula" | "evidence" | "query" | "proposal" | "decision";
  label: string;
  recordId?: string;
  revisionId?: string;
  source: SourceKind;
};
type GraphEdge = {
  key: string; from: string; to: string;
  relation: "INCLUDES" | "ENCODES" | "SUPPORTED_BY" | "USES_PREMISE" | "AT_REVISION" | "BASED_ON" | "property-reference";
  source: SourceKind;
};
type GraphModel = { nodes: GraphNode[]; edges: GraphEdge[]; warnings: string[] };
```

These are frontend contracts, not backend changes. Add explicit provenance/detail references in implementation as needed. A source tag on an edge means the record used to project that edge, not a direct graph dump.

### Projection rules

- Revision/assertion/evidence IDs come from their matching records. Deduplicate evidence by ID; conflicting content for one ID is a data warning.
- The API does not expose a database Formula node ID in the normalized memory type. Use a namespaced presentation key such as `formula:<assertion ID>` and disclose it as a projection; do not claim it is the stored formula hash or globally deduplicate by a homegrown hash.
- Default folded formulas keep the graph compact. A derived AST view, if later implemented, uses distinct styling and the label `Formula structure`; it must not impersonate stored nodes/edges.
- Workspace head and revision parent are ID properties. If drawn, use a dashed property-reference edge with that label; never create fictitious `HEAD` or `PREVIOUS` stored edges.
- Query support must be joined by exact assertion IDs against the query's own snapshot. If an assertion is unavailable, show unresolved support explicitly, not an edge to a same-looking assertion in the current revision.
- Draw persisted decision relations only with an explicit persisted decision record/event. Imported receipt data remains labelled recorded. No external release execution is implied by PROCEED.
- Quarantined submissions remain outside the accepted membership boundary.

### Layout and interaction

Build node/edge maps and adjacency lists in O(V+E). Sort within fixed semantic columns by stable kind/ID, O(V log V), then allocate deterministic positions. Keep query/decision on one side, revision/assertions central, evidence/formula details on the other. Avoid treating all domain relationships as a DAG to be topologically sorted: cross-links and cycles may exist in a general projection. This layout uses semantic ranks and explicit edge routes instead.

The default mode displays the selected query's support or the selected revision's accepted assertions, with formulas folded. Use SVG cubic paths behind nodes, directional arrows, and selected-edge labels. Place full edge names in a legend/inspector instead of labelling every crossing.

Select via click or keyboard. Hover is an enhancement, never the only access path. Provide Fit, +/− zoom and Reset; pointer drag pans only from the background, and node activation remains a click. Do not hijack normal page scrolling. Retain selection while filtering and announce when it becomes hidden. Provide an equivalent relationship list so keyboard and screen-reader users can reach every displayed record without traversing hundreds of SVG shapes.

Memoize graph construction by immutable snapshot/query identity, separate selection from layout state, and preserve coordinates during highlighting. Neighborhood focus uses adjacency traversal O(V+E); revision diff uses sets O(A+B). No all-pairs comparison or per-frame React state updates. Pan/zoom may use a requestAnimationFrame-backed transform.

Initial display budget: 120 nodes and 240 edges. Above this, show an explicitly bounded focused subgraph with counts and a list/search path to all loaded records. Never silently drop data or pretend the subset is the full graph. Demo acceptance requires all canonical facts and relevant support to fit without clipping at 1440px. Performance targets: graph transform/layout under 50ms for the display budget on the test machine and selection response under 100ms; measure before reporting these as achieved.

## 8. Live observation, caching, and correctness

1. Give each authenticated connection an opaque in-memory session key. Include it with workspace/revision in query keys; never put the bearer token itself in a cache key. Clear protected queries and imported enrichment on disconnect or identity/workspace changes.
2. Poll workspace head and readiness every 3 seconds while visible. Poll quarantine every 5 seconds while visible because quarantine can change without advancing the head. Pause background polling, abort obsolete fetches, deduplicate through TanStack Query, and use bounded error backoff. Avoid a second custom polling loop.
3. Fetch history on connection, head change, and explicit refresh. Cache immutable memory by workspace/session/revision; do not reload every historical snapshot on each tick.
4. Follow head is on for a fresh live observer with no explicit historical selection. Choosing a revision disables it. Re-enabling follows the latest observed head. In replay mode, a chapter pins its recorded revision; it never changes when the live head advances.
5. When head changes, first load the new snapshot and corresponding history. Commit the visible heading/graph together after validating the response revision. Keep the previous snapshot under its previous label with a pending indicator until then. Handle rapid successive heads with cancellation/identity checks.
6. A changed head triggers impact loading only for the selected correction/history view. Impact can change if additional queries are created against its parent, so use explicit refresh or bounded visible polling while that impact view is active. Do not treat impact lists as immutable solely because their revision ID is immutable.
7. Add frontend `getQueryResult(workspaceId, queryId, options)` for the existing route. Extend history pagination with `before_sequence` and impact pagination with `before`; deduplicate pages and reset cursor state on context changes.
8. Current means current as of the last successful read, not an eternal guarantee. Read-query responses preserve their original observed head. Show a separate comparison with the latest observed workspace head rather than rewriting their historical fields.
9. Imported runs can read historical snapshots/results only after validating the workspace match. Check revision, query IDs, and knowledge hash when both sources provide one. Source disagreement stops enrichment and displays a mismatch; it does not silently replace imported outcomes.
10. Use semantic empty/error states: `No accepted assertions`, `No affected results returned`, `Detail not included in this recording`, `Revision unavailable`, `Authentication expired`, `Service unavailable`. These states must never fall through to development fixtures.

## 9. Suggested file plan and implementation packets

New filenames below are proposed; reuse small existing components where appropriate. Keep `LiveApp.tsx` as orchestration rather than adding another several hundred lines to it.

| Packet | Files / responsibility | Completion gate |
| --- | --- | --- |
| P0 — Baseline and contracts | Read repository rules; task log; inspect latest main; define graph/run types in `src/visualization/types.ts` and `src/run/types.ts` | Agreed types, baseline checks, no backend changes |
| P1 — Pure adapters | `src/visualization/project.ts`, `layout.ts`, `diff.ts`; `src/run/parse.ts`, `normalize.ts`; corresponding `.test.ts` | Valid/missing/hostile imports, dynamic revisions, exact support joins, deterministic layout tested |
| P2 — Graph and inspector | `src/components/GraphCanvas.tsx`, `GraphLegend.tsx`, `RecordInspector.tsx`; scoped visualization CSS | Static valid fixtures at desktop/narrow sizes; keyboard and reduced-motion paths work |
| P3 — Live integration | `src/live/useWorkspaceObserver.ts`, `MemoryGraphView.tsx`, `HistoryImpactView.tsx`; `api/client.ts`; `LiveApp.tsx` | Head changes, pin/follow, quarantine without head change, read errors, pagination and stale response cases pass |
| P4 — Recorded walkthrough | `src/run/RunImport.tsx`, `RunWalkthrough.tsx`, `RunChapter.tsx`; query detail reader; scoped run CSS | Completed and partial actual-format artifacts render; missing fields honest; replay performs zero POSTs |
| P5 — Navigation and finish | `Shell.tsx`, `model/location.ts` and tests, `FixtureApp.tsx`, `App.tsx` as required; `global.css` | Existing links/forms preserved, source labels visible, focus mode, responsive and browser history work |
| P6 — Verification and recording guide | Extend `e2e/live-query.mjs` or add a focused browser script; sanitized test fixtures; `docs/DEMO.md` additions; own/master logs | Release checks, visual QA, real API rehearsal when available, final handoff |

Use route sections `run`, `memory`, `queries`, and `history`. Preserve existing `/memory` links; name that nav item Memory graph. Run import stays in component/session state. A run URL after reload shows a helpful import prompt because files are not persisted. Add URL chapter/selection fields only with explicit parse/serialize tests; never encode imported JSON or tokens. Choose one integration owner for `Shell`, routing, `LiveApp`, and client contracts.

### Execution sequence for one agent

1. Fetch current main, preserve unrelated work/stashes, create `codex/saqlain/frontend-visualization` or the acting person's equivalent branch. Read the latest handoffs. Record exact scope and exclusions.
2. Re-run baseline checks. Investigate failures before UI changes. A passing suite is not a claim that all code is error-free.
3. Implement P1 with small hand-authored sanitized fixtures matching real producer shapes. Freeze the view-model props before component work.
4. Implement P2 and memory graph P3. Review in the browser before starting elaborate replay UI. This is the first usable milestone.
5. Implement P4, first with summary-only input and missing-detail states, then journals and API enrichment. Check that imported events are not accidentally executed.
6. Complete P5, history comparison, and scoped visual polish. Preserve existing query/mutation semantics.
7. Execute P6. Fix correctness and readability before animation. Commit explicit task paths, integrate origin/main, rerun affected checks, and push directly when implementation is authorized.

### Optional split if two agents are assigned later

Saqlain can own data contracts, parsing, live observer, API-read adapters, tests, and final integration. Mahavir can own GraphCanvas, inspector, chapter presentation, and visual CSS against the frozen props. Each uses a separate checkout and separate task branch. The presentation agent must not edit shared routing/client/LiveApp files while the integration owner is editing them. No package or lockfile changes without coordination. Submit typed components with synthetic fixtures; integrate in P1 → P2/P4 → P3/P5 order. This is a proposed allocation, not a claim that either agent has started it.

### Timebox and priority cuts

Budget roughly 4–6 focused engineering hours for the core experience plus 1–2 hours of verification/recording preparation; this is a planning estimate, not a delivery promise. At this hackathon stage, protect at least two hours before the deadline for video upload and submission checks.

Must ship: graph with correct provenance; revision selection/follow; support overlay; correction impact; summary/journal walkthrough with manual chapters; honest error/mode states; focus mode; verification. Defer auto-play, automatic file watching, formula AST trees, large-graph layout, graphical certificate derivation, export animations, new dashboards, and dark mode. If time compresses, record terminal cutaways for missing detail rather than simulate it. A static layout with correct selection is sufficient; keep zoom/pan minimal if Fit plus readable scrolling already solves the demo.

## 10. Validation matrix

### Pure model and contract tests

- Same input yields stable positions and IDs; all displayed edges have resolvable endpoints or an explicit missing-record warning.
- Removed/replaced membership preserves old snapshots; shared assertion/evidence identities stay consistent.
- Query support cannot attach to another revision/workspace's assertions.
- UNKNOWN and SOLVER_UNKNOWN stay distinct; proof status and logical status remain independent.
- Writer-denied, operator-quarantined, committed correction, stale-decision conflict, and resumed result map from actual producer fields.
- Repeated reader events after resume are not duplicated; mode metadata is not applied to the wrong chapter; partial/mixed/fallback runs are labelled correctly.
- Summary counts do not generate fictitious nodes; missing evidence, query formula, or checker output stays missing.
- Import rejects bad JSON, duplicate/conflicting files, wrong workspace, oversized data, extreme formula depth, and unsupported field types. Rendered text cannot inject markup.
- API path/query serialization covers query IDs, `before_sequence`, and impact `before`. Pagination retains all loaded items once.

### Browser checks

Use the existing synthetic harness for deterministic integration. Extend it only with synthetic scenarios needed for browser testing; no production endpoint changes. Test graph selection/details, keyboard/list equivalence, revision pin/follow, quarantine refresh without a new head, disconnect/reconnect isolation, rapid revision changes, history comparison, malformed imports, partial runs, and a full nine-chapter import. Capture network requests to assert replay/chapter/graph interactions cause **zero mutation requests**.

Cover 1440×900, 1920×1080, 1024px, and 390px widths, plus 200% zoom. Verify no clipped graph labels, overlapping toolbars, hidden source labels, console errors, focus traps, or interaction-blocking animation. Check reduced motion, visible keyboard focus, and a relationship list usable without a pointer. Inspect screenshots manually; do not infer visual quality from build success.

### Existing regression gate

From the repo root, run the commands already used by this repository:

```text
uv run --locked pytest -q
uv run --locked python -m unittest discover -s tests/proofcheck -q
uv run --locked python -m compileall -q src tests packages/proofcheck/src scripts agents evaluation
npm --prefix apps/web run typecheck
npm --prefix apps/web test
npm --prefix apps/web run build
uv run --locked python -m evaluation.run --suite acceptance --output .artifacts/frontend-acceptance
git diff --check
```

`scripts/verify_release.sh` is the existing Bash aggregate, including dependency installation. Use it where Bash/tooling are configured; PowerShell can execute the individual commands above with exit-code checks. For browser smoke, inspect `apps/web/e2e/harness.py` and `apps/web/e2e/live-query.mjs`; set the actual Chrome path and preview origin for the machine. Record commands and results, not just "tested everything".

### Real-service rehearsal gate

When FalkorDB/API are available, connect the browser to that API explicitly (`MEMOPOPS_API_ORIGIN`; Vite defaults to the synthetic harness on 8010, while the demo runner defaults to 8001). Verify memory, query reload, quarantine, correction, impact, and historical selection from the real service. Stop and restart only frontend development services if needed; the visualization task does not require destructive resets.

Use one complete run's artifacts for recording. The existing runner's `--reset` deletes and reseeds `workspace_demo`; it is a deliberate rehearsal operation and must never be invoked by merely opening the UI. Do not reset between recording the run and API-enriching its historical graph. Do not describe an in-memory browser harness as FalkorDB persistence evidence.

## 11. Recording storyboard

Target about four minutes, subject to the actual submission uploader's constraints. Record at 1920×1080 and verify the exported video at normal playback size. Use the same completed take for terminal cutaways and UI walkthrough. Keep labels legible and pause briefly on outcome changes.

| Time | Shot | Narration goal |
| --- | --- | --- |
| 0:00–0:20 | Memory graph, baseline selected | State the concrete problem: agents can act on memory that has changed. Introduce revision-bound shared memory. |
| 0:20–0:50 | Select one assertion/evidence; show source path | Explain what is accepted, where it came from, and what FalkorDB stores. |
| 0:50–1:20 | Reader chapter, support overlay and PROCEED receipt | Show an answer backed by explicit premises and a certificate status. |
| 1:20–1:35 | Unknown chapter | Missing information leads to abstention rather than a fabricated answer. |
| 1:35–2:00 | Writer/operator quarantine chapter | Show role separation and why contradictory memory was not activated. |
| 2:00–2:45 | Revision comparison and impact | Replace a premise; highlight affected historical support; preserve the old snapshot. This is the main visual moment. |
| 2:45–3:15 | Resumed reader and new result | Show the actual stale conflict if recorded, reread/recheck, and resulting BLOCK receipt. |
| 3:15–3:40 | Terminal checker cutaway, then verification chapter | Show real original/tampered checker exits and their labelled summary. |
| 3:40–4:00 | Final graph + brief repository/local setup reference | Explain why graph dependencies matter and where judges can reproduce the project. |

A recorded scene uses the label `Recorded run` throughout. Keep actual live-model/scripted/fallback disclosure visible. A short terminal cutaway establishes the executed run; the browser explains its records. Do not claim database restart, all-live model execution, or actual software deployment from these scenes unless separately demonstrated.

Recording preparation: select a successful take with all required outcomes, review imports for private content, set the correct API origin, confirm historical revisions still exist, close token/error-detail popovers, fit the graph, enable focus mode, verify reduced background movement, and perform one full narration rehearsal. Keep repository/local setup instructions accessible after recording. App deployment remains out of scope.

## 12. Final acceptance and implementation handoff prompt

The work is ready only when the complete demo story is understandable from the visual interface, every state has a real source, old/new revisions cannot be confused, graph interactions are readable and accessible, existing backend/terminal behavior is preserved, and verification results are recorded. A beautiful screen with fabricated activity fails this gate.

Copy this prompt to the implementing agent:

> Implement `docs/plan/FRONTEND_VISUALIZATION_PLAN.md` against the latest main. First read AGENTS.md, current handoffs, and the actual demo/API producers. Work for the human assigned in your chat and create the matching task branch. Keep backend, solver, checker, graph schema, agent logic, and terminal runner unchanged. Build the live memory graph and explicitly labelled recorded-run walkthrough in the existing React app. Follow the packet order and provenance rules, preserve old links/forms, and use runtime revisions. Run the specified checks, inspect the UI in a browser, and report separately what was tested with synthetic data versus real FalkorDB. Update your own log and the concise master log. When implementation is authorized, commit only scoped files and push directly to main following the integration rules; do not create a PR or deploy the app.

The user subsequently authorized implementation. Follow the frontend guide for the delivered experience; optional enhancements and real-service recording checks remain subject to the stated scope and evidence requirements.
