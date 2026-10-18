import {
  QueryClient,
  QueryClientProvider,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { useEffect, useState } from "react"

import {
  ApiError,
  buildCertificateQuery,
  getCertificate,
  getHealthReady,
  getHistory,
  getMemory,
  getProposals,
  getRevisionImpact,
  getWorkspace,
  listWorkspaces,
  postDecision,
  postQuery,
  postRevision,
} from "../api/client"
import type { Formula, QueryResponse } from "../api/types"
import { ResultCard } from "../components/ResultCard"
import { Shell } from "../components/Shell"
import { RevisionComparison } from "../components/RevisionComparison"
import { MemoryGraphView, QuerySupport } from "./MemoryGraphView"
import { RunWalkthrough } from "../run/RunWalkthrough"
import type { RunData } from "../run/parse"
import { pollInterval, usePageVisible } from "./observation"
import { suggestedDecision } from "../model/decision"
import { presentResult, revisionLabel, sameRevision } from "../model/copy"
import { assertionTitle, formatTimestamp, prettyFormula } from "../model/formula"
import { hrefFor, type AppLocation, type Section } from "../model/location"

type Session = {
  workspaceId: string
  token: string
  canWrite: boolean
  followInitially: boolean
}

export function LiveApp(props: {
  location: AppLocation
  navigate: (href: string, replace?: boolean) => void
}) {
  const [session, setSession] = useState<Session | null>(null)
  const [run, setRun] = useState<RunData | null>(null)
  const [cache, setCache] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: false, refetchOnWindowFocus: false },
          mutations: { retry: false },
        },
      }),
  )
  function connect(next: Session) {
    cache.clear()
    setCache(
      new QueryClient({
        defaultOptions: {
          queries: { retry: false, refetchOnWindowFocus: false },
          mutations: { retry: false },
        },
      }),
    )
    setSession(next)
  }
  useEffect(() => () => cache.clear(), [cache])
  if (props.location.section === "run")
    return (
      <QueryClientProvider client={cache}>
        <RunWalkthrough
          run={run}
          onRun={setRun}
          location={props.location}
          navigate={props.navigate}
          connection={session ?? undefined}
        />
      </QueryClientProvider>
    )
  if (!session || session.workspaceId !== props.location.workspaceId) {
    return <ConnectForm location={props.location} navigate={props.navigate} onConnect={connect} />
  }
  return (
    <QueryClientProvider client={cache}>
      <WorkspaceScreen
        location={{ ...props.location, workspaceId: session.workspaceId }}
        navigate={props.navigate}
        token={session.token}
        canWrite={session.canWrite}
        followInitially={session.followInitially}
        onDisconnect={() => {
          cache.clear()
          setSession(null)
        }}
      />
    </QueryClientProvider>
  )
}

function ConnectForm(props: {
  location: AppLocation
  navigate: (href: string, replace?: boolean) => void
  onConnect: (session: Session) => void
}) {
  const [workspaceId, setWorkspaceId] = useState(props.location.workspaceId ?? "workspace_demo")
  const [revisionId, setRevisionId] = useState(props.location.revisionId ?? "")
  const [token, setToken] = useState("")
  const [pending, setPending] = useState(false)
  const [error, setError] = useState("")
  return (
    <main className="main connect-page" id="content">
      <h1 className="page-title">memopops</h1>
      <p>Shared memory, with reasons.</p>
      <a
        className="walkthrough-link"
        href="/run"
        onClick={(e) => {
          e.preventDefault()
          props.navigate("/run")
        }}
      >
        Open a recorded walkthrough →
      </a>
      <form
        className="panel"
        onSubmit={(event) => {
          event.preventDefault()
          setPending(true)
          setError("")
          void listWorkspaces({ token })
            .then(async (workspaces) => {
              const match = workspaces.find((item) => item.workspace_id === workspaceId)
              if (!match) {
                setError("This token is not authorized for a workspace.")
                return
              }
              const details = await getWorkspace(match.workspace_id, { token })
              props.onConnect({
                workspaceId: details.workspace_id,
                token,
                canWrite: details.capabilities?.can_write_memory === true,
                followInitially: !revisionId,
              })
              props.navigate(
                hrefFor(new URL(window.location.href), {
                  workspaceId: details.workspace_id,
                  revisionId: revisionId || details.head_revision_id,
                  section: props.location.section,
                  source: "api",
                  preview: null,
                }),
              )
            })
            .catch((caught: unknown) => {
              setError(
                caught instanceof ApiError
                  ? caught.message
                  : "The memory service could not be reached.",
              )
            })
            .finally(() => setPending(false))
        }}
      >
        <h2 className="section-title">Connect to the memory service</h2>
        <p className="meta">
          The bearer token stays in this page only. Development fixtures are not used if this
          request fails.
        </p>
        <label className="revision-control">
          <span>Workspace</span>
          <input
            type="text"
            value={workspaceId}
            onChange={(event) => setWorkspaceId(event.target.value)}
            required
          />
        </label>
        <label className="revision-control">
          <span>Revision</span>
          <input
            type="text"
            value={revisionId}
            onChange={(event) => setRevisionId(event.target.value)}
            placeholder="Current head (automatic)"
          />
        </label>
        <label className="revision-control">
          <span>Bearer token</span>
          <input
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            autoComplete="off"
            required
          />
        </label>
        {error ? (
          <p className="callout" role="alert">
            {error}
          </p>
        ) : null}
        <button className="primary" type="submit" disabled={pending}>
          {pending ? "Connecting…" : "Connect"}
        </button>
      </form>
    </main>
  )
}

function WorkspaceScreen(props: {
  location: AppLocation & { workspaceId: string }
  navigate: (href: string, replace?: boolean) => void
  token: string
  canWrite: boolean
  followInitially: boolean
  onDisconnect: () => void
}) {
  const cache = useQueryClient()
  const [followHead, setFollowHead] = useState(props.followInitially)
  const [followError, setFollowError] = useState(false)
  const [followAttempt, setFollowAttempt] = useState(0)
  const [view, setView] = useState<"graph" | "list">("graph")
  const visible = usePageVisible()
  const workspaceId = props.location.workspaceId
  const token = props.token
  const health = useQuery({
    queryKey: ["health", "ready"],
    queryFn: ({ signal }) => getHealthReady({ signal }),
    refetchInterval: (query) => pollInterval(visible, query.state),
  })
  const revisionId = props.location.revisionId
  const memory = useQuery({
    queryKey: ["memory", workspaceId, revisionId],
    queryFn: ({ signal }) => getMemory(workspaceId, revisionId ?? "", { signal, token }),
    enabled: Boolean(revisionId),
  })
  const history = useInfiniteQuery({
    queryKey: ["history", workspaceId],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ signal, pageParam }) => getHistory(workspaceId, { signal, token }, pageParam),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  })
  const proposals = useQuery({
    queryKey: ["proposals", workspaceId],
    queryFn: ({ signal }) => getProposals(workspaceId, { signal, token }),
    refetchInterval: (query) => pollInterval(visible, query.state, 5000),
  })

  function go(patch: Partial<AppLocation>) {
    props.navigate(
      hrefFor(new URL(window.location.href), {
        ...props.location,
        source: "api",
        preview: null,
        ...patch,
      }),
    )
  }

  const workspace = useQuery({
    queryKey: ["workspace", workspaceId],
    queryFn: ({ signal }) => getWorkspace(workspaceId, { signal, token }),
    refetchInterval: (query) => pollInterval(visible, query.state),
  })
  const headRevisionId = workspace.data?.head_revision_id
  useEffect(() => {
    if (headRevisionId) void cache.invalidateQueries({ queryKey: ["history", workspaceId] })
  }, [headRevisionId, cache, workspaceId])
  useEffect(() => {
    let active = true
    setFollowError(false)
    if (followHead && headRevisionId && headRevisionId !== revisionId) {
      void cache
        .fetchQuery({
          queryKey: ["memory", workspaceId, headRevisionId],
          queryFn: ({ signal }) => getMemory(workspaceId, headRevisionId, { token, signal }),
        })
        .then((snapshot) => {
          if (
            active &&
            snapshot.revision_id === headRevisionId &&
            snapshot.workspace_id === workspaceId
          )
            props.navigate(
              hrefFor(new URL(window.location.href), {
                revisionId: headRevisionId,
                selectedId: null,
              }),
            )
        })
        .catch(() => {
          if (active) setFollowError(true)
        })
    }
    return () => {
      active = false
    }
  }, [
    headRevisionId,
    followHead,
    revisionId,
    cache,
    workspaceId,
    token,
    props.navigate,
    followAttempt,
  ])
  const historical = Boolean(revisionId && headRevisionId && revisionId !== headRevisionId)
  const visibleMemory =
    memory.data &&
    memory.data.workspace_id === workspaceId &&
    sameRevision(memory.data.revision_id, revisionId)
      ? memory.data
      : null
  const connectionTone =
    health.isError || workspace.isError || memory.isError || (followHead && followError)
      ? "bad"
      : workspace.isSuccess
        ? "ok"
        : "pending"
  const connectionLabel =
    connectionTone === "bad"
      ? "Refresh failed"
      : workspace.isSuccess
        ? `Live API · checked ${new Date(workspace.dataUpdatedAt).toLocaleTimeString()}`
        : "Checking connection"
  const revisionRecords = [
    ...new Map(
      (history.data?.pages.flatMap((page) => page.revisions) ?? []).map((item) => [
        item.revision_id,
        item,
      ]),
    ).values(),
  ]
  const revisionChoices = revisionRecords.map((item) => ({
    id: item.revision_id,
    label: revisionLabel(item.revision_id),
  }))
  if (revisionId && !revisionChoices.some((item) => item.id === revisionId)) {
    revisionChoices.unshift({ id: revisionId, label: revisionLabel(revisionId) })
  }

  return (
    <Shell
      workspaceLabel={workspaceId}
      subtitle={`Live API · ${workspace.dataUpdatedAt ? `checked ${new Date(workspace.dataUpdatedAt).toLocaleTimeString()}` : "Connecting"} · Revision-bound shared memory`}
      section={props.location.section}
      revisionId={revisionId}
      revisions={revisionChoices}
      onRevision={(next) => {
        setFollowHead(false)
        go({ revisionId: next, selectedId: null })
      }}
      historical={historical}
      connectionLabel={connectionLabel}
      connectionTone={connectionTone}
      hrefForSection={(section: Section) =>
        hrefFor(new URL(window.location.href), {
          ...props.location,
          section,
          source: "api",
          preview: null,
        })
      }
      onNavigate={props.navigate}
      main={
        props.location.section === "queries" ? (
          <LiveQuery
            location={props.location}
            revisionId={revisionId}
            headRevisionId={headRevisionId}
            token={token}
            canAsk={Boolean(revisionId && token)}
            onCurrent={() => {
              setFollowHead(true)
              go({ section: "queries", revisionId: headRevisionId ?? revisionId })
            }}
          />
        ) : props.location.section === "history" ? (
          <LiveHistory
            workspaceId={workspaceId}
            token={token}
            pending={history.isPending}
            error={history.error}
            onRetry={() => void history.refetch()}
            revisions={revisionRecords.map((item) => ({
              ...item,
              committed_at: item.committed_at ?? "",
            }))}
            hasMore={history.hasNextPage}
            loadingMore={history.isFetchingNextPage}
            onMore={() => void history.fetchNextPage()}
            selected={revisionId}
            onSelect={(next) => {
              setFollowHead(false)
              go({ revisionId: next, section: "history" })
            }}
          />
        ) : (
          <>
            <div className="section-heading">
              <div>
                <span className="eyebrow">Persistent shared context</span>
                <h2 className="page-title">Accepted memory</h2>
                <p className="meta">
                  Inspect what is known, where it came from, and what depends on it.
                </p>
              </div>
              <div className="cluster">
                <button
                  type="button"
                  aria-pressed={view === "graph"}
                  onClick={() => setView("graph")}
                >
                  Graph
                </button>
                <button
                  type="button"
                  aria-pressed={view === "list"}
                  onClick={() => setView("list")}
                >
                  List
                </button>
              </div>
            </div>
            <div className="observer-bar">
              <label>
                <input
                  type="checkbox"
                  checked={followHead}
                  onChange={(e) => setFollowHead(e.target.checked)}
                />{" "}
                Follow current head
              </label>
              <span className="meta">
                {historical
                  ? followHead
                    ? "Loading current head; showing prior snapshot"
                    : "Pinned historical snapshot"
                  : "Current as of last read"}
              </span>
              <button
                type="button"
                onClick={() => {
                  void workspace.refetch()
                  setFollowAttempt((attempt) => attempt + 1)
                  void memory.refetch()
                  void proposals.refetch()
                  void history.refetch()
                }}
              >
                Refresh
              </button>
              <button type="button" onClick={props.onDisconnect}>
                Disconnect
              </button>
            </div>
            {followHead && followError && (
              <p className="callout" role="alert">
                The latest snapshot could not be loaded. The prior revision is retained. Use Refresh
                to retry.
              </p>
            )}
            {memory.error && <Failure error={memory.error} onRetry={() => void memory.refetch()} />}
            {memory.isPending && <Loading label="Loading accepted memory" />}
            {view === "graph" && visibleMemory && (
              <MemoryGraphView
                memory={visibleMemory}
                token={token}
                proposals={proposals.data ?? []}
                onSelect={(id) => go({ selectedId: id })}
              />
            )}
            <LiveQuarantine
              pending={proposals.isPending}
              error={proposals.error}
              onRetry={() => void proposals.refetch()}
              items={proposals.data ?? []}
            />
            {view === "list" && (
              <LiveMemory
                pending={memory.isPending}
                error={memory.error}
                onRetry={() => void memory.refetch()}
                assertions={visibleMemory?.assertions ?? []}
                atoms={visibleMemory?.atoms ?? []}
                selectedId={props.location.selectedId}
                onSelect={(id) => go({ selectedId: id })}
                waiting={Boolean(memory.data && !visibleMemory)}
                canWrite={props.canWrite && !historical}
                workspaceId={workspaceId}
                revisionId={revisionId}
                token={token}
                onCommitted={(next) => go({ revisionId: next, section: "memory" })}
              />
            )}
          </>
        )
      }
      inspector={
        <LiveInspector
          assertion={
            visibleMemory?.assertions.find((item) => item.id === props.location.selectedId) ?? null
          }
          atoms={visibleMemory?.atoms ?? []}
          hash={visibleMemory?.knowledge_hash ?? ""}
        />
      }
    />
  )
}

function LiveQuarantine(props: {
  pending: boolean
  error: unknown
  onRetry: () => void
  items: import("../api/types").ProposalDocument[]
}) {
  if (props.pending) return null
  if (props.error) {
    return (
      <section className="panel">
        <h2 className="section-title">Quarantined submissions</h2>
        <Failure error={props.error} onRetry={props.onRetry} />
      </section>
    )
  }
  if (props.items.length === 0) return null
  return (
    <section className="panel">
      <h2 className="section-title">Quarantined submissions</h2>
      <p className="meta">
        These proposals were checked and not activated. Quarantine does not advance the head.
        {props.items.length >= 50 ? " Showing up to 50 proposals." : ""}
      </p>
      <ul className="memory-list">
        {props.items.map((item) => (
          <li key={item.proposal_id}>
            <div className="memory-row">
              <strong>{item.proposal_id}</strong>
              <span className="meta">
                Base {item.base_revision_id} · {item.reason}
              </span>
              {item.submitted_request?.reason ? <p>{item.submitted_request.reason}</p> : null}
              {item.submitted_request?.mutations?.length ? (
                <code className="formula">
                  {item.submitted_request.mutations.length} mutation(s)
                </code>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

function LiveMemory(props: {
  pending: boolean
  error: unknown
  onRetry: () => void
  assertions: { id: string; formula: Formula; evidence: { excerpt: string }[] }[]
  atoms: { id: string; label: string; meaning: string; scope: string }[]
  selectedId: string | null
  onSelect: (id: string) => void
  waiting: boolean
  canWrite: boolean
  workspaceId: string
  revisionId: string | null
  token: string
  onCommitted: (revisionId: string) => void
}) {
  if (props.pending) return <Loading label="Loading memory" />
  if (props.error) return <Failure error={props.error} onRetry={props.onRetry} />
  if (props.waiting)
    return (
      <p className="callout" role="status">
        Waiting for the selected revision. Older results are not shown under this heading.
      </p>
    )
  return (
    <>
      <div>
        <p className="section-kicker">Memories</p>
        <h2 className="page-title">
          {props.assertions.length === 0
            ? "No accepted memory"
            : `${props.assertions.length} accepted`}
        </h2>
      </div>
      {props.canWrite && props.revisionId ? (
        <AddMemory
          workspaceId={props.workspaceId}
          revisionId={props.revisionId}
          token={props.token}
          atoms={props.atoms}
          onCommitted={props.onCommitted}
        />
      ) : null}
      <ul className="memory-list">
        {props.assertions.map((assertion) => (
          <li key={assertion.id}>
            <button
              className="memory-row"
              type="button"
              aria-current={props.selectedId === assertion.id}
              onClick={() => props.onSelect(assertion.id)}
            >
              <strong>{assertionTitle(assertion.formula, props.atoms)}</strong>
              <code className="formula">{prettyFormula(assertion.formula)}</code>
              <span className="meta">{assertion.evidence[0]?.excerpt}</span>
            </button>
          </li>
        ))}
      </ul>
    </>
  )
}

function AddMemory(props: {
  workspaceId: string
  revisionId: string
  token: string
  atoms: { id: string; label: string }[]
  onCommitted: (revisionId: string) => void
}) {
  const client = useQueryClient()
  const [atomId, setAtomId] = useState(props.atoms[0]?.id ?? "")
  const [negated, setNegated] = useState(false)
  const [reason, setReason] = useState("")
  const [evidenceUri, setEvidenceUri] = useState("")
  const [evidenceExcerpt, setEvidenceExcerpt] = useState("")
  const [observedAt, setObservedAt] = useState("")
  const [notice, setNotice] = useState("")
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID())
  useEffect(() => {
    setIdempotencyKey(crypto.randomUUID())
  }, [atomId, negated, reason, evidenceUri, evidenceExcerpt, observedAt, props.revisionId])
  const mutation = useMutation({
    mutationFn: () =>
      postRevision(
        props.workspaceId,
        {
          expected_revision: props.revisionId,
          idempotency_key: idempotencyKey,
          reason,
          acceptance: "human_confirmed",
          mutations: [
            {
              op: "add",
              assertion: {
                client_ref: "inspector-add",
                formula: negated
                  ? { op: "not", arg: { op: "atom", id: atomId } }
                  : { op: "atom", id: atomId },
                evidence: [
                  {
                    uri: evidenceUri.trim(),
                    excerpt: evidenceExcerpt.trim(),
                    observed_at: new Date(observedAt).toISOString(),
                  },
                ],
              },
            },
          ],
        },
        { token: props.token },
      ),
    onSuccess: async (result) => {
      if (result.status === 201 && result.body.revision_id) {
        await client.invalidateQueries()
        setIdempotencyKey(crypto.randomUUID())
        props.onCommitted(result.body.revision_id)
        setNotice("")
        return
      }
      setNotice(
        result.body.reason ||
          "The service accepted the request without changing the current revision.",
      )
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : "The memory service could not save this."
      setNotice(
        error instanceof ApiError && error.status === 409
          ? `${message} Review the revision, then submit again.`
          : message,
      )
      if (error instanceof ApiError && error.status === 409) setIdempotencyKey(crypto.randomUUID())
    },
  })
  return (
    <form
      className="panel"
      onSubmit={(event) => {
        event.preventDefault()
        mutation.mutate()
      }}
    >
      <h2 className="section-title">Add memory</h2>
      <label className="revision-control">
        <span>Atom</span>
        <select value={atomId} onChange={(event) => setAtomId(event.target.value)}>
          {props.atoms.map((atom) => (
            <option key={atom.id} value={atom.id}>
              {atom.label}
            </option>
          ))}
        </select>
      </label>
      <label className="cluster">
        <input
          type="checkbox"
          checked={negated}
          onChange={(event) => setNegated(event.target.checked)}
        />{" "}
        Assert the negation
      </label>
      <label className="revision-control">
        <span>Reason</span>
        <input
          type="text"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          required
        />
      </label>
      <label className="revision-control">
        <span>Evidence URI</span>
        <input
          type="text"
          required
          maxLength={2048}
          value={evidenceUri}
          onChange={(event) => setEvidenceUri(event.target.value)}
          placeholder="https://… or fixture://…"
        />
      </label>
      <label className="revision-control">
        <span>Evidence excerpt</span>
        <textarea
          required
          maxLength={2000}
          value={evidenceExcerpt}
          onChange={(event) => setEvidenceExcerpt(event.target.value)}
        />
      </label>
      <label className="revision-control">
        <span>Observed at (local time)</span>
        <input
          type="datetime-local"
          required
          value={observedAt}
          onChange={(event) => setObservedAt(event.target.value)}
        />
      </label>
      <p className="meta">
        The observation time is saved in UTC. Evidence records the source; it does not certify its
        factual accuracy.
      </p>
      {notice ? (
        <p className="callout" role="status">
          {notice}
        </p>
      ) : null}
      <button
        className="primary"
        type="submit"
        disabled={
          mutation.isPending ||
          !reason.trim() ||
          !evidenceUri.trim() ||
          !evidenceExcerpt.trim() ||
          !observedAt
        }
      >
        {mutation.isPending ? "Saving…" : "Submit for check"}
      </button>
    </form>
  )
}

function LiveQuery(props: {
  location: AppLocation & { workspaceId: string }
  revisionId: string | null
  headRevisionId?: string
  token: string
  canAsk: boolean
  onCurrent: () => void
}) {
  const [atomId, setAtomId] = useState("release_ready")
  const [negated, setNegated] = useState(false)
  const [result, setResult] = useState<QueryResponse | null>(null)
  const [resultFormula, setResultFormula] = useState<Formula | null>(null)
  const [error, setError] = useState<string>("")
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID())
  useEffect(() => {
    setIdempotencyKey(crypto.randomUUID())
  }, [atomId, negated, props.revisionId])
  const visible =
    result &&
    result.workspace_id === props.location.workspaceId &&
    sameRevision(result.revision_id, props.revisionId)
      ? result
      : null
  const mutation = useMutation({
    mutationFn: (formula: Formula) =>
      postQuery(
        props.location.workspaceId,
        buildCertificateQuery({
          revision_id: props.revisionId ?? "",
          idempotency_key: idempotencyKey,
          query: formula,
        }),
        { token: props.token },
      ),
    onSuccess: (response, submitted) => {
      setError("")
      setResult(response)
      setResultFormula(submitted)
      setIdempotencyKey(crypto.randomUUID())
    },
    onError: (caught) => {
      setResult(null)
      const message =
        caught instanceof ApiError
          ? caught.message
          : "The memory service could not check this query."
      setError(
        caught instanceof ApiError && caught.status === 409
          ? `${message} The question was kept. Review it, then check again.`
          : message,
      )
      if (caught instanceof ApiError && caught.status === 409)
        setIdempotencyKey(crypto.randomUUID())
    },
  })
  const formula: Formula = negated
    ? { op: "not", arg: { op: "atom", id: atomId } }
    : { op: "atom", id: atomId }
  const presentation = visible
    ? presentResult({
        result: visible.result,
        proofStatus: visible.proof_status,
        freshness:
          props.headRevisionId && props.headRevisionId !== visible.revision_id
            ? "HISTORICAL"
            : visible.freshness,
        revisionLabel: revisionLabel(visible.revision_id),
        explanation: visible.explanation,
      })
    : null
  return (
    <>
      <div>
        <p className="section-kicker">Ask about this memory</p>
        <h2 className="page-title">Check</h2>
      </div>
      <form
        className="query-box"
        onSubmit={(event) => {
          event.preventDefault()
          if (props.canAsk) mutation.mutate(formula)
        }}
      >
        <label className="revision-control">
          <span>Atom</span>
          <input type="text" value={atomId} onChange={(event) => setAtomId(event.target.value)} />
        </label>
        <details>
          <summary>Advanced formula</summary>
          <label className="cluster">
            <input
              type="checkbox"
              checked={negated}
              onChange={(event) => setNegated(event.target.checked)}
            />{" "}
            Query the negation
          </label>
        </details>
        {error ? (
          <p className="callout" role="alert">
            {error}
          </p>
        ) : null}
        <button className="primary" type="submit" disabled={!props.canAsk || mutation.isPending}>
          {mutation.isPending ? "Checking…" : "Check"}
        </button>
      </form>
      {result && !visible ? (
        <p className="callout" role="status">
          A result arrived for a different revision and was not shown.
        </p>
      ) : null}
      {presentation && visible ? (
        <ResultCard
          presentation={presentation}
          formulaText={prettyFormula(resultFormula ?? formula)}
          onCheckCurrent={props.onCurrent}
        >
          {visible.proof_status === "VERIFIED" && visible.query_id ? (
            <CertificateDownload
              workspaceId={props.location.workspaceId}
              queryId={visible.query_id}
              token={props.token}
            />
          ) : null}
          <RecordDecision
            key={visible.query_id}
            workspaceId={props.location.workspaceId}
            revisionId={visible.revision_id}
            headRevisionId={props.headRevisionId}
            queryId={visible.query_id}
            result={visible.result}
            proofStatus={visible.proof_status}
            token={props.token}
          />
        </ResultCard>
      ) : null}
      {visible && <QuerySupport result={visible} token={props.token} />}
    </>
  )
}

function RecordDecision(props: {
  workspaceId: string
  revisionId: string
  headRevisionId?: string
  queryId: string
  result: QueryResponse["result"]
  proofStatus: QueryResponse["proof_status"]
  token: string
}) {
  const [note, setNote] = useState("")
  const [idempotencyKey] = useState(() => crypto.randomUUID())
  const atHead = props.headRevisionId === props.revisionId
  const outcome = suggestedDecision(props.result, props.proofStatus)
  const mutation = useMutation({
    mutationFn: () => {
      if (!outcome) throw new Error("unsupported result")
      return postDecision(
        props.workspaceId,
        {
          expected_revision: props.revisionId,
          query_id: props.queryId,
          idempotency_key: idempotencyKey,
          outcome,
          rationale:
            outcome === "PROCEED"
              ? "Query is PROVED at the current revision."
              : "Query is REFUTED at the current revision.",
        },
        { token: props.token },
      )
    },
    onSuccess: (receipt) => setNote(`Recorded ${receipt.outcome} for ${receipt.decision_id}.`),
    onError: (caught) =>
      setNote(caught instanceof ApiError ? caught.message : "Decision could not be recorded."),
  })
  if (!atHead || !outcome) return null
  return (
    <div className="cluster">
      <button
        className="secondary"
        type="button"
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        {mutation.isPending ? "Recording…" : `Record ${outcome} decision`}
      </button>
      {note ? (
        <p className="meta" role="status">
          {note}
        </p>
      ) : null}
    </div>
  )
}

function CertificateDownload(props: { workspaceId: string; queryId: string; token: string }) {
  const [note, setNote] = useState("")
  const [error, setError] = useState("")
  return (
    <div className="cluster">
      <button
        className="secondary"
        type="button"
        onClick={() => {
          void getCertificate(props.workspaceId, props.queryId, { token: props.token }).then(
            (bundle) => {
              const blob = new Blob([`${JSON.stringify(bundle, null, 2)}\n`], {
                type: "application/json",
              })
              const url = URL.createObjectURL(blob)
              const link = document.createElement("a")
              link.href = url
              link.download = `certificate-${props.queryId}.json`
              link.click()
              URL.revokeObjectURL(url)
              setError("")
              setNote("Certificate file downloaded.")
            },
            (caught: unknown) => {
              setNote("")
              setError(
                caught instanceof ApiError
                  ? caught.message
                  : "The certificate could not be downloaded.",
              )
            },
          )
        }}
      >
        Download certificate
      </button>
      {note ? <span role="status">{note}</span> : null}
      {error ? <span role="alert">{error}</span> : null}
    </div>
  )
}

function LiveHistory(props: {
  workspaceId: string
  token: string
  pending: boolean
  error: unknown
  onRetry: () => void
  revisions: {
    revision_id: string
    parent_revision_id?: string | null
    reason: string
    committed_at: string
    actor_label?: string
  }[]
  hasMore: boolean
  loadingMore: boolean
  onMore: () => void
  selected: string | null
  onSelect: (revisionId: string) => void
}) {
  const visible = usePageVisible()
  const impact = useInfiniteQuery({
    queryKey: ["impact", props.workspaceId, props.selected],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ signal, pageParam }) =>
      getRevisionImpact(
        props.workspaceId,
        props.selected ?? "",
        { signal, token: props.token },
        pageParam,
      ),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: Boolean(props.selected),
    refetchInterval: (query) => pollInterval(visible, query.state, 5000),
  })
  const selectedRecord = props.revisions.find((r) => r.revision_id === props.selected)
  const parentId = selectedRecord?.parent_revision_id
  const before = useQuery({
    queryKey: ["memory", props.workspaceId, parentId],
    queryFn: ({ signal }) =>
      getMemory(props.workspaceId, parentId!, { token: props.token, signal }),
    enabled: Boolean(parentId),
  })
  const after = useQuery({
    queryKey: ["memory", props.workspaceId, props.selected],
    queryFn: ({ signal }) =>
      getMemory(props.workspaceId, props.selected!, { token: props.token, signal }),
    enabled: Boolean(props.selected),
  })
  const impactTotal = impact.data?.pages[0]?.total_count ?? 0
  const impactItems = [
    ...new Map(
      (impact.data?.pages.flatMap((p) => p.items) ?? []).map((item) => [item.query_id, item]),
    ).values(),
  ]
  if (props.pending) return <Loading label="Loading history" />
  if (props.error) return <Failure error={props.error} onRetry={props.onRetry} />
  return (
    <>
      <h2 className="page-title">Revisions</h2>
      {props.revisions.length === 0 ? (
        <p>No revisions are recorded.</p>
      ) : (
        <ul className="history-list">
          {props.revisions.map((revision) => (
            <li key={revision.revision_id}>
              <button
                className="history-row"
                type="button"
                aria-current={props.selected === revision.revision_id}
                onClick={() => props.onSelect(revision.revision_id)}
              >
                <strong>
                  {revisionLabel(revision.revision_id)}
                  {revision.actor_label ? ` · ${revision.actor_label}` : ""}
                </strong>
                <span>{revision.reason}</span>
                <span className="meta">{formatTimestamp(revision.committed_at)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {props.hasMore && (
        <button type="button" disabled={props.loadingMore} onClick={props.onMore}>
          Load earlier revisions
        </button>
      )}
      {before.data && after.data && <RevisionComparison before={before.data} after={after.data} />}
      {(before.isError || after.isError) && (
        <p className="callout">
          Revision comparison unavailable. Historical records have not been substituted.
        </p>
      )}
      {impact.isError && <Failure error={impact.error} onRetry={() => void impact.refetch()} />}
      {props.selected && impact.data && impactTotal > 0 ? (
        <section className="panel">
          <h3 className="section-title">Affected prior queries</h3>
          <p className="meta">
            Showing {impactItems.length} of {impactTotal} affected historical result(s) for{" "}
            {revisionLabel(props.selected)}. Recheck these results at the new revision.
          </p>
          <ul className="memory-list">
            {impactItems.map((item) => (
              <li key={item.query_id}>
                <div className="memory-row">
                  <strong>{item.result}</strong>
                  <span className="meta">
                    Query {item.query_id} at {revisionLabel(item.revision_id)} ·{" "}
                    {item.dependency_basis}
                  </span>
                  <span className="meta">
                    Changed support: {item.changed_assertion_ids.join(", ")}
                  </span>
                </div>
              </li>
            ))}
          </ul>
          {impact.hasNextPage && (
            <button
              type="button"
              disabled={impact.isFetchingNextPage}
              onClick={() => void impact.fetchNextPage()}
            >
              Load more affected results
            </button>
          )}
        </section>
      ) : null}
      {impact.isSuccess && impactTotal === 0 && (
        <p className="meta">No affected prior results returned for this revision.</p>
      )}
      <p className="meta">
        Select a revision to inspect history. Impact lists real stored query dependencies when the
        API provides them.
      </p>
    </>
  )
}

function LiveInspector(props: {
  assertion: {
    formula: Formula
    evidence: { uri: string; excerpt: string; observed_at: string }[]
    actor_label?: string
    accepted_at_revision?: string
  } | null
  atoms: { id: string; label: string; meaning: string; scope: string }[]
  hash: string
}) {
  if (!props.assertion) {
    return (
      <>
        <p className="section-kicker">Inspector</p>
        <h2 className="section-title">Evidence</h2>
        <p>Select a memory to see its evidence.</p>
      </>
    )
  }
  const evidence = props.assertion.evidence[0]
  return (
    <>
      <p className="section-kicker">Inspector</p>
      <h2 className="section-title">{assertionTitle(props.assertion.formula, props.atoms)}</h2>
      <code className="formula">{prettyFormula(props.assertion.formula)}</code>
      <p className="evidence">{evidence?.excerpt ?? "No evidence recorded."}</p>
      {evidence ? (
        <p className="meta">
          {evidence.uri} · {formatTimestamp(evidence.observed_at)}
        </p>
      ) : null}
      {props.assertion.actor_label ? (
        <p className="meta">Actor {props.assertion.actor_label}</p>
      ) : null}
      {props.hash ? <p className="meta">Knowledge hash {props.hash}</p> : null}
    </>
  )
}

function Loading(props: { label: string }) {
  return (
    <main className="main" id="content" aria-busy="true">
      <p>{props.label}…</p>
      <div className="skeleton" />
    </main>
  )
}

function Failure(props: { error: unknown; onRetry: () => void }) {
  const message =
    props.error instanceof ApiError
      ? props.error.message
      : "The memory service could not be reached."
  const devHref = import.meta.env.DEV
    ? hrefFor(new URL(window.location.href), {
        source: "development",
        workspaceId: "workspace_demo",
        section: "memory",
        revisionId: "rev_002",
      })
    : null
  return (
    <main className="main" id="content">
      <div className="error-panel" role="alert">
        <h1 className="page-title">Could not load memory</h1>
        <p>{message}</p>
        <button className="primary" type="button" onClick={props.onRetry}>
          Retry
        </button>
        {devHref ? <a href={devHref}>Open development fixtures</a> : null}
      </div>
    </main>
  )
}
