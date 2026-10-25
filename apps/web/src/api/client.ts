import type {
  ErrorBody,
  AtomRecord,
  HistoryDocument,
  MemoryDocument,
  MutationReceipt,
  MutationRequest,
  DecisionReceipt,
  DecisionRequest,
  ImpactDocument,
  ProposalDocument,
  QueryRequest,
  QueryResponse,
  RevisionRecord,
  WorkspaceDocument,
  WorkspaceSummary,
} from "./types"

const API_PREFIX = "/api/v1"

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly retryable: boolean
  readonly requestId: string | null
  readonly details: Record<string, unknown> | null

  constructor(
    message: string,
    init: {
      status: number
      code: string
      retryable: boolean
      requestId: string | null
      details: Record<string, unknown> | null
    },
  ) {
    super(message)
    this.name = "ApiError"
    this.status = init.status
    this.code = init.code
    this.retryable = init.retryable
    this.requestId = init.requestId
    this.details = init.details
  }
}

export type RequestOptions = {
  signal?: AbortSignal
  token?: string | null
}

export function apiOrigin(): string {
  return (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "")
}

type ApiMemory = {
  workspace_id: string
  revision_id: string
  knowledge_hash: string
  atom_ids: string[]
  atoms?: AtomRecord[]
  assertions: Array<{
    id: string
    formula: MemoryDocument["assertions"][number]["formula"]
    evidence: MemoryDocument["assertions"][number]["evidence"]
    actor_id?: string
  }>
}

function normalizeMemory(payload: ApiMemory): MemoryDocument {
  const atoms: AtomRecord[] = payload.atom_ids.map((id) => {
    const definition = payload.atoms?.find(atom => atom.id === id)
    return { id, label: definition?.label || id, meaning: definition?.meaning || id, scope: definition?.scope || payload.workspace_id }
  })
  return {
    workspace_id: payload.workspace_id,
    revision_id: payload.revision_id,
    knowledge_hash: payload.knowledge_hash,
    semantics_version: "boolean-v1",
    atoms,
    assertions: payload.assertions.map((item) => ({
      id: item.id,
      formula: item.formula,
      evidence: item.evidence,
      actor_label: item.actor_id,
      accepted_at_revision: payload.revision_id,
    })),
  }
}

export function buildCertificateQuery(input: Omit<QueryRequest, "proof_mode">): QueryRequest {
  return { ...input, proof_mode: "certificate" }
}

export function workspacePath(workspaceId: string, suffix: string): string {
  return `${API_PREFIX}/workspaces/${encodeURIComponent(workspaceId)}${suffix}`
}

export async function getHealthReady(options?: RequestOptions): Promise<{ status: string }> {
  return request("/api/v1/health/ready", { signal: options?.signal })
}

export async function listWorkspaces(options?: RequestOptions): Promise<WorkspaceSummary[]> {
  const body = await request<WorkspaceSummary[] | { workspaces: WorkspaceSummary[] }>("/api/v1/workspaces", options)
  return Array.isArray(body) ? body : body.workspaces
}

export function getWorkspace(workspaceId: string, options?: RequestOptions): Promise<WorkspaceDocument> {
  return request(workspacePath(workspaceId, ""), options)
}

export function initializeWorkspace(workspaceId: string, atoms: AtomRecord[], options?: RequestOptions): Promise<{ revision_id: string }> {
  return request(workspacePath(workspaceId, "/initialize"), { ...options, method: "POST", body: JSON.stringify({ atoms }) })
}

export type QuerySummary = Pick<QueryResponse, "query_id" | "revision_id" | "query" | "result" | "proof_status" | "freshness"> & { created_at?: string }

export function getQueryHistory(workspaceId: string, options?: RequestOptions, before?: string): Promise<{ items: QuerySummary[]; next_cursor: string | null }> {
  return request(workspacePath(workspaceId, `/queries?limit=25${before ? `&before=${encodeURIComponent(before)}` : ""}`), options)
}

export async function getMemory(workspaceId: string, revisionId: string, options?: RequestOptions): Promise<MemoryDocument> {
  const query = new URLSearchParams({ revision_id: revisionId })
  const payload = await request<ApiMemory>(workspacePath(workspaceId, `/memory?${query}`), options)
  return normalizeMemory(payload)
}

export async function getHistory(workspaceId: string, options?: RequestOptions, beforeSequence?: string): Promise<HistoryDocument> {
  const payload = await request<{ items?: RevisionRecord[]; revisions?: RevisionRecord[]; next_cursor?: number | string | null }>(
    workspacePath(workspaceId, `/revisions${beforeSequence ? `?before_sequence=${encodeURIComponent(beforeSequence)}` : ""}`),
    options,
  )
  const items = payload.items ?? payload.revisions ?? []
  return {
    revisions: items.map((item) => ({
      ...item,
      committed_at: item.created_at ?? item.committed_at ?? "",
      actor_label: item.actor_id ?? item.actor_label,
    })),
    next_cursor: payload.next_cursor == null ? null : String(payload.next_cursor),
  }
}

export function getCertificate(workspaceId: string, queryId: string, options?: RequestOptions): Promise<unknown> {
  return request(workspacePath(workspaceId, `/queries/${encodeURIComponent(queryId)}/certificate`), options)
}

export function getQueryResult(workspaceId: string, queryId: string, options?: RequestOptions): Promise<QueryResponse> {
  return request(workspacePath(workspaceId, `/queries/${encodeURIComponent(queryId)}`), options)
}

export function getRevisionImpact(
  workspaceId: string,
  revisionId: string,
  options?: RequestOptions,
  before?: string,
): Promise<ImpactDocument> {
  const query = new URLSearchParams({ revision: revisionId, limit: "50" })
  if (before) query.set("before", before)
  return request(workspacePath(workspaceId, `/impact?${query}`), options)
}

export function getProposals(workspaceId: string, options?: RequestOptions): Promise<ProposalDocument[]> {
  return request<ProposalDocument[] | { proposals: ProposalDocument[] }>(
    workspacePath(workspaceId, "/proposals?status=QUARANTINED"),
    options,
  ).then((value) => (Array.isArray(value) ? value : value.proposals))
}

export function postQuery(workspaceId: string, body: QueryRequest, options?: RequestOptions): Promise<QueryResponse> {
  return request(workspacePath(workspaceId, "/queries"), {
    method: "POST",
    body: JSON.stringify(body),
    signal: options?.signal,
    token: options?.token,
  })
}

export function postDecision(
  workspaceId: string,
  body: DecisionRequest,
  options?: RequestOptions,
): Promise<DecisionReceipt> {
  return request(workspacePath(workspaceId, "/decisions"), {
    method: "POST",
    body: JSON.stringify(body),
    signal: options?.signal,
    token: options?.token,
  })
}

export function postRevision(
  workspaceId: string,
  body: MutationRequest,
  options?: RequestOptions,
): Promise<{ status: number; body: MutationReceipt }> {
  return requestStatus(workspacePath(workspaceId, "/revisions"), {
    method: "POST",
    body: JSON.stringify(body),
    signal: options?.signal,
    token: options?.token,
  })
}

async function request<T>(path: string, options?: RequestOptions & RequestInit): Promise<T> {
  const response = await send(path, options)
  if (!response.ok) throw await toError(response)
  return response.json() as Promise<T>
}

async function requestStatus(path: string, options?: RequestOptions & RequestInit): Promise<{ status: number; body: MutationReceipt }> {
  const response = await send(path, options)
  if (!response.ok) throw await toError(response)
  const body = (await response.json()) as MutationReceipt
  return { status: response.status, body }
}

async function send(path: string, options?: RequestOptions & RequestInit): Promise<Response> {
  const init: RequestInit & { token?: string | null } = { ...(options ?? {}) }
  const token = init.token
  delete init.token
  try {
    return await fetch(`${apiOrigin()}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    })
  } catch {
    throw new ApiError("The memory service could not be reached.", {
      status: 0,
      code: "NETWORK",
      retryable: true,
      requestId: null,
      details: null,
    })
  }
}

export function messageFromPayload(payload: ErrorBody | null, status: number): { message: string; code: string; retryable: boolean; requestId: string | null; details: Record<string, unknown> | null } {
  const envelope = payload?.error
  if (envelope?.message) {
    return {
      message: envelope.message,
      code: envelope.code || "HTTP_ERROR",
      retryable: envelope.retryable ?? status >= 500,
      requestId: envelope.request_id ?? null,
      details: envelope.details ?? null,
    }
  }
  if (typeof payload?.detail === "string" && payload.detail) {
    return { message: payload.detail, code: status === 409 ? "CONFLICT" : "HTTP_ERROR", retryable: status >= 500, requestId: null, details: null }
  }
  if (payload?.detail && typeof payload.detail === "object" && !Array.isArray(payload.detail)) {
    const actual = payload.detail.actual_revision
    const message = actual
      ? `Memory changed. Review revision ${actual} before retrying.`
      : "Memory changed. Review the latest revision before retrying."
    return { message, code: payload.detail.code || "REVISION_CONFLICT", retryable: false, requestId: null, details: payload.detail }
  }
  if (Array.isArray(payload?.detail)) {
    const message = payload.detail.map((item) => item.msg).filter((item): item is string => Boolean(item)).join(" ")
    if (message) return { message, code: "VALIDATION", retryable: false, requestId: null, details: null }
  }
  return { message: `The memory service returned status ${status}.`, code: "HTTP_ERROR", retryable: status >= 500, requestId: null, details: null }
}

async function toError(response: Response): Promise<ApiError> {
  let payload: ErrorBody | null = null
  try {
    payload = (await response.json()) as ErrorBody
  } catch {
    payload = null
  }
  const parsed = messageFromPayload(payload, response.status)
  return new ApiError(parsed.message, { status: response.status, ...parsed })
}
