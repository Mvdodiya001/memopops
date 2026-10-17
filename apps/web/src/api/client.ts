import type {
  ErrorBody,
  HistoryDocument,
  MemoryDocument,
  MutationReceipt,
  MutationRequest,
  ProposalDocument,
  QueryRequest,
  QueryResponse,
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

export function apiOrigin(): string {
  return (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "")
}

export function workspacePath(workspaceId: string, suffix: string): string {
  return `${API_PREFIX}/workspaces/${encodeURIComponent(workspaceId)}${suffix}`
}

export async function getHealthReady(signal?: AbortSignal): Promise<{ status: string }> {
  return request("/api/v1/health/ready", { signal })
}

export async function listWorkspaces(signal?: AbortSignal): Promise<WorkspaceSummary[]> {
  const body = await request<WorkspaceSummary[] | { workspaces: WorkspaceSummary[] }>("/api/v1/workspaces", { signal })
  return Array.isArray(body) ? body : body.workspaces
}

export function getWorkspace(workspaceId: string, signal?: AbortSignal): Promise<WorkspaceDocument> {
  return request(workspacePath(workspaceId, ""), { signal })
}

export function getMemory(workspaceId: string, revisionId: string, signal?: AbortSignal): Promise<MemoryDocument> {
  const query = new URLSearchParams({ revision: revisionId })
  return request(workspacePath(workspaceId, `/memory?${query}`), { signal })
}

export function getHistory(workspaceId: string, signal?: AbortSignal): Promise<HistoryDocument> {
  return request(workspacePath(workspaceId, "/revisions"), { signal })
}

export function getProposals(workspaceId: string, signal?: AbortSignal): Promise<ProposalDocument[]> {
  const body = awaitRequest<ProposalDocument[] | { proposals: ProposalDocument[] }>(
    workspacePath(workspaceId, "/proposals?status=QUARANTINED"),
    { signal },
  )
  return body.then((value) => (Array.isArray(value) ? value : value.proposals))
}

export function postQuery(workspaceId: string, body: QueryRequest, signal?: AbortSignal): Promise<QueryResponse> {
  return request(workspacePath(workspaceId, "/queries"), {
    method: "POST",
    body: JSON.stringify(body),
    signal,
  })
}

export function postRevision(
  workspaceId: string,
  body: MutationRequest,
  signal?: AbortSignal,
): Promise<{ status: number; body: MutationReceipt }> {
  return requestStatus(workspacePath(workspaceId, "/revisions"), {
    method: "POST",
    body: JSON.stringify(body),
    signal,
  })
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const response = await send(path, init)
  if (!response.ok) throw await toError(response)
  return response.json() as Promise<T>
}

function awaitRequest<T>(path: string, init: RequestInit): Promise<T> {
  return request<T>(path, init)
}

async function requestStatus(path: string, init: RequestInit): Promise<{ status: number; body: MutationReceipt }> {
  const response = await send(path, init)
  if (!response.ok) throw await toError(response)
  const body = (await response.json()) as MutationReceipt
  return { status: response.status, body }
}

async function send(path: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(`${apiOrigin()}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
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

async function toError(response: Response): Promise<ApiError> {
  let payload: ErrorBody | null = null
  try {
    payload = (await response.json()) as ErrorBody
  } catch {
    payload = null
  }
  const envelope = payload?.error
  const message = envelope?.message || `The memory service returned status ${response.status}.`
  return new ApiError(message, {
    status: response.status,
    code: envelope?.code || "HTTP_ERROR",
    retryable: envelope?.retryable ?? response.status >= 500,
    requestId: envelope?.request_id ?? null,
    details: envelope?.details ?? null,
  })
}
