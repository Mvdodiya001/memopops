import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"

import {
  ApiError,
  buildCertificateQuery,
  getCertificate,
  getHealthReady,
  getHistory,
  getMemory,
  getProposals,
  getWorkspace,
  listWorkspaces,
  postDecision,
  postQuery,
  postRevision,
} from "../api/client"
import type { Formula, QueryResponse } from "../api/types"
import { ResultCard } from "../components/ResultCard"
import { Shell } from "../components/Shell"
import { presentResult, revisionLabel, sameRevision } from "../model/copy"
import { assertionTitle, formatTimestamp, prettyFormula } from "../model/formula"
import { hrefFor, type AppLocation, type Section } from "../model/location"

type Session = {
  workspaceId: string
  token: string
  canWrite: boolean
}

export function LiveApp(props: {
  location: AppLocation
  navigate: (href: string, replace?: boolean) => void
}) {
  const [session, setSession] = useState<Session | null>(null)
  if (!session || session.workspaceId !== props.location.workspaceId) {
    return <ConnectForm location={props.location} navigate={props.navigate} onConnect={setSession} />
  }
  return (
    <WorkspaceScreen
      location={{ ...props.location, workspaceId: session.workspaceId }}
      navigate={props.navigate}
      token={session.token}
      canWrite={session.canWrite}
    />
  )
}

function ConnectForm(props: {
  location: AppLocation
  navigate: (href: string, replace?: boolean) => void
  onConnect: (session: Session) => void
}) {
  const [workspaceId, setWorkspaceId] = useState(props.location.workspaceId ?? "workspace_demo")
  const [revisionId, setRevisionId] = useState(props.location.revisionId ?? "rev_001")
  const [token, setToken] = useState("")
  const [pending, setPending] = useState(false)
  const [error, setError] = useState("")
  return (
    <main className="main" id="content">
      <h1 className="page-title">memopops</h1>
      <p>Shared memory, with reasons.</p>
      <form
        className="panel"
        onSubmit={(event) => {
          event.preventDefault()
          setPending(true)
          setError("")
          void listWorkspaces({ token }).then(async (workspaces) => {
            const match = workspaces.find((item) => item.workspace_id === workspaceId) ?? workspaces[0]
            if (!match) {
              setError("This token is not authorized for a workspace.")
              return
            }
            const details = await getWorkspace(match.workspace_id, { token })
            props.onConnect({
              workspaceId: details.workspace_id,
              token,
              canWrite: details.capabilities?.can_write_memory === true,
            })
            props.navigate(hrefFor(new URL(window.location.href), {
              workspaceId: details.workspace_id,
              revisionId: revisionId || details.head_revision_id,
              section: props.location.section,
              source: "api",
              preview: null,
            }))
          }).catch((caught: unknown) => {
            setError(caught instanceof ApiError ? caught.message : "The memory service could not be reached.")
          }).finally(() => setPending(false))
        }}
      >
        <h2 className="section-title">Connect to the memory service</h2>
        <p className="meta">The bearer token stays in this page only. Development fixtures are not used if this request fails.</p>
        <label className="revision-control">
          <span>Workspace</span>
          <input type="text" value={workspaceId} onChange={(event) => setWorkspaceId(event.target.value)} required />
        </label>
        <label className="revision-control">
          <span>Revision</span>
          <input type="text" value={revisionId} onChange={(event) => setRevisionId(event.target.value)} required />
        </label>
        <label className="revision-control">
          <span>Bearer token</span>
          <input type="password" value={token} onChange={(event) => setToken(event.target.value)} autoComplete="off" required />
        </label>
        {error ? <p className="callout" role="alert">{error}</p> : null}
        <button className="primary" type="submit" disabled={pending}>{pending ? "Connecting…" : "Connect"}</button>
      </form>
    </main>
  )
}

function WorkspaceScreen(props: {
  location: AppLocation & { workspaceId: string }
  navigate: (href: string, replace?: boolean) => void
  token: string
  canWrite: boolean
}) {
  const workspaceId = props.location.workspaceId
  const token = props.token
  const health = useQuery({
    queryKey: ["health", "ready"],
    queryFn: ({ signal }) => getHealthReady({ signal }),
    refetchInterval: () => (document.visibilityState === "visible" ? 3000 : false),
  })
  const revisionId = props.location.revisionId
  const memory = useQuery({
    queryKey: ["memory", workspaceId, revisionId],
    queryFn: ({ signal }) => getMemory(workspaceId, revisionId ?? "", { signal, token }),
    enabled: Boolean(revisionId),
  })
  const history = useQuery({
    queryKey: ["history", workspaceId],
    queryFn: ({ signal }) => getHistory(workspaceId, { signal, token }),
  })
  const proposals = useQuery({
    queryKey: ["proposals", workspaceId],
    queryFn: ({ signal }) => getProposals(workspaceId, { signal, token }),
  })

  function go(patch: Partial<AppLocation>) {
    props.navigate(hrefFor(new URL(window.location.href), { ...props.location, source: "api", preview: null, ...patch }))
  }

  const workspace = useQuery({
    queryKey: ["workspace", workspaceId],
    queryFn: ({ signal }) => getWorkspace(workspaceId, { signal, token }),
  })
  const headRevisionId = workspace.data?.head_revision_id
  const historical = Boolean(revisionId && headRevisionId && revisionId !== headRevisionId)
  const visibleMemory = memory.data && sameRevision(memory.data.revision_id, revisionId) ? memory.data : null
  const connectionTone = health.isError ? "bad" : health.isSuccess ? "ok" : "pending"
  const connectionLabel = health.isError ? "Unavailable" : health.isSuccess ? "Connected" : "Checking connection"
  const revisionChoices = (history.data?.revisions ?? []).map((item) => ({ id: item.revision_id, label: revisionLabel(item.revision_id) }))
  if (revisionId && !revisionChoices.some((item) => item.id === revisionId)) {
    revisionChoices.unshift({ id: revisionId, label: revisionLabel(revisionId) })
  }

  return (
    <Shell
      workspaceLabel={workspaceId}
      subtitle="Shared memory, with reasons."
      section={props.location.section}
      revisionId={revisionId}
      revisions={revisionChoices}
      onRevision={(next) => go({ revisionId: next, selectedId: null })}
      historical={historical}
      connectionLabel={connectionLabel}
      connectionTone={connectionTone}
      hrefForSection={(section: Section) => hrefFor(new URL(window.location.href), { ...props.location, section, source: "api", preview: null })}
      onNavigate={props.navigate}
      main={
        props.location.section === "queries" ? (
          <LiveQuery
            location={props.location}
            revisionId={revisionId}
            headRevisionId={headRevisionId}
            token={token}
            canAsk={Boolean(revisionId && token)}
            onCurrent={() => go({ section: "queries" })}
          />
        ) : props.location.section === "history" ? (
          <LiveHistory
            pending={history.isPending}
            error={history.error}
            onRetry={() => void history.refetch()}
            revisions={(history.data?.revisions ?? []).map((item) => ({ ...item, committed_at: item.committed_at ?? "" }))}
            selected={revisionId}
            onSelect={(next) => go({ revisionId: next, section: "history" })}
          />
        ) : (
          <>
            <LiveQuarantine
              pending={proposals.isPending}
              error={proposals.error}
              onRetry={() => void proposals.refetch()}
              items={proposals.data ?? []}
            />
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
          </>
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
      <p className="meta">These proposals were checked and not activated. Head memory is unchanged.</p>
      <ul className="memory-list">
        {props.items.map((item) => (
          <li key={item.proposal_id}>
            <div className="memory-row">
              <strong>{item.proposal_id}</strong>
              <span className="meta">Base {item.base_revision_id} · {item.reason}</span>
              {item.submitted_request?.reason ? <p>{item.submitted_request.reason}</p> : null}
              {item.submitted_request?.mutations?.length ? (
                <code className="formula">{item.submitted_request.mutations.length} mutation(s)</code>
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
  if (props.waiting) return <p className="callout" role="status">Waiting for the selected revision. Older results are not shown under this heading.</p>
  return (
    <>
      <div>
        <p className="section-kicker">Memories</p>
        <h2 className="page-title">{props.assertions.length === 0 ? "No accepted memory" : `${props.assertions.length} accepted`}</h2>
      </div>
      {props.canWrite && props.revisionId ? (
        <AddMemory workspaceId={props.workspaceId} revisionId={props.revisionId} token={props.token} atoms={props.atoms} onCommitted={props.onCommitted} />
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
  token: string
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
    }, { token: props.token }),
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
      const message = error instanceof ApiError ? error.message : "The memory service could not save this."
      setNotice(error instanceof ApiError && error.status === 409 ? `${message} Review the revision, then submit again.` : message)
      if (error instanceof ApiError && error.status === 409) setIdempotencyKey(crypto.randomUUID())
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
  headRevisionId?: string
  token: string
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
    mutationFn: (formula: Formula) => postQuery(props.location.workspaceId, buildCertificateQuery({
      revision_id: props.revisionId ?? "",
      idempotency_key: idempotencyKey,
      query: formula,
    }), { token: props.token }),
    onSuccess: (response) => {
      setError("")
      setResult(response)
      setIdempotencyKey(crypto.randomUUID())
    },
    onError: (caught) => {
      setResult(null)
      const message = caught instanceof ApiError ? caught.message : "The memory service could not check this query."
      setError(caught instanceof ApiError && caught.status === 409 ? `${message} The question was kept. Review it, then check again.` : message)
      if (caught instanceof ApiError && caught.status === 409) setIdempotencyKey(crypto.randomUUID())
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
        <ResultCard presentation={presentation} formulaText={prettyFormula(formula)} onCheckCurrent={props.onCurrent}>
          {visible.proof_status === "VERIFIED" && visible.query_id ? (
            <CertificateDownload workspaceId={props.location.workspaceId} queryId={visible.query_id} token={props.token} />
          ) : null}
          <RecordDecision
            workspaceId={props.location.workspaceId}
            revisionId={visible.revision_id}
            headRevisionId={props.headRevisionId}
            queryId={visible.query_id}
            result={visible.result}
            token={props.token}
          />
        </ResultCard>
      ) : null}
    </>
  )
}

function RecordDecision(props: {
  workspaceId: string
  revisionId: string
  headRevisionId?: string
  queryId: string
  result: QueryResponse["result"]
  token: string
}) {
  const [note, setNote] = useState("")
  const atHead = props.headRevisionId === props.revisionId
  const outcome = props.result === "PROVED" ? "PROCEED" : props.result === "REFUTED" ? "BLOCK" : null
  const mutation = useMutation({
    mutationFn: () => {
      if (!outcome) throw new Error("unsupported result")
      return postDecision(props.workspaceId, {
        expected_revision: props.revisionId,
        query_id: props.queryId,
        idempotency_key: crypto.randomUUID(),
        outcome,
        rationale: outcome === "PROCEED"
          ? "Query is PROVED at the current revision."
          : "Query is REFUTED at the current revision.",
      }, { token: props.token })
    },
    onSuccess: (receipt) => setNote(`Recorded ${receipt.outcome} for ${receipt.decision_id}.`),
    onError: (caught) => setNote(caught instanceof ApiError ? caught.message : "Decision could not be recorded."),
  })
  if (!atHead || !outcome) return null
  return (
    <div className="cluster">
      <button className="secondary" type="button" disabled={mutation.isPending} onClick={() => mutation.mutate()}>
        {mutation.isPending ? "Recording…" : `Record ${outcome} decision`}
      </button>
      {note ? <p className="meta" role="status">{note}</p> : null}
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
          void getCertificate(props.workspaceId, props.queryId, { token: props.token }).then((bundle) => {
            const blob = new Blob([`${JSON.stringify(bundle, null, 2)}\n`], { type: "application/json" })
            const url = URL.createObjectURL(blob)
            const link = document.createElement("a")
            link.href = url
            link.download = `certificate-${props.queryId}.json`
            link.click()
            URL.revokeObjectURL(url)
            setError("")
            setNote("Certificate file downloaded.")
          }, (caught: unknown) => {
            setNote("")
            setError(caught instanceof ApiError ? caught.message : "The certificate could not be downloaded.")
          })
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

