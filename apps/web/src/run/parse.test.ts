import { describe, expect, it } from "vitest"
import { chapterEvents, chapterQuery, parseFormula, parseRunFiles, recordedMemory } from "./parse"

function files() {
  const decision = {
    query_id: "q1",
    revision_id: "baseline-dynamic",
    result: "PROVED",
    proof_status: "VERIFIED",
    choice: "ship",
  }
  return [
    {
      name: "summary.json",
      content: JSON.stringify({
        workspace_id: "demo",
        take: "test",
        requested_model_mode: "live",
        fallback_used: true,
        baseline_revision_id: "baseline-dynamic",
        scenes: {
          memory: { revision_id: "baseline-dynamic", assertion_count: 1 },
          reader: { decision, mode: "scripted_replay" },
          correction: { revision_id: "new-dynamic" },
        },
      }),
    },
    {
      name: "reader.json",
      content: JSON.stringify({
        workspace_id: "demo",
        mode: "live_model",
        events: [
          {
            tool: "inspect_memory",
            revision_id: "baseline-dynamic",
            atom_ids: ["ready"],
            assertions: [{ id: "a", formula: { op: "atom", id: "ready" } }],
          },
          { tool: "query_conclusion", ...decision, support_assertion_ids: ["a"] },
          { tool: "record_decision", ...decision, outcome: "PROCEED", persisted: true },
          {
            tool: "record_decision",
            code: "REVISION_CONFLICT",
            expected_revision_id: "baseline-dynamic",
            head_revision_id: "new-dynamic",
          },
        ],
      }),
    },
  ]
}
describe("recorded run import", () => {
  it("uses actual revision IDs and never creates evidence absent from the journal", () => {
    const run = parseRunFiles(files())
    expect(run.baseline).toBe("baseline-dynamic")
    expect(recordedMemory(run, run.baseline)?.assertions[0].evidence).toEqual([])
    expect(recordedMemory(run, "unrecorded")).toBeNull()
    expect(chapterQuery(run, "reader")?.support_assertion_ids).toEqual(["a"])
  })
  it("maps persisted outcomes and resumed conflicts without fixed event counts", () => {
    const run = parseRunFiles(files())
    expect(chapterEvents(run, "reader").some((e) => e.outcome === "PROCEED")).toBe(true)
    expect(chapterEvents(run, "resume")[0].code).toBe("REVISION_CONFLICT")
    expect(run.scenes.reader.mode).toBe("scripted_replay")
    expect(run.journals["reader.json"].mode).toBe("live_model")
  })
  it("allows partial summary-only runs without fabricating snapshots", () => {
    const run = parseRunFiles(files().slice(0, 1))
    expect(recordedMemory(run, run.baseline)).toBeNull()
    expect(run.warnings.join()).toContain("missing")
    expect(run.scenes.verify).toBeUndefined()
  })
  it("rejects malformed, duplicate and mismatched-workspace files", () => {
    expect(() => parseRunFiles([{ name: "summary.json", content: "{" }])).toThrow("Invalid JSON")
    expect(() => parseRunFiles([...files(), files()[0]])).toThrow("Duplicate")
    const wrong = files()
    wrong[1].content = wrong[1].content.replace('"workspace_id":"demo"', '"workspace_id":"other"')
    expect(() => parseRunFiles(wrong)).toThrow("Workspace mismatch")
  })
  it("rejects conflicting immutable query and assertion records", () => {
    const wrong = files(),
      journal = JSON.parse(wrong[1].content)
    journal.events.push({
      tool: "query_conclusion",
      query_id: "q1",
      revision_id: "other",
      result: "PROVED",
      proof_status: "VERIFIED",
    })
    wrong[1].content = JSON.stringify(journal)
    expect(() => parseRunFiles(wrong)).toThrow("conflicting revisions")
    journal.events.pop()
    journal.events.push({
      tool: "inspect_memory",
      revision_id: "baseline-dynamic",
      assertions: [{ id: "a", formula: { op: "atom", id: "different" } }],
    })
    wrong[1].content = JSON.stringify(journal)
    expect(() => parseRunFiles(wrong)).toThrow("Conflicting assertions")
  })
  it("rejects unsupported result enums and unbounded events/inputs", () => {
    const wrong = files()
    wrong[1].content = wrong[1].content.replace('"PROVED"', '"probably"')
    expect(() => parseRunFiles(wrong)).toThrow("Unsupported")
    expect(() =>
      parseRunFiles([{ name: "summary.json", content: "x".repeat(5 * 1024 * 1024 + 1) }]),
    ).toThrow("limit")
    expect(() =>
      parseRunFiles(Array.from({ length: 13 }, (_, i) => ({ name: `${i}.txt`, content: "" }))),
    ).toThrow("12")
  })
  it("bounds recursive formulas and rejects arbitrary operators", () => {
    expect(() => parseFormula({ op: "execute", args: [] })).toThrow("invalid Boolean")
    let formula: unknown = { op: "atom", id: "p" }
    for (let i = 0; i < 66; i++) formula = { op: "not", arg: formula }
    expect(() => parseFormula(formula)).toThrow("depth")
  })
  it("rejects a changed logical outcome for the same query", () => {
    const wrong = files(),
      journal = JSON.parse(wrong[1].content)
    journal.events.push({
      tool: "query_conclusion",
      query_id: "q1",
      revision_id: "baseline-dynamic",
      result: "REFUTED",
      proof_status: "VERIFIED",
    })
    wrong[1].content = JSON.stringify(journal)
    expect(() => parseRunFiles(wrong)).toThrow("Conflicting outcomes")
  })
})
