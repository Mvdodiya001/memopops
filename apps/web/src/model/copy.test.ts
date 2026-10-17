import { describe, expect, it } from "vitest"

import { presentResult, revisionLabel, sameRevision } from "./copy"

describe("presentResult", () => {
  it("keeps proved, refuted, unknown, conflict, and unfinished checks distinct", () => {
    const proved = presentResult({ result: "PROVED", proofStatus: "VERIFIED", freshness: "CURRENT_AS_OF_READ", revisionLabel: "Revision 1" })
    const refuted = presentResult({ result: "REFUTED", proofStatus: "VERIFIED", freshness: "CURRENT_AS_OF_READ", revisionLabel: "Revision 2" })
    const unknown = presentResult({ result: "UNKNOWN", proofStatus: "NOT_REQUESTED", freshness: "CURRENT_AS_OF_READ", revisionLabel: "Revision 1" })
    const broken = presentResult({ result: "INCONSISTENT_MEMORY", proofStatus: "NOT_REQUESTED", freshness: "CURRENT_AS_OF_READ", revisionLabel: "Revision 1" })
    const unfinished = presentResult({ result: "SOLVER_UNKNOWN", proofStatus: "NOT_REQUESTED", freshness: "CURRENT_AS_OF_READ", revisionLabel: "Revision 1" })
    const budget = presentResult({ result: "PROVED", proofStatus: "BUDGET_EXCEEDED", freshness: "CURRENT_AS_OF_READ", revisionLabel: "Revision 1" })
    const historical = presentResult({ result: "PROVED", proofStatus: "VERIFIED", freshness: "HISTORICAL", revisionLabel: "Revision 1" })

    expect(proved.title).toBe("Follows from memory")
    expect(proved.assurance).toBe("Proof verified · Revision 1")
    expect(refuted.title).toBe("Ruled out by memory")
    expect(refuted.explanation).toBe("The accepted premises establish its negation.")
    expect(unknown.title).toBe("Not established")
    expect(unknown.tone).toBe("neutral")
    expect(broken.title).toBe("Memory needs repair")
    expect(unfinished.title).toBe("Check could not finish")
    expect(budget.assurance).toBe("Solver checked")
    expect(budget.explanation).toContain("certificate")
    expect(historical.historical).toBe(true)
    expect(historical.currentAction).toBe("Check against current memory")
    expect(new Set([proved.title, refuted.title, unknown.title, broken.title, unfinished.title]).size).toBe(5)
  })
})

describe("revision identity", () => {
  it("labels numbered revisions and rejects mismatched snapshots", () => {
    expect(revisionLabel("rev_002")).toBe("Revision 2")
    expect(revisionLabel("workspace_demo")).toBe("workspace_demo")
    expect(sameRevision("rev_001", "rev_001")).toBe(true)
    expect(sameRevision("rev_001", "rev_002")).toBe(false)
    expect(sameRevision(null, "rev_002")).toBe(false)
  })
})
