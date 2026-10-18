import { describe, expect, it } from "vitest"
import type { MemoryDocument } from "../api/types"
import {
  boundedGraph,
  diffMemory,
  layoutGraph,
  matchesRecordedMemory,
  projectMemory,
  type SupportQuery,
} from "./graph"

const memory: MemoryDocument = {
  workspace_id: "demo",
  revision_id: "dynamic-head",
  knowledge_hash: "hash",
  semantics_version: "boolean-v1",
  atoms: [],
  assertions: [
    {
      id: "a",
      formula: { op: "atom", id: "ready" },
      evidence: [
        {
          id: "e",
          uri: "fixture://source",
          excerpt: "Synthetic source",
          observed_at: "2026-10-18T00:00:00Z",
        },
      ],
    },
  ],
}
const query: SupportQuery = {
  workspace_id: "demo",
  query_id: "q",
  revision_id: "dynamic-head",
  result: "PROVED",
  proof_status: "VERIFIED",
  support_assertion_ids: ["a"],
}
describe("graph projections", () => {
  it("shows persisted decision receipts but never invents a node for local abstention", () => {
    const decision = {
      decision_id: "d",
      query_id: "q",
      revision_id: memory.revision_id,
      outcome: "PROCEED",
      persisted: true,
    }
    const graph = projectMemory(memory, { query, decision })
    expect(graph.edges.find((e) => e.from === "decision:d" && e.relation === "BASED_ON")?.to).toBe(
      "query:q",
    )
    expect(
      projectMemory(memory, { query, decision: { ...decision, persisted: false } }).nodes.some(
        (n) => n.kind === "decision",
      ),
    ).toBe(false)
  })
  it("rejects conflicting API enrichment and tolerates JSON key order", () => {
    const reordered = JSON.parse(JSON.stringify(memory)) as MemoryDocument
    reordered.assertions[0].formula = { id: "ready", op: "atom" }
    expect(matchesRecordedMemory(reordered, memory, "demo", "dynamic-head")).toBe(true)
    expect(
      matchesRecordedMemory(
        { ...memory, knowledge_hash: "changed" },
        memory,
        "demo",
        "dynamic-head",
      ),
    ).toBe(false)
    expect(matchesRecordedMemory(memory, memory, "other", "dynamic-head")).toBe(false)
    expect(matchesRecordedMemory(memory, memory, "demo", "old")).toBe(false)
  })
  it("projects real memberships and provenance without invented operator nodes", () => {
    const graph = projectMemory(memory)
    expect(graph.edges.map((e) => e.relation)).toEqual(["INCLUDES", "SUPPORTED_BY"])
    expect(graph.nodes.map((n) => n.recordId)).toEqual(["dynamic-head", "a", "e"])
  })
  it("joins exact query support and rejects another tenant or revision", () => {
    expect(projectMemory(memory, { query }).edges.some((e) => e.relation === "USES_PREMISE")).toBe(
      true,
    )
    for (const patch of [{ workspace_id: "other" }, { revision_id: "old" }]) {
      const graph = projectMemory(memory, { query: { ...query, ...patch } })
      expect(graph.edges.some((e) => e.relation === "USES_PREMISE")).toBe(false)
      expect(graph.warnings).toHaveLength(1)
    }
  })
  it("retains missing support as a warning instead of substituting a node", () => {
    const graph = projectMemory(memory, {
      query: { ...query, support_assertion_ids: ["unavailable"] },
    })
    expect(graph.warnings[0]).toContain("unavailable")
    expect(graph.edges.every((e) => graph.nodes.some((n) => n.key === e.to))).toBe(true)
  })
  it("keeps quarantine outside accepted membership and formula IDs clearly derived", () => {
    const graph = projectMemory(memory, {
      formulas: true,
      proposals: [
        {
          proposal_id: "p",
          base_revision_id: memory.revision_id,
          status: "QUARANTINED",
          reason: "Conflict",
        },
      ],
    })
    expect(graph.nodes.find((n) => n.kind === "formula")?.source).toBe("derived")
    expect(graph.nodes.find((n) => n.kind === "formula")?.recordId).toBeUndefined()
    expect(graph.edges.find((e) => e.from === "proposal:p")?.relation).toBe("BASED_ON")
    expect(graph.edges.some((e) => e.to === "proposal:p" && e.relation === "INCLUDES")).toBe(false)
  })
  it("deduplicates shared evidence and warns on conflicting contents", () => {
    const extra = {
      ...memory.assertions[0],
      id: "b",
      evidence: [{ ...memory.assertions[0].evidence[0], excerpt: "Conflicting" }],
    }
    const graph = projectMemory({ ...memory, assertions: [...memory.assertions, extra] })
    expect(graph.nodes.filter((n) => n.kind === "evidence")).toHaveLength(1)
    expect(graph.warnings).toHaveLength(1)
  })
  it("lays out identical inputs deterministically and bounds large scenes", () => {
    const graph = projectMemory({
      ...memory,
      assertions: Array.from({ length: 180 }, (_, i) => ({
        ...memory.assertions[0],
        id: `a-${i}`,
      })),
    })
    const focused = boundedGraph(graph)
    expect(focused.nodes.length).toBeLessThanOrEqual(120)
    expect(focused.edges.length).toBeLessThanOrEqual(240)
    expect(focused.warnings.join()).toContain("182")
    expect(layoutGraph(focused)).toEqual(layoutGraph(focused))
  })
  it("compares immutable membership by IDs and retains the original snapshot", () => {
    const after = {
      ...memory,
      revision_id: "corrected",
      assertions: [{ ...memory.assertions[0], id: "replacement" }],
    }
    const diff = diffMemory(memory, after)
    expect(diff.removed[0].id).toBe("a")
    expect(diff.added[0].id).toBe("replacement")
    expect(memory.assertions[0].id).toBe("a")
  })
})
