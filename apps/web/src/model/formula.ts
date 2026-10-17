import type { AtomRecord, AssertionRecord, Formula } from "../api/types"

export function prettyFormula(formula: Formula): string {
  switch (formula.op) {
    case "atom":
      return formula.id
    case "not":
      return `¬${wrap(formula.arg)}`
    case "and":
      return `(${prettyFormula(formula.args[0])} ∧ ${prettyFormula(formula.args[1])})`
    case "or":
      return `(${prettyFormula(formula.args[0])} ∨ ${prettyFormula(formula.args[1])})`
    case "implies":
      return `(${prettyFormula(formula.args[0])} → ${prettyFormula(formula.args[1])})`
    case "iff":
      return `(${prettyFormula(formula.args[0])} ↔ ${prettyFormula(formula.args[1])})`
  }
}

function wrap(formula: Formula): string {
  if (formula.op === "atom") return formula.id
  return `(${prettyFormula(formula)})`
}

export function assertionTitle(formula: Formula, atoms: readonly AtomRecord[]): string {
  const byId = new Map(atoms.map((atom) => [atom.id, atom]))
  if (formula.op === "atom") return byId.get(formula.id)?.meaning ?? formula.id
  if (formula.op === "not" && formula.arg.op === "atom") {
    const atom = byId.get(formula.arg.id)
    return atom ? `Negation of “${atom.label}”` : prettyFormula(formula)
  }
  if (formula.op === "implies") {
    return `${phrase(formula.args[0], byId)} implies ${phrase(formula.args[1], byId)}`
  }
  return prettyFormula(formula)
}

function phrase(formula: Formula, atoms: Map<string, AtomRecord>): string {
  if (formula.op === "atom") return atoms.get(formula.id)?.label ?? formula.id
  if (formula.op === "not" && formula.arg.op === "atom") {
    const atom = atoms.get(formula.arg.id)
    return atom ? `not ${atom.label}` : prettyFormula(formula)
  }
  if (formula.op === "and") return `${phrase(formula.args[0], atoms)} and ${phrase(formula.args[1], atoms)}`
  return prettyFormula(formula)
}

export function formatTimestamp(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date)
}

export type AssertionDiff = {
  added: AssertionRecord[]
  removed: AssertionRecord[]
}

export function assertionDiff(before: readonly AssertionRecord[], after: readonly AssertionRecord[]): AssertionDiff {
  const beforeText = new Map(before.map((item) => [item.id, prettyFormula(item.formula)]))
  const afterText = new Map(after.map((item) => [item.id, prettyFormula(item.formula)]))
  return {
    removed: before.filter((item) => afterText.get(item.id) !== prettyFormula(item.formula)),
    added: after.filter((item) => beforeText.get(item.id) !== prettyFormula(item.formula)),
  }
}
