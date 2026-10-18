import type { LogicalResult, ProofStatus } from "../api/types"

// Match the agent's decision policy. The API receipt itself is audit metadata.
export function suggestedDecision(result: LogicalResult, proof: ProofStatus) {
  if (proof !== "VERIFIED" && proof !== "NOT_REQUESTED") return null
  return result === "PROVED" ? "PROCEED" : result === "REFUTED" ? "BLOCK" : null
}
