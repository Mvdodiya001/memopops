import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"

import {
  ApiError,
  getHealthReady,
  getHistory,
  getMemory,
  getWorkspace,
  listWorkspaces,
  postQuery,
  postRevision,
} from "../api/client"
import type { Formula, QueryResponse } from "../api/types"
import { ResultCard } from "../components/ResultCard"
import { Shell } from "../components/Shell"
import { presentResult, revisionLabel, sameRevision } from "../model/copy"
import { assertionTitle, formatTimestamp, prettyFormula } from "../model/formula"
import { hrefFor, type AppLocation, type Section } from "../model/location"

export function LiveApp(props: {
  location: AppLocation
  navigate: (href: string, replace?: boolean) => void
}) {
  if (!props.location.workspaceId) return <WorkspaceGate navigate={props.navigate} />
  return <WorkspaceScreen location={{ ...props.location, workspaceId: props.location.workspaceId }} navigate={props.navigate} />
}

function WorkspaceGate(props: { navigate: (href: string, replace?: boolean) => void }) {
  const workspaces = useQuery({ queryKey: ["workspaces"], queryFn: ({ signal }) => listWorkspaces(signal) })
  if (workspaces.isPending) return <Loading label="Loading workspaces" />
  if (workspaces.isError) return <Failure error={workspaces.error} onRetry={() => void workspaces.refetch()} />
  const items = workspaces.data
  if (items.length === 1) {
    const only = items[0]
    return <Redirect note="Opening the authorized workspace." href={hrefFor(new URL(window.location.href), { workspaceId: only.workspace_id, section: "memory" })} navigate={props.navigate} />
  }
  return (
    <main className="main" id="content">
      <h1 className="page-title">memopops</h1>
      <p>Shared memory, with reasons.</p>
      {items.length === 0 ? <p className="callout">No workspace is authorized for this session.</p> : (
        <ul className="memory-list">
          {items.map((item) => (
            <li key={item.workspace_id}>
              <a href={hrefFor(new URL(window.location.href), { workspaceId: item.workspace_id, section: "memory" })}>{item.label}</a>
            </li>
          ))}
        </ul>
      )}
    </main>
  )
}

function WorkspaceScreen(props: {
  location: AppLocation & { workspaceId: string }
  navigate: (href: string, replace?: boolean) => void
}) {
  const workspaceId = props.location.workspaceId
  const health = useQuery({
    queryKey: ["health", "ready"],
    queryFn: ({ signal }) => getHealthReady(signal),
    refetchInterval: () => (document.visibilityState === "visible" ? 3000 : false),
  })
  const workspace = useQuery({
    queryKey: ["workspace", workspaceId],
    queryFn: ({ signal }) => getWorkspace(workspaceId, signal),
  })
  const revisionId = props.location.revisionId ?? workspace.data?.head_revision_id ?? null
  const memory = useQuery({
    queryKey: ["memory", workspaceId, revisionId],
    queryFn: ({ signal }) => getMemory(workspaceId, revisionId ?? "", signal),
    enabled: Boolean(revisionId),
  })
  const history = useQuery({
    queryKey: ["history", workspaceId],
    queryFn: ({ signal }) => getHistory(workspaceId, signal),
  })

  useEffect(() => {
    if (!props.location.revisionId && workspace.data?.head_revision_id) {
      props.navigate(hrefFor(new URL(window.location.href), { revisionId: workspace.data.head_revision_id }), true)
    }
  }, [props, workspace.data?.head_revision_id])

  function go(patch: Partial<AppLocation>) {
    props.navigate(hrefFor(new URL(window.location.href), { ...props.location, source: "api", preview: null, ...patch }))
  }

  if (workspace.isPending) {
    return <Loading label="Loading workspace" />
  }
  if (workspace.isError) return <Failure error={workspace.error} onRetry={() => void workspace.refetch()} />
  const current = workspace.data
  const historical = Boolean(revisionId && current.head_revision_id && revisionId !== current.head_revision_id)
  const visibleMemory = memory.data && sameRevision(memory.data.revision_id, revisionId) ? memory.data : null
  const connectionTone = health.isError ? "bad" : health.isSuccess ? "ok" : "pending"
  const connectionLabel = health.isError ? "Unavailable" : health.isSuccess ? "Connected" : "Checking connection"

  return (
    <Shell
      workspaceLabel={current.label}
      subtitle={historical ? "Read-only earlier revision" : "Shared memory, with reasons."}
      section={props.location.section}
      revisionId={revisionId}
      revisions={(history.data?.revisions ?? []).map((item) => ({ id: item.revision_id, label: revisionLabel(item.revision_id) }))}
      onRevision={(next) => go({ revisionId: next, selectedId: null })}
      historical={historical}
      connectionLabel={connectionLabel}
      connectionTone={connectionTone}
      hrefForSection={(section: Section) => hrefFor(new URL(window.location.href), { ...props.location, section, source: "api", preview: null })}
      onNavigate={props.navigate}
      main={
        props.location.section === "queries" ? (
          <LiveQuery location={props.location} revisionId={revisionId} canAsk={Boolean(revisionId)} onCurrent={() => go({ revisionId: current.head_revision_id, section: "queries" })} />
        ) : props.location.section === "history" ? (
          <LiveHistory
            pending={history.isPending}
            error={history.error}
            onRetry={() => void history.refetch()}
            revisions={history.data?.revisions ?? []}
            selected={revisionId}
            onSelect={(next) => go({ revisionId: next, section: "history" })}
          />
        ) : (
          <LiveMemory
            pending={memory.isPending}
            error={memory.error}
            onRetry={() => void memory.refetch()}
            assertions={visibleMemory?.assertions ?? []}
            atoms={visibleMemory?.atoms ?? []}
            selectedId={props.location.selectedId}
            onSelect={(id) => go({ selectedId: id })}
            waiting={Boolean(memory.data && !visibleMemory)}
            canWrite={current.capabilities?.can_write_memory === true && !historical}
            workspaceId={workspaceId}
            revisionId={revisionId}
            onCommitted={(next) => go({ revisionId: next, section: "memory" })}
          />
        )
      }
      inspector={
        <LiveInspector
          assertion={visibleMemory?.assertions.find((item) => item.id === props.location.selectedId) ?? null}
          atoms={visibleMemory?.atoms ?? []}
          hash={visibleMemory?.knowledge_hash ?? ""}
        />
      }
    />
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
  onCommitted: (revisionId: string) => void
}) {
  if (props.pending) return <Loading label="Loading memory" />
  if (props.error) return <Failure error={props.error} onRetry={props.onRetry} />
  if (props.waiting) return <p className="callout" role="status">Waiting for the selected revision. Older results are not shown under this heading.</p>
  return (
    <>
      <div>
        <p className="section-kicker">Memories</p>
        <h2 className="page-title">{props.assertions.length === 0 ? "No accepted memory" : `${props.assertions.length} accepted`}</h2>
      </div>
      {props.canWrite && props.revisionId ? (
        <AddMemory workspaceId={props.workspaceId} revisionId={props.revisionId} atoms={props.atoms} onCommitted={props.onCommitted} />
      ) : null}
      <ul className="memory-list">
        {props.assertions.map((assertion) => (
          <li key={assertion.id}>
            <button className="memory-row" type="button" aria-current={props.selectedId === assertion.id} onClick={() => props.onSelect(assertion.id)}>
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
  atoms: { id: string; label: string }[]
  onCommitted: (revisionId: string) => void
}) {
  const client = useQueryClient()
  const [atomId, setAtomId] = useState(props.atoms[0]?.id ?? "")
  const [negated, setNegated] = useState(false)
  const [reason, setReason] = useState("")
  const [notice, setNotice] = useState("")
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID())
  useEffect(() => {
    setIdempotencyKey(crypto.randomUUID())
  }, [atomId, negated, reason, props.revisionId])
  const mutation = useMutation({
    mutationFn: () => postRevision(props.workspaceId, {
      expected_revision: props.revisionId,
      idempotency_key: idempotencyKey,
      reason,
      acceptance: "human_confirmed",
      mutations: [{
        op: "add",
        assertion: {
          client_ref: "inspector-add",
          formula: negated ? { op: "not", arg: { op: "atom", id: atomId } } : { op: "atom", id: atomId },
          evidence: [],
        },
      }],
    }),
    onSuccess: async (result) => {
      if (result.status === 201 && result.body.revision_id) {
        await client.invalidateQueries()
        setIdempotencyKey(crypto.randomUUID())
        props.onCommitted(result.body.revision_id)
        setNotice("")
        return
      }
      setNotice(result.body.reason || "The service accepted the request without changing the current revision.")
    },
    onError: (error) => {
      setNotice(error instanceof ApiError ? error.message : "The memory service could not save this.")
    },
  })
  return (
    <form className="panel" onSubmit={(event) => { event.preventDefault(); mutation.mutate() }}>
      <h2 className="section-title">Add memory</h2>
      <label className="revision-control">
        <span>Atom</span>
        <select value={atomId} onChange={(event) => setAtomId(event.target.value)}>
          {props.atoms.map((atom) => <option key={atom.id} value={atom.id}>{atom.label}</option>)}
        </select>
      </label>
      <label className="cluster"><input type="checkbox" checked={negated} onChange={(event) => setNegated(event.target.checked)} /> Assert the negation</label>
      <label className="revision-control">
        <span>Reason</span>
        <input type="text" value={reason} onChange={(event) => setReason(event.target.value)} required />
      </label>
      {notice ? <p className="callout" role="status">{notice}</p> : null}
      <button className="primary" type="submit" disabled={mutation.isPending || !reason.trim()}>{mutation.isPending ? "Saving…" : "Submit for check"}</button>
    </form>
  )
}

function LiveQuery(props: {
  location: AppLocation & { workspaceId: string }
  revisionId: string | null
  canAsk: boolean
  onCurrent: () => void
}) {
  const [atomId, setAtomId] = useState("release_ready")
  const [negated, setNegated] = useState(false)
  const [result, setResult] = useState<QueryResponse | null>(null)
  const [error, setError] = useState<string>("")
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID())
  useEffect(() => {
    setIdempotencyKey(crypto.randomUUID())
  }, [atomId, negated, props.revisionId])
  const visible = result && sameRevision(result.revision_id, props.revisionId) ? result : null
  const mutation = useMutation({
    mutationFn: (formula: Formula) => postQuery(props.location.workspaceId, {
      revision_id: props.revisionId ?? "",
      idempotency_key: idempotencyKey,
      query: formula,
      proof_mode: "certificate",
    }),
    onSuccess: (response) => {
      setError("")
      setResult(response)
      setIdempotencyKey(crypto.randomUUID())
    },
    onError: (caught) => {
      setResult(null)
      setError(caught instanceof ApiError ? caught.message : "The memory service could not check this query.")
    },
  })
  const formula: Formula = negated ? { op: "not", arg: { op: "atom", id: atomId } } : { op: "atom", id: atomId }
  const presentation = visible
    ? presentResult({
        result: visible.result,
        proofStatus: visible.proof_status,
        freshness: visible.freshness,
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
      <form className="query-box" onSubmit={(event) => { event.preventDefault(); if (props.canAsk) mutation.mutate(formula) }}>
        <label className="revision-control">
          <span>Atom</span>
          <input type="text" value={atomId} onChange={(event) => setAtomId(event.target.value)} />
        </label>
        <details>
          <summary>Advanced formula</summary>
          <label className="cluster"><input type="checkbox" checked={negated} onChange={(event) => setNegated(event.target.checked)} /> Query the negation</label>
        </details>
        {error ? <p className="callout" role="alert">{error}</p> : null}
        <button className="primary" type="submit" disabled={!props.canAsk || mutation.isPending}>{mutation.isPending ? "Checking…" : "Check"}</button>
      </form>
      {result && !visible ? <p className="callout" role="status">A result arrived for a different revision and was not shown.</p> : null}
      {presentation && visible ? (
        <ResultCard presentation={presentation} formulaText={prettyFormula(visible.query)} onCheckCurrent={props.onCurrent} />
      ) : null}
    </>
  )
}

function LiveHistory(props: {
  pending: boolean
  error: unknown
  onRetry: () => void
  revisions: { revision_id: string; reason: string; committed_at: string; actor_label?: string }[]
  selected: string | null
  onSelect: (revisionId: string) => void
}) {
  if (props.pending) return <Loading label="Loading history" />
  if (props.error) return <Failure error={props.error} onRetry={props.onRetry} />
  return (
    <>
      <h2 className="page-title">Revisions</h2>
      {props.revisions.length === 0 ? <p>No revisions are recorded.</p> : (
        <ul className="history-list">
          {props.revisions.map((revision) => (
            <li key={revision.revision_id}>
              <button className="history-row" type="button" aria-current={props.selected === revision.revision_id} onClick={() => props.onSelect(revision.revision_id)}>
                <strong>{revisionLabel(revision.revision_id)}{revision.actor_label ? ` · ${revision.actor_label}` : ""}</strong>
                <span>{revision.reason}</span>
                <span className="meta">{formatTimestamp(revision.committed_at)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="meta">Assertion diffs appear when both snapshots are loaded. This view does not invent them from the revision list.</p>
    </>
  )
}

function LiveInspector(props: {
  assertion: { formula: Formula; evidence: { uri: string; excerpt: string; observed_at: string }[]; actor_label?: string; accepted_at_revision?: string } | null
  atoms: { id: string; label: string; meaning: string; scope: string }[]
  hash: string
}) {
  if (!props.assertion) {
    return <><p className="section-kicker">Inspector</p><h2 className="section-title">Evidence</h2><p>Select a memory to see its evidence.</p></>
  }
  const evidence = props.assertion.evidence[0]
  return (
    <>
      <p className="section-kicker">Inspector</p>
      <h2 className="section-title">{assertionTitle(props.assertion.formula, props.atoms)}</h2>
      <code className="formula">{prettyFormula(props.assertion.formula)}</code>
      <p className="evidence">{evidence?.excerpt ?? "No evidence recorded."}</p>
      {evidence ? <p className="meta">{evidence.uri} · {formatTimestamp(evidence.observed_at)}</p> : null}
      {props.assertion.actor_label ? <p className="meta">Actor {props.assertion.actor_label}</p> : null}
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
  const message = props.error instanceof ApiError ? props.error.message : "The memory service could not be reached."
  const devHref = import.meta.env.DEV ? hrefFor(new URL(window.location.href), { source: "development", workspaceId: "workspace_demo", section: "memory", revisionId: "rev_002" }) : null
  return (
    <main className="main" id="content">
      <div className="error-panel" role="alert">
        <h1 className="page-title">Could not load memory</h1>
        <p>{message}</p>
        <button className="primary" type="button" onClick={props.onRetry}>Retry</button>
        {devHref ? <a href={devHref}>Open development fixtures</a> : null}
      </div>
    </main>
  )
}

function Redirect(props: { href: string; note: string; navigate: (href: string, replace?: boolean) => void }) {
  useEffect(() => {
    props.navigate(props.href, true)
  }, [props])
  return <p className="main">{props.note}</p>
}
