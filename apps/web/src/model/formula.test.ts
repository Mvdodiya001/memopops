import { describe, expect, it } from "vitest"

import type { AssertionRecord } from "../api/types"
import { assertionDiff, prettyFormula } from "./formula"

const passed: AssertionRecord = {
  id: "as_tests_pass",
  formula: { op: "atom", id: "tests_pass" },
  evidence: [],
}
const failed: AssertionRecord = {
  id: "as_tests_fail",
  formula: { op: "not", arg: { op: "atom", id: "tests_pass" } },
  evidence: [],
}
const deployed: AssertionRecord = {
  id: "as_api_v2",
  formula: { op: "atom", id: "api_v2" },
  evidence: [],
}

describe("assertionDiff", () => {
  it("shows a replacement as a removal plus an addition", () => {
    const diff = assertionDiff([deployed, passed], [deployed, failed])
    expect(diff.removed.map((item) => item.id)).toEqual(["as_tests_pass"])
    expect(diff.added.map((item) => item.id)).toEqual(["as_tests_fail"])
    expect(prettyFormula(failed.formula)).toBe("¬tests_pass")
  })
})
