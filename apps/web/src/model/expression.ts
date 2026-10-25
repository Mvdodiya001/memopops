import type { Formula } from "../api/types"

/** Deterministic notation, never an LLM translation. Server validates the resulting AST again. */
export function parseExpression(text: string, registered: readonly string[]): Formula {
  if (!text.trim() || text.length > 4096)
    throw new Error("Enter an expression of at most 4,096 characters.")
  const tokens: string[] = []
  let offset = 0
  while (offset < text.length) {
    if (!text.slice(offset).trim()) break
    const match = /^\s*(<->|->|[()!&|¬∧∨→↔]|[a-z][a-z0-9_]{0,63})/.exec(text.slice(offset))
    if (!match)
      throw new Error(
        `Unexpected character near position ${offset + 1}. Use proposition IDs and logic operators.`,
      )
    tokens.push(
      ({ "¬": "!", "∧": "&", "∨": "|", "→": "->", "↔": "<->" } as Record<string, string>)[
        match[1]
      ] ?? match[1],
    )
    offset += match[0].length
    if (tokens.length > 256) throw new Error("Expression is too large.")
  }
  let index = 0
  const known = new Set(registered)
  const precedence: Record<string, number> = { "<->": 1, "->": 2, "|": 3, "&": 4 }
  const operations = { "<->": "iff", "->": "implies", "|": "or", "&": "and" } as const
  function expression(minimum = 1, depth = 1): Formula {
    if (depth > 16) throw new Error("Expressions may be at most 16 levels deep.")
    const token = tokens[index++]
    let left: Formula
    if (token === "!") left = { op: "not", arg: expression(5, depth + 1) }
    else if (token === "(") {
      left = expression(1, depth + 1)
      if (tokens[index++] !== ")") throw new Error("Missing closing parenthesis.")
    } else {
      if (!token || !/^[a-z][a-z0-9_]*$/.test(token))
        throw new Error("Expected a proposition or parenthesized expression.")
      if (!known.has(token))
        throw new Error(`Unknown proposition: ${token}. Choose an ID from this workspace.`)
      left = { op: "atom", id: token }
    }
    while (index < tokens.length) {
      const operator = tokens[index] as keyof typeof operations
      const rank = precedence[operator] ?? 0
      if (rank < minimum) break
      index++
      const right = expression(rank + (operator === "->" ? 0 : 1), depth + 1)
      left = { op: operations[operator], args: [left, right] }
    }
    return left
  }
  const result = expression()
  if (index !== tokens.length)
    throw new Error(`Unexpected token: ${tokens[index]}. Add an operator between propositions.`)
  let nodes = 0
  function check(node: Formula, depth: number) {
    if (++nodes > 64 || depth > 16)
      throw new Error("Formula exceeds the limit of 64 nodes or 16 levels.")
    if (node.op === "not") check(node.arg, depth + 1)
    else if (node.op !== "atom") node.args.forEach((child) => check(child, depth + 1))
  }
  check(result, 1)
  return result
}
