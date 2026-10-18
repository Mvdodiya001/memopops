import { describe, expect, it } from "vitest"
import { suggestedDecision } from "./decision"

describe("suggested decisions", () => {
  it("withholds actions for incomplete/failed certificates or undecided logic", () => {
    expect(suggestedDecision("PROVED", "VERIFIED")).toBe("PROCEED")
    expect(suggestedDecision("REFUTED", "NOT_REQUESTED")).toBe("BLOCK")
    expect(suggestedDecision("PROVED", "BUDGET_EXCEEDED")).toBeNull()
    expect(suggestedDecision("REFUTED", "FAILED")).toBeNull()
    expect(suggestedDecision("UNKNOWN", "NOT_REQUESTED")).toBeNull()
    expect(suggestedDecision("SOLVER_UNKNOWN", "NOT_REQUESTED")).toBeNull()
  })
})
