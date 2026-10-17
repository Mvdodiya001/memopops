/**
 * Provisional client shapes for M1, named to match docs/plan/CONTRACTS.md.
 * OpenAPI from the memory service replaces this file when it is published.
 * Display fields marked optional are not yet in the frozen response schema.
 */

export type Formula =
  | { op: "atom"; id: string }
  | { op: "not"; arg: Formula }
  | { op: "and" | "or" | "implies" | "iff"; args: [Formula, Formula] }

export type LogicalResult = "PROVED" | "REFUTED" | "UNKNOWN" | "INCONSISTENT_MEMORY" | "SOLVER_UNKNOWN"
export type ProofStatus = "VERIFIED" | "NOT_REQUESTED" | "BUDGET_EXCEEDED" | "FAILED"
export type Freshness = "CURRENT_AS_OF_READ" | "HISTORICAL"

export type Evidence = {
  id: string
  uri: string
  excerpt: string
  observed_at: string
}

export type AtomRecord = {
  id: string
  label: string
  meaning: string
  scope: string
}

export type AssertionRecord = {
  id: string
  formula: Formula
  evidence: Evidence[]
  accepted_at_revision?: string
  actor_label?: string
}

export type MemoryDocument = {
  workspace_id: string
  revision_id: string
  knowledge_hash: string
  semantics_version: "boolean-v1"
  atoms: AtomRecord[]
  assertions: AssertionRecord[]
}

export type WorkspaceSummary = {
  workspace_id: string
  label: string
}

export type WorkspaceDocument = {
  workspace_id: string
  label: string
  head_revision_id: string
  role?: string
  capabilities?: { can_write_memory?: boolean }
  semantics_version?: "boolean-v1"
}

export type WitnessMap = Record<string, boolean>

export type QueryResponse = {
  query_id: string
  workspace_id: string
  revision_id: string
  head_revision_observed: string
  freshness: Freshness
  semantics_version: "boolean-v1"
  knowledge_hash: string
  query_hash: string
  result: LogicalResult
  proof_status: ProofStatus
  witnesses_verified: boolean
  certificate_id: string | null
  support_assertion_ids: string[]
  explanation: string
  query: Formula
  solver?: { name: string; version: string; reason_unknown: string | null }
  timings_ms?: { load: number; solve: number; certificate: number; check: number }
  witnesses?: {
    knowledge: WitnessMap | null
    query_true: WitnessMap | null
    query_false: WitnessMap | null
  }
}

export type RevisionRecord = {
  revision_id: string
  parent_revision_id: string | null
  sequence: number
  knowledge_hash: string
  committed_at: string
  reason: string
  actor_label?: string
  acceptance?: "human_confirmed" | "trusted_fixture" | "model_proposed"
}

export type HistoryDocument = {
  revisions: RevisionRecord[]
  next_cursor: string | null
}

export type ProposalDocument = {
  proposal_id: string
  status: "QUARANTINED" | "PENDING_REVIEW"
  base_revision_id: string
  reason: string
  conflicting_assertion_ids: string[]
  proposed_assertion: {
    client_ref: string
    formula: Formula
    evidence: Evidence[]
  }
}

export type QueryRequest = {
  revision_id: string
  idempotency_key: string
  query: Formula
  proof_mode: "certificate" | "solver"
}

export type MutationRequest = {
  expected_revision: string
  idempotency_key: string
  reason: string
  acceptance: "human_confirmed" | "trusted_fixture" | "model_proposed"
  mutations: Array<
    | { op: "add"; assertion: MutationAssertion }
    | { op: "retract"; target_assertion_id: string }
    | { op: "replace"; target_assertion_id: string; assertion: MutationAssertion }
  >
}

export type MutationAssertion = {
  client_ref: string
  formula: Formula
  evidence: Evidence[]
}

export type MutationReceipt = {
  revision_id?: string
  parent_revision_id?: string
  knowledge_hash?: string
  proposal_id?: string
  base_revision_id?: string
  conflicting_assertion_ids?: string[]
  reason?: string
}

export type ErrorBody = {
  error?: {
    code?: string
    message?: string
    request_id?: string
    retryable?: boolean
    details?: Record<string, unknown>
  }
}
