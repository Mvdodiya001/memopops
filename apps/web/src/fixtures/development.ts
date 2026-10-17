import r1File from "@vectors/demo-r1-proved.json"
import r2File from "@vectors/demo-r2-refuted.json"

import type { AssertionRecord, AtomRecord, Formula, MemoryDocument, ProposalDocument, QueryResponse, RevisionRecord, WorkspaceDocument } from "../api/types"

export const FIXTURE_NOTICE = "Development fixtures. These records are not live memory and are not a fallback for API failures."

export const DEMO_WORKSPACE_ID = "workspace_demo"
export const HEAD_REVISION_ID = "rev_002"

const atoms: AtomRecord[] = [
  {
    id: "api_v2",
    label: "API v2",
    meaning: "API v2 is deployed for release demo-42.",
    scope: "release demo-42",
  },
  {
    id: "tests_pass",
    label: "Integration tests",
    meaning: "The integration suite passed for release demo-42.",
    scope: "release demo-42",
  },
  {
    id: "release_ready",
    label: "Release readiness",
    meaning: "Release demo-42 may proceed.",
    scope: "release demo-42",
  },
  {
    id: "docs_signed",
    label: "Documentation",
    meaning: "The release notes for demo-42 are signed.",
    scope: "release demo-42",
  },
]

const deployed: Formula = { op: "atom", id: "api_v2" }
const tests: Formula = { op: "atom", id: "tests_pass" }
const ready: Formula = { op: "atom", id: "release_ready" }
const notTests: Formula = { op: "not", arg: tests }
const allow: Formula = { op: "implies", args: [{ op: "and", args: [deployed, tests] }, ready] }
const block: Formula = {
  op: "implies",
  args: [{ op: "not", arg: tests }, { op: "not", arg: ready }],
}

const longCorrection =
  "The corrected integration report for release demo-42 says the suite failed during checkout, migration, and rollback. The original passing report remains available as historical evidence. This development fixture keeps the full excerpt visible so the row and inspector grow instead of clipping it."

const r1Assertions: AssertionRecord[] = [
  {
    id: "as_api_v2",
    formula: deployed,
    accepted_at_revision: "rev_001",
    actor_label: "Operator",
    evidence: [
      {
        id: "ev_api",
        uri: "fixture://demo-42/api",
        excerpt: "API v2 is deployed on the release candidate.",
        observed_at: "2026-10-17T09:00:00Z",
      },
    ],
  },
  {
    id: "as_tests_pass",
    formula: tests,
    accepted_at_revision: "rev_001",
    actor_label: "Operator",
    evidence: [
      {
        id: "ev_tests",
        uri: "fixture://demo-42/tests",
        excerpt: "The integration suite passed in the original report.",
        observed_at: "2026-10-17T09:30:00Z",
      },
    ],
  },
  {
    id: "as_ready_rule",
    formula: allow,
    accepted_at_revision: "rev_001",
    actor_label: "Operator",
    evidence: [
      {
        id: "ev_ready",
        uri: "fixture://demo-42/policy-ready",
        excerpt: "Operator policy: a deployed API v2 and passing tests allow this release.",
        observed_at: "2026-10-17T09:40:00Z",
      },
    ],
  },
  {
    id: "as_block_rule",
    formula: block,
    accepted_at_revision: "rev_001",
    actor_label: "Operator",
    evidence: [
      {
        id: "ev_block",
        uri: "fixture://demo-42/policy-block",
        excerpt: "Operator policy: failed tests block this release. The allow rule alone does not imply this.",
        observed_at: "2026-10-17T09:41:00Z",
      },
    ],
  },
]

const r2Assertions: AssertionRecord[] = [
  r1Assertions[0],
  {
    id: "as_tests_fail",
    formula: notTests,
    accepted_at_revision: "rev_002",
    actor_label: "Operator",
    evidence: [
      {
        id: "ev_tests_corrected",
        uri: "fixture://demo-42/tests-corrected",
        excerpt: longCorrection,
        observed_at: "2026-10-17T10:00:00Z",
      },
    ],
  },
  r1Assertions[2],
  r1Assertions[3],
]

function memory(revisionId: string, knowledgeHash: string, assertions: AssertionRecord[]): MemoryDocument {
  return {
    workspace_id: DEMO_WORKSPACE_ID,
    revision_id: revisionId,
    knowledge_hash: knowledgeHash,
    semantics_version: "boolean-v1",
    atoms,
    assertions,
  }
}

type ProofStep = { clause_id: number; text: string }
type ClauseRow = { id: number; literals: number[]; origin: string; assertion_id?: string; pivot?: number }

type VectorFile = {
  development_fixture: true
  notice: string
  explanation: string
  steps: ProofStep[]
  bundle: {
    result: "PROVED" | "REFUTED"
    revision_id: string
    workspace_id: string
    knowledge_hash: string
    query_hash: string
    support_assertion_ids: string[]
    knowledge_witness: Record<string, boolean>
    query: Formula
    clauses: ClauseRow[]
    empty_clause_id: number
  }
}

export type StoredQuery = {
  response: QueryResponse
  steps: ProofStep[]
  clauses: ClauseRow[]
  bundle: unknown
}

function asVector(file: unknown): VectorFile {
  if (!file || typeof file !== "object" || !("development_fixture" in file) || file.development_fixture !== true) {
    throw new Error("Development vector is missing its fixture label.")
  }
  return file as VectorFile
}

const proved = asVector(r1File)
const refuted = asVector(r2File)

export const workspace: WorkspaceDocument = {
  workspace_id: DEMO_WORKSPACE_ID,
  label: "Release demo-42",
  head_revision_id: HEAD_REVISION_ID,
  role: "operator",
  capabilities: { can_write_memory: true },
  semantics_version: "boolean-v1",
}

export const revisions: RevisionRecord[] = [
  {
    revision_id: "rev_001",
    parent_revision_id: null,
    sequence: 1,
    knowledge_hash: proved.bundle.knowledge_hash,
    committed_at: "2026-10-17T09:42:00Z",
    reason: "Seed the release demo-42 snapshot.",
    actor_label: "Operator",
    acceptance: "trusted_fixture",
  },
  {
    revision_id: "rev_002",
    parent_revision_id: "rev_001",
    sequence: 2,
    knowledge_hash: refuted.bundle.knowledge_hash,
    committed_at: "2026-10-17T10:05:00Z",
    reason: "Correct the test report for release demo-42.",
    actor_label: "Operator",
    acceptance: "human_confirmed",
  },
]

export const memories: Record<string, MemoryDocument> = {
  rev_001: memory("rev_001", proved.bundle.knowledge_hash, r1Assertions),
  rev_002: memory("rev_002", refuted.bundle.knowledge_hash, r2Assertions),
}

function checkedQuery(vector: VectorFile, queryId: string): StoredQuery {
  const bundle = vector.bundle
  return {
    response: {
      query_id: queryId,
      workspace_id: bundle.workspace_id,
      revision_id: bundle.revision_id,
      head_revision_observed: HEAD_REVISION_ID,
      freshness: bundle.revision_id === HEAD_REVISION_ID ? "CURRENT_AS_OF_READ" : "HISTORICAL",
      semantics_version: "boolean-v1",
      knowledge_hash: bundle.knowledge_hash,
      query_hash: bundle.query_hash,
      result: bundle.result,
      proof_status: "VERIFIED",
      witnesses_verified: true,
      certificate_id: queryId,
      support_assertion_ids: bundle.support_assertion_ids,
      explanation: vector.explanation,
      query: bundle.query,
      solver: { name: "independent-checker", version: "resolution-v1", reason_unknown: null },
      witnesses: { knowledge: bundle.knowledge_witness, query_true: null, query_false: null },
    },
    steps: vector.steps,
    clauses: bundle.clauses,
    bundle,
  }
}

const unknownDocs: QueryResponse = {
  query_id: "query_r1_docs",
  workspace_id: DEMO_WORKSPACE_ID,
  revision_id: "rev_001",
  head_revision_observed: HEAD_REVISION_ID,
  freshness: "HISTORICAL",
  semantics_version: "boolean-v1",
  knowledge_hash: proved.bundle.knowledge_hash,
  query_hash: "development-fixture-docs-signed",
  result: "UNKNOWN",
  proof_status: "NOT_REQUESTED",
  witnesses_verified: true,
  certificate_id: null,
  support_assertion_ids: [],
  explanation: "Both outcomes remain possible under this memory.",
  query: { op: "atom", id: "docs_signed" },
  witnesses: {
    knowledge: null,
    query_true: { api_v2: true, docs_signed: true, release_ready: true, tests_pass: true },
    query_false: { api_v2: true, docs_signed: false, release_ready: true, tests_pass: true },
  },
}

const refutedApi: QueryResponse = {
  query_id: "query_r1_not_api",
  workspace_id: DEMO_WORKSPACE_ID,
  revision_id: "rev_001",
  head_revision_observed: HEAD_REVISION_ID,
  freshness: "HISTORICAL",
  semantics_version: "boolean-v1",
  knowledge_hash: proved.bundle.knowledge_hash,
  query_hash: "development-fixture-not-api",
  result: "REFUTED",
  proof_status: "NOT_REQUESTED",
  witnesses_verified: false,
  certificate_id: null,
  support_assertion_ids: ["as_api_v2"],
  explanation: "API v2 is an accepted premise, so its negation does not hold. This fixture has no exported certificate for this query.",
  query: { op: "not", arg: deployed },
}

export type QueryChoice = {
  id: string
  label: string
  formula: Formula
}

export const queryChoices: QueryChoice[] = [
  { id: "release_ready", label: "Release readiness", formula: ready },
  { id: "not_api_v2", label: "Negation of API v2", formula: { op: "not", arg: deployed } },
  { id: "docs_signed", label: "Documentation signed", formula: { op: "atom", id: "docs_signed" } },
]

const stored = new Map<string, StoredQuery>([
  ["rev_001:release_ready", checkedQuery(proved, "query_r1_ready")],
  ["rev_002:release_ready", checkedQuery(refuted, "query_r2_ready")],
  ["rev_001:not_api_v2", { response: refutedApi, steps: [], clauses: [], bundle: null }],
  ["rev_001:docs_signed", { response: unknownDocs, steps: [], clauses: [], bundle: null }],
  ["rev_002:docs_signed", { response: { ...unknownDocs, query_id: "query_r2_docs", revision_id: "rev_002", knowledge_hash: refuted.bundle.knowledge_hash, freshness: "CURRENT_AS_OF_READ", witnesses: {
    knowledge: null,
    query_true: { api_v2: true, docs_signed: true, release_ready: false, tests_pass: false },
    query_false: { api_v2: true, docs_signed: false, release_ready: false, tests_pass: false },
  } }, steps: [], clauses: [], bundle: null }],
])

export function storedQuery(revisionId: string, choiceId: string): StoredQuery | null {
  return stored.get(`${revisionId}:${choiceId}`) ?? null
}

export const quarantine: ProposalDocument = {
  proposal_id: "proposal_not_tests",
  status: "QUARANTINED",
  base_revision_id: "rev_001",
  reason: "Adding a failed test report without retracting the passing report would make memory inconsistent.",
  conflicting_assertion_ids: ["as_tests_pass"],
  proposed_assertion: {
    client_ref: "test-correction",
    formula: notTests,
    evidence: [
      {
        id: "ev_tests_corrected",
        uri: "fixture://demo-42/tests-corrected",
        excerpt: longCorrection,
        observed_at: "2026-10-17T10:00:00Z",
      },
    ],
  },
}

export function memoryFor(revisionId: string): MemoryDocument | null {
  return memories[revisionId] ?? null
}
