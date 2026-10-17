import type { Freshness, LogicalResult, ProofStatus } from "../api/types"

export type ResultTone = "neutral" | "positive" | "conflict" | "pending"

export type ResultPresentation = {
  title: string
  explanation: string
  assurance: string | null
  tone: ResultTone
  historical: boolean
  currentAction: string | null
}

export function presentResult(input: {
  result: LogicalResult
  proofStatus: ProofStatus
  freshness: Freshness
  revisionLabel: string
  explanation?: string
}): ResultPresentation {
  const historical = input.freshness === "HISTORICAL"
  const base = baseCopy(input.result, input.explanation)
  if (input.proofStatus === "BUDGET_EXCEEDED") {
    return {
      title: base.title,
      explanation: "A complete certificate was not generated within the limit.",
      assurance: "Solver checked",
      tone: base.tone,
      historical,
      currentAction: historical ? "Check against current memory" : null,
    }
  }
  if (input.proofStatus === "FAILED") {
    return {
      title: "Result withheld",
      explanation: "The certificate failed an integrity check.",
      assurance: null,
      tone: "conflict",
      historical,
      currentAction: null,
    }
  }
  const assurance =
    input.proofStatus === "VERIFIED" ? `Proof verified · ${input.revisionLabel}` : null
  return {
    title: base.title,
    explanation: base.explanation,
    assurance,
    tone: base.tone,
    historical,
    currentAction: historical ? "Check against current memory" : null,
  }
}

function baseCopy(result: LogicalResult, explanation?: string): { title: string; explanation: string; tone: ResultTone } {
  switch (result) {
    case "PROVED":
      return {
        title: "Follows from memory",
        explanation: explanation || "This follows from the accepted premises.",
        tone: "positive",
      }
    case "REFUTED":
      return {
        title: "Ruled out by memory",
        explanation: explanation || "The accepted premises establish its negation.",
        tone: "conflict",
      }
    case "UNKNOWN":
      return {
        title: "Not established",
        explanation: explanation || "Both outcomes remain possible under this memory.",
        tone: "neutral",
      }
    case "INCONSISTENT_MEMORY":
      return {
        title: "Memory needs repair",
        explanation: explanation || "Accepted premises conflict. Conclusions are withheld.",
        tone: "conflict",
      }
    case "SOLVER_UNKNOWN":
      return {
        title: "Check could not finish",
        explanation: explanation || "No conclusion was established within the limit.",
        tone: "pending",
      }
  }
}

export function revisionLabel(revisionId: string): string {
  const match = /^rev_0*(\d+)$/.exec(revisionId)
  if (!match) return revisionId
  return `Revision ${Number(match[1])}`
}

export function sameRevision(left: string | null | undefined, right: string | null | undefined): boolean {
  return Boolean(left && right && left === right)
}
