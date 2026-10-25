import { describe, expect, it } from "vitest"
import { parseExpression } from "./expression"

const ids = ["p", "q", "r"]
describe("explicit logic expressions", () => {
  it("preserves precedence, parentheses and right-associative implication", () => {
    expect(parseExpression("p & !q -> r", ids)).toEqual({
      op: "implies",
      args: [
        {
          op: "and",
          args: [
            { op: "atom", id: "p" },
            { op: "not", arg: { op: "atom", id: "q" } },
          ],
        },
        { op: "atom", id: "r" },
      ],
    })
    expect(parseExpression("p -> q -> r", ids)).toEqual(parseExpression("p -> (q -> r)", ids))
    expect(parseExpression("¬p ∨ (q ↔ r)", ids)).toEqual(parseExpression("!p | (q <-> r)", ids))
  })
  it.each([
    "",
    "p q",
    "p constructor q",
    "p &",
    "(p",
    "p)",
    "p && q",
    "unknown",
    "p; alert(1)",
    "!".repeat(100) + "p",
    "p | ".repeat(65) + "q",
  ])("rejects invalid or excessive input: %s", (text) => {
    expect(() => parseExpression(text, ids)).toThrow()
  })
  it("handles registered proposition names that also occur on Object.prototype", () => {
    expect(parseExpression("constructor", ["constructor"])).toEqual({ op: "atom", id: "constructor" })
    expect(parseExpression("hasownproperty -> constructor", ["hasownproperty", "constructor"]).op).toBe("implies")
  })
})
