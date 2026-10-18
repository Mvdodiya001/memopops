# Visual memory workspace

The frontend provides a live memory graph, query-support graphs, revision comparison, and a recorded-run walkthrough. API, database schema, agent behavior, solver, checker, and terminal demo contracts remain unchanged.

## Start

Start the database/API using [local setup](submission/LOCAL_SETUP.md), then point Vite at that API. For the demo's usual port, in PowerShell:

```powershell
$env:MEMOPOPS_API_ORIGIN = 'http://127.0.0.1:8001'
npm --prefix apps/web run dev
```

Open `http://127.0.0.1:5173` and connect with a workspace reader token. Leave Revision empty to discover/follow the head, or enter an ID to pin history. Disconnect clears the protected query cache. Tokens remain in memory.

Vite still defaults to port 8010 for the synthetic test harness. Set the origin explicitly when recording against the real service.

## Live views

- **Memory graph:** select assertions/evidence, expand formula views, or switch to List for the existing memory/operator form. Derived formula keys are not database Formula IDs. Browse all records provides keyboard inspection and search.
- **Show support:** open an existing query ID from the terminal or impact results. There is no query-list endpoint or feed of all agent calls. Only matching workspace/revision support is overlaid.
- **Follow current head:** reads the next snapshot before changing the visible revision. Selecting a revision pins it. Refresh checks workspace, memory, quarantine, and history. Hidden-page polling pauses; failures back off.
- **Queries:** retain existing submission, decision and certificate controls, with a new support graph. Results display the formula actually submitted, even after the input changes.
- **History:** compares a revision with its actual parent, then lists affected stored query dependencies with pagination. An affected result needs rechecking; a historical certificate remains bound to its original premises.

Relationships are projections of available records, not a proof-step execution animation. Quarantine is outside accepted membership. Impact covers the selected revision's immediate parent according to the existing service semantics.

## Recorded walkthrough

1. Complete a take using the [demo runner](DEMO.md). Keep its artifacts and historical database revisions; resetting the graph afterward removes history needed for API enrichment. The UI never resets it.
2. Open Walkthrough or `/run`. Select `summary.json`, `reader.json`, `reader-docs.json`, and `writer.json` from one take. Optionally include `graph-queries.cypher`, certificates, or the Gemini transcript. The main interface displays allowlisted summary/journal fields, not arbitrary transcript text.
3. Navigate nine chapters manually with buttons, or left/right arrows outside input controls. Missing scenes stay labelled Not recorded.
4. Use Focus mode for recording. With a run loaded, it hides navigation, inspector and import controls while retaining mode, revision and Recorded run labels. Exit focus to replace/clear files.

Imports stay in memory and are not uploaded or put in URLs. Reloading requires reimport. Bounds: 12 files, 5 MiB each, 20 MiB total, 2,000 events. Invalid imports preserve the previous valid run. Consistency checks reject mismatched workspaces, revisions and immutable records; they do not cryptographically authenticate a run.

The final reader journal includes both initial/resumed steps. Chapters use actual query/revision IDs, not fixed event counts. Requested live mode is distinct from actual scene mode. Fallback is disclosed. Unknown can lead to local abstention without a persisted Decision node. Checker exits are recorded reports; the browser does not independently recheck the certificate.

Offline journals contain formulas but omit evidence excerpts. To enrich a run, connect through Memory graph to the matching API workspace, then return to Walkthrough. Only matching historical details are used. The graph chapter displays actual recorded Cypher/query row counts; skipped runs remain labelled skipped. Row counts are not graph node totals.

Observer and walkthrough interactions issue reads only. Existing explicit query/mutation forms retain their behavior. Choose 1920×1080 and Focus mode for the video; the [full storyboard](plan/FRONTEND_VISUALIZATION_PLAN.md) covers accepted memory, support, uncertainty, quarantine, correction, resumed decisions, and terminal checker cutaways. On narrow screens, use Browse all records instead of the graph canvas.

## Verification

Run web typecheck, tests and build normally. The extended browser test uses synthetic in-memory data and actual scripted DemoRunner artifact formats. It never connects to FalkorDB or reads production credentials.

Start the isolated harness from the repo root:

```text
uv run --locked python -m apps.web.e2e.visual_harness
```

In separate terminals, with the Vite API origin set to `http://127.0.0.1:8010`, run:

```text
npm --prefix apps/web run build
npm --prefix apps/web run preview
node apps/web/e2e/visualization.mjs
```

Set `CHROME_PATH` to the Chrome executable if needed. Run the browser test only against this harness: it deliberately submits synthetic quarantine/correction requests there. Stop the harness and preview afterward. Screenshots, scripted artifacts and `browser-report.json` go under ignored `.artifacts/frontend-browser`.

Coverage includes query support, quarantine without a new head, head following, pinned history, impact, every recorded chapter, malformed-file recovery, responsive focus, reduced motion, browser exceptions, and zero replay mutation requests. Real FalkorDB checks must be reported separately.
