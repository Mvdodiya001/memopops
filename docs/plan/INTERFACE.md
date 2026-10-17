# Interface specification

Owner: Mahavir. This is a web product with Apple-inspired restraint and hierarchy, not a native Apple UI clone. The values below are our web design choices; they are not copied platform system-color constants. Apple layout, color and accessibility guidance informs the principles [R12–R14].

## 1. Visual intent

The product should feel like a carefully edited desktop tool: readable typography, aligned content, quiet separators, clear selection, and a useful inspector. The user's attention belongs on memory, evidence and changes. Avoid neon accents, gradients, glowing graphs, decorative AI sparkles, oversized hero slogans, glass on every surface, and grids of empty metric cards.

Working display name: **memopops**. Subtitle inside the workspace: **Shared memory, with reasons.** No unverified claim such as “zero hallucinations” or “mathematically true memory.”

## 2. Layout and visual tokens

| Token | Initial choice |
| --- | --- |
| Page | `#F5F5F7` soft neutral |
| Main content | `#FFFFFF` |
| Sidebar/hover | `#EFEFF2` / `#E8E8ED` |
| Primary text | `#1D1D1F` |
| Secondary text | `#5C5C63` |
| Quiet border | `#D9D9DE`; decoration only, not the sole control boundary |
| Primary action/focus | `#2457A7` restrained blue |
| Positive text | `#24633C` on `#EAF3ED` |
| Conflict text | `#8F2929` on `#F9ECEC` |
| Pending/stale text | `#77520C` on `#FAF2DE` |
| Unknown | Neutral text + question icon, never colored like an error |
| Typeface | `-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif` |
| Formula/code | System monospace stack; no font download required |
| Type scale | 28/34 page title; 18/26 section; 15/22 body; 13/18 metadata; avoid tiny gray text |
| Spacing | 4, 8, 12, 16, 24, 32, 48 px |
| Corners | 8 px controls, 12 px panels; consistent nested radii |
| Shadows | One subtle sheet/popover shadow; flat content panes |
| Motion | 120–180 ms state transitions; reduced-motion removes nonessential animation |

Check actual contrast in rendered states; a token list is not an accessibility audit. Target ≥4.5:1 normal text, ≥3:1 large text and essential control boundaries. Use labels/icons alongside color [R14,R15]. Keep a visible 2 px focus ring with offset. Comfortable controls are about 40–44 px high, larger on touch; dense table rows can be 48 px.

Desktop at 1440 px: 208 px navigation, fluid central content (minimum about 520 px), 352 px inspector, 24 px content padding. Header around 56 px. At 1000–1199 px collapse inspector into a side sheet. At <768 px use one column with navigation menu and full-width inspector route. Horizontal scrolling belongs only inside formula/code regions, not the whole page.

Use CSS grid `208px minmax(0, 1fr) 352px` only when viewport permits. Test at 1440×900, 1024×768, 390×844 and 200% zoom. Let rows grow for long evidence. No fixed-height text clipping.

## 3. Primary screen

```text
┌──────────────┬────────────────────────────────┬──────────────────────┐
│ memopops     │ Release demo-42       Revision 2│ Inspector            │
│              │                                │                      │
│ Memory       │ Ask about this memory          │ Release readiness    │
│ Queries      │ [release_ready        ] [Check]│ Refuted              │
│ History      │                                │ Proof verified       │
│              │ Memories  4 accepted           │                      │
│              │ API v2 is deployed             │ Why                  │
│ Workspace    │ Integration tests failed       │ The accepted failure │
│ Demo-42      │ Passing tests allow readiness  │ rule rules it out.   │
│              │ Failed tests block readiness   │                      │
│ Connected    │                                │ Evidence · Proof     │
└──────────────┴────────────────────────────────┴──────────────────────┘
```

This is an information-layout sketch, not a pixel-accurate implementation. Every displayed assertion comes from the selected revision. Main navigation has three useful destinations, not ten placeholders.

## 4. Screen behavior

### Memory

- Header: workspace name, revision selector and connection state. Show current versus historical explicitly. Historical mode is read-only.
- Main list: human assertion label, small formula, source/actor and accepted-at revision. Keep one main action “Add memory” for authorized writers.
- Inspector: selected assertion's meaning, evidence, source date, actor, revision membership and supersession history. Do not collapse distinct evidence confidence into a truth score.
- Query control: choose a registered atom or structured formula builder. Default simple atom query; advanced nested formula editing behind disclosure. No mandatory chat transcript.

### Query result

Show the answer label first, a one-sentence explanation second, then the proof assurance and revision. Copy choices:

| API state | Main wording | Supporting wording |
| --- | --- | --- |
| PROVED / VERIFIED | “Follows from memory” | “Proof verified · Revision 1” |
| REFUTED / VERIFIED | “Ruled out by memory” | “The accepted premises establish its negation.” |
| UNKNOWN | “Not established” | “Both outcomes remain possible under this memory.” |
| INCONSISTENT_MEMORY | “Memory needs repair” | “Accepted premises conflict. Conclusions are withheld.” |
| SOLVER_UNKNOWN | “Check could not finish” | “No conclusion was established within the limit.” |
| BUDGET_EXCEEDED certificate | Logical result plus “Solver checked” | “A complete certificate was not generated within the limit.” |
| HISTORICAL | Persistent “Earlier revision” label | “Check against current memory” action. |

Do not show PROVED as a green universal truth badge. Avoid technical identifiers in the primary sentence. Put formal AST/CNF/solver version in a Details disclosure.

The proof view starts with a readable ordered explanation. Optional graph highlights one selected step and its parents; no force-layout animation. Show ≤40 nodes by default, with a full accessible step table and certificate download. Display real stored derivation; LLM-generated prose cannot replace steps.

### Conflict and correction

Submitting NOT tests_pass while tests_pass is accepted opens a review sheet: proposed assertion, conflicting accepted assertion, their evidence and expected revision. Actions: “Keep current memory” or authorized “Replace this assertion”. Do not offer a one-click “force accept” bypass.

Before replacement, show a concise preview: which assertion leaves, which enters, and affected prior conclusions. The backend validates the whole replacement again. Only a confirmed successful commit changes displayed accepted memory. A 409 preserves the user's input, refreshes the revision, and asks them to review the change before resubmitting.

### History and agent activity

History rows show revision, actor, change summary and time. Selecting r1/r2 displays a real added/removed assertion diff. Old proofs stay accessible. Event rows identify Writer, Reader and Operator with tool action and outcome; display “Scripted replay” or “Live model” mode accurately. Do not animate fabricated agents “thinking.”

## 5. State management and interaction

- URL includes workspace, revision and selected object so reload/share preserves context.
- TanStack Query keys include workspace and revision. Abort or ignore responses for outdated selections; never display r1 data under an r2 heading.
- Small skeletons mirror actual content only after noticeable delay. Buttons show “Checking…”/“Saving…” with repeat submission prevented.
- Read errors show actionable Retry; no data is different from failed loading. Offline state keeps visible historical data labeled, disables writes and does not claim current verification.
- Use native button/input/table semantics; labels are visible. Accessible dialogs trap focus and restore it on close. Escape dismisses sheets; keyboard activates all actions. Avoid unsolicited global shortcuts.
- Error messages preserve form input. Long formulas/evidence wrap or scroll locally. Copy/download has clear confirmation.
- No polling when the page is hidden. Initially poll workspace head/events every 3 seconds while a demo is active; manually refresh otherwise. SSE is optional after correctness.

## 6. UI acceptance checklist

Every API result, proof status and freshness state has a distinct display. All primary actions work using keyboard alone. Contrast checks pass across text/status/disabled/focus states. At 200% zoom content reflows without hidden controls. Narrow view retains query result, evidence and revision context. Reduced-motion preference works. Loading/error/empty/long-content screens are visually inspected. A 409 and stale response are exercised against the real API. No dev fixtures ship as an automatic production fallback.

The final aesthetic review asks: Is the important conclusion obvious? Is evidence one interaction away? Do spacing and alignment make groups clear? Is any decoration competing with the decision? Remove it if so.
