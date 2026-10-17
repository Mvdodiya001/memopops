import { useEffect, useMemo, useState } from "react"

import type { Formula, QueryResponse } from "../api/types"
import { ConflictDialog } from "../components/ConflictDialog"
import { ResultCard } from "../components/ResultCard"
import { Shell } from "../components/Shell"
import {
  DEMO_WORKSPACE_ID,
  FIXTURE_NOTICE,
  HEAD_REVISION_ID,
  memories,
  memoryFor,
  quarantine,
  queryChoices,
  revisions,
  storedQuery,
  workspace,
} from "../fixtures/development"
import { presentResult, revisionLabel } from "../model/copy"
import { assertionDiff, assertionTitle, formatTimestamp, prettyFormula } from "../model/formula"
import { hrefFor, type AppLocation } from "../model/location"

const WORDING = [
  { result: "PROVED", proofStatus: "VERIFIED", freshness: "CURRENT_AS_OF_READ" },
  { result: "REFUTED", proofStatus: "VERIFIED", freshness: "CURRENT_AS_OF_READ" },
  { result: "UNKNOWN", proofStatus: "NOT_REQUESTED", freshness: "CURRENT_AS_OF_READ" },
  { result: "INCONSISTENT_MEMORY", proofStatus: "NOT_REQUESTED", freshness: "CURRENT_AS_OF_READ" },
  { result: "SOLVER_UNKNOWN", proofStatus: "NOT_REQUESTED", freshness: "CURRENT_AS_OF_READ" },
  { result: "PROVED", proofStatus: "BUDGET_EXCEEDED", freshness: "CURRENT_AS_OF_READ" },
  { result: "PROVED", proofStatus: "VERIFIED", freshness: "HISTORICAL" },
] as const

export function FixtureApp(props: {
  location: AppLocation
  navigate: (href: string, replace?: boolean) => void
}) {
  const revisionId = props.location.revisionId && memories[props.location.revisionId] ? props.location.revisionId : HEAD_REVISION_ID
  const location = props.location.workspaceId === DEMO_WORKSPACE_ID && props.location.revisionId === revisionId
    ? props.location
    : { ...props.location, workspaceId: DEMO_WORKSPACE_ID, revisionId }
  const memory = memoryFor(revisionId)
  const [choiceId, setChoiceId] = useState("release_ready")
  const [conflictOpen, setConflictOpen] = useState(false)
  const [downloadNote, setDownloadNote] = useState("")
  const [conflictPreview, setConflictPreview] = useState("")
  const atoms = memory?.atoms ?? []
  const selected = memory?.assertions.find((item) => item.id === location.selectedId) ?? null
  const stored = storedQuery(revisionId, choiceId)
  const historical = revisionId !== HEAD_REVISION_ID

  function go(patch: Partial<AppLocation>, replace = false) {
    const current = new URL(window.location.href)
    props.navigate(hrefFor(current, { ...location, source: "development", ...patch }), replace)
  }

  useEffect(() => {
    if (props.location.workspaceId === DEMO_WORKSPACE_ID && props.location.revisionId === revisionId) return
    const current = new URL(window.location.href)
    props.navigate(hrefFor(current, { ...location, workspaceId: DEMO_WORKSPACE_ID, revisionId, source: "development" }), true)
  }, [location, props, revisionId])

  const parent = revisions.find((item) => item.revision_id === revisionId)?.parent_revision_id
  const diff = useMemo(() => {
    if (!parent) return assertionDiff([], memory?.assertions ?? [])
    return assertionDiff(memories[parent]?.assertions ?? [], memory?.assertions ?? [])
  }, [memory, parent])

  return (
    <>
      <Shell
        banner={<FixtureBanner preview={location.preview} onPreview={(preview) => go({ preview })} />}
        workspaceLabel={workspace.label}
        subtitle={historical ? "Read-only earlier revision" : "Shared memory, with reasons."}
        section={location.section}
        revisionId={revisionId}
        revisions={revisions.map((item) => ({ id: item.revision_id, label: revisionLabel(item.revision_id) }))}
        onRevision={(next) => go({ revisionId: next, selectedId: null })}
        historical={historical}
        connectionLabel="Development fixtures"
        connectionTone="pending"
        hrefForSection={(section) => hrefFor(new URL(window.location.href), { ...location, section, source: "development" })}
        onNavigate={(href) => props.navigate(href)}
        main={
          location.preview === "error" ? (
            <ErrorPreview />
          ) : location.preview === "empty" ? (
            <EmptyPreview />
          ) : location.section === "queries" ? (
            <QuerySection
              choiceId={choiceId}
              onChoice={setChoiceId}
              stored={stored}
              revisionId={revisionId}
              historical={historical}
              downloadNote={downloadNote}
              onDownload={() => {
                if (!stored?.bundle) return
                downloadJson(stored.bundle, `certificate-${revisionId}.json`)
                setDownloadNote("Certificate file downloaded.")
              }}
              onCurrent={() => go({ revisionId: HEAD_REVISION_ID, section: "queries" })}
            />
          ) : location.section === "history" ? (
            <HistorySection
              selectedRevision={revisionId}
              onSelect={(next) => go({ revisionId: next, section: "history" })}
              added={diff.added.map((item) => assertionTitle(item.formula, atoms))}
              removed={diff.removed.map((item) => assertionTitle(item.formula, atoms))}
            />
          ) : (
            <MemorySection
              count={memory?.assertions.length ?? 0}
              assertions={memory?.assertions ?? []}
              atoms={atoms}
              selectedId={selected?.id ?? null}
              canWrite={!historical}
              conflictNote={conflictPreview}
              onSelect={(id) => go({ selectedId: id, section: "memory" })}
              onReview={() => setConflictOpen(true)}
            />
          )
        }
        inspector={
          <Inspector
            selected={selected}
            atoms={atoms}
            stored={location.section === "queries" ? stored : null}
            hash={memory?.knowledge_hash ?? ""}
          />
        }
      />
      <ConflictDialog
        open={conflictOpen}
        expectedRevision={revisionLabel(quarantine.base_revision_id)}
        proposedTitle="Negation of “Integration tests”"
        proposedFormula={prettyFormula(quarantine.proposed_assertion.formula)}
        proposedEvidence={quarantine.proposed_assertion.evidence[0]?.excerpt ?? ""}
        currentTitle="The integration suite passed for release demo-42."
        currentFormula="tests_pass"
        currentEvidence="The integration suite passed in the original report."
        preview={{
          leaves: "The passing integration-test report leaves accepted memory.",
          enters: "The negation of that report enters in the same batch.",
          affected: "Release readiness was proved at revision 1 and is checked again at revision 2.",
          note: "Development fixtures cannot publish a revision. Revision 2 is a separate stored snapshot of that correction.",
          confirmLabel: "Show revision 2",
        }}
        onClose={() => setConflictOpen(false)}
        onConfirm={() => {
          setConflictOpen(false)
          setConflictPreview("Showing the stored revision 2 snapshot. Nothing was published from this browser.")
          go({ revisionId: HEAD_REVISION_ID, section: "memory", selectedId: "as_tests_fail" })
        }}
      />
    </>
  )
}

function FixtureBanner(props: { preview: AppLocation["preview"]; onPreview: (preview: AppLocation["preview"]) => void }) {
  return (
    <div className="fixture-banner" role="note">
      <p>{FIXTURE_NOTICE}</p>
      <div className="banner-actions">
        <button className="secondary" type="button" aria-pressed={props.preview === null} onClick={() => props.onPreview(null)}>Records</button>
        <button className="secondary" type="button" aria-pressed={props.preview === "empty"} onClick={() => props.onPreview("empty")}>Empty preview</button>
        <button className="secondary" type="button" aria-pressed={props.preview === "error"} onClick={() => props.onPreview("error")}>Error preview</button>
      </div>
    </div>
  )
}

function MemorySection(props: {
  count: number
  assertions: { id: string; formula: Formula; evidence: { excerpt: string }[]; accepted_at_revision?: string }[]
  atoms: { id: string; label: string; meaning: string; scope: string }[]
  selectedId: string | null
  canWrite: boolean
  conflictNote: string
  onSelect: (id: string) => void
  onReview: () => void
}) {
  return (
    <>
      <div>
        <p className="section-kicker">Memories</p>
        <h2 className="page-title">{props.count} accepted</h2>
      </div>
      {props.conflictNote ? <p className="callout" role="status">{props.conflictNote}</p> : null}
      <div className="cluster">
        <button className="secondary" type="button" onClick={props.onReview}>Review quarantined proposal</button>
        <button className="primary" type="button" disabled={!props.canWrite} onClick={props.onReview}>
          {props.canWrite ? "Add memory" : "Historical revisions are read-only"}
        </button>
      </div>
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

function QuerySection(props: {
  choiceId: string
  onChoice: (id: string) => void
  stored: ReturnType<typeof storedQuery>
  revisionId: string
  historical: boolean
  downloadNote: string
  onDownload: () => void
  onCurrent: () => void
}) {
  const response = props.stored?.response
  const presentation = response
    ? presentResult({
        result: response.result,
        proofStatus: response.proof_status,
        freshness: props.historical ? "HISTORICAL" : response.freshness,
        revisionLabel: revisionLabel(props.revisionId),
        explanation: response.explanation,
      })
    : null
  return (
    <>
      <div>
        <p className="section-kicker">Ask about this memory</p>
        <h2 className="page-title">Stored results</h2>
      </div>
      <form className="query-box" onSubmit={(event) => event.preventDefault()}>
        <div className="query-row" role="group" aria-label="Development query">
          {queryChoices.map((choice) => (
            <button
              key={choice.id}
              className="choice"
              type="button"
              aria-pressed={props.choiceId === choice.id}
              onClick={() => props.onChoice(choice.id)}
            >
              {choice.label}
            </button>
          ))}
        </div>
        <p className="meta">Checking uses the stored development result for this revision. It does not call the API and does not invent a proof.</p>
      </form>
      {presentation && response ? (
        <ResultCard presentation={presentation} formulaText={response.query ? prettyFormula(response.query) : undefined} onCheckCurrent={props.onCurrent}>
          {props.stored?.steps.length ? (
            <ol className="steps">
              {props.stored.steps.map((step) => <li key={step.clause_id}>{step.text}</li>)}
            </ol>
          ) : null}
          {response.witnesses?.query_true && response.witnesses.query_false ? (
            <WitnessPair truth={response.witnesses.query_true} falsity={response.witnesses.query_false} />
          ) : null}
          {props.stored?.clauses.length ? (
            <details>
              <summary>Formal steps</summary>
              <ClauseTable clauses={props.stored.clauses} />
            </details>
          ) : null}
          <div className="cluster">
            <button className="secondary" type="button" disabled={!props.stored?.bundle} onClick={props.onDownload}>
              Download certificate
            </button>
            {props.downloadNote ? <span role="status">{props.downloadNote}</span> : null}
          </div>
        </ResultCard>
      ) : (
        <p className="callout" role="status">This development fixture has no stored result for that query.</p>
      )}
      <WordingGallery />
    </>
  )
}

function WitnessPair(props: { truth: Record<string, boolean>; falsity: Record<string, boolean> }) {
  return (
    <div className="stack">
      <p className="meta">One witness makes the query true. Another makes it false. Absence is not treated as false.</p>
      <code className="formula">true: {formatWitness(props.truth)}</code>
      <code className="formula">false: {formatWitness(props.falsity)}</code>
    </div>
  )
}

function formatWitness(witness: Record<string, boolean>): string {
  return Object.entries(witness).map(([key, value]) => `${key}=${value ? "true" : "false"}`).join(", ")
}

function ClauseTable(props: { clauses: { id: number; literals: number[]; origin: string; assertion_id?: string; pivot?: number }[] }) {
  return (
    <div className="table-scroll">
      <table>
        <caption className="sr-only">Certificate clauses</caption>
        <thead>
          <tr><th>Step</th><th>Origin</th><th>Literals</th><th>Source</th></tr>
        </thead>
        <tbody>
          {props.clauses.map((clause) => (
            <tr key={clause.id}>
              <td>{clause.id}</td>
              <td>{clause.origin}</td>
              <td>{clause.literals.length ? clause.literals.join(", ") : "empty"}</td>
              <td>{clause.assertion_id ?? (clause.pivot ? `pivot ${clause.pivot}` : "")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function WordingGallery() {
  return (
    <section className="stack" aria-label="Wording preview">
      <div>
        <h2 className="section-title">Wording preview</h2>
        <p className="meta">These cards show status copy. They are not stored results for the selected revision.</p>
      </div>
      {WORDING.map((item) => {
        const presentation = presentResult({ ...item, revisionLabel: "Revision 1" })
        return (
          <article className="gallery-card" key={`${item.result}-${item.proofStatus}-${item.freshness}`}>
            <h3>{presentation.title}</h3>
            <p>{presentation.explanation}</p>
            {presentation.assurance ? <p className={`pill tone-${presentation.tone}`}>{presentation.assurance}</p> : null}
            {presentation.historical ? <p className="pill historical">Earlier revision</p> : null}
          </article>
        )
      })}
    </section>
  )
}

function HistorySection(props: {
  selectedRevision: string
  onSelect: (revisionId: string) => void
  added: string[]
  removed: string[]
}) {
  return (
    <>
      <div>
        <p className="section-kicker">History</p>
        <h2 className="page-title">Revisions</h2>
      </div>
      <ul className="history-list">
        {revisions.map((revision) => (
          <li key={revision.revision_id}>
            <button className="history-row" type="button" aria-current={props.selectedRevision === revision.revision_id} onClick={() => props.onSelect(revision.revision_id)}>
              <strong>{revisionLabel(revision.revision_id)} · {revision.actor_label}</strong>
              <span>{revision.reason}</span>
              <span className="meta">{formatTimestamp(revision.committed_at ?? revision.created_at ?? "")} · {revision.acceptance === "trusted_fixture" ? "Trusted fixture" : "Human confirmed"}</span>
            </button>
          </li>
        ))}
      </ul>
      <div className="panel">
        <h2 className="section-title">Changes in {revisionLabel(props.selectedRevision)}</h2>
        <DiffList label="Added" items={props.added} />
        <DiffList label="Removed" items={props.removed} />
      </div>
    </>
  )
}

function DiffList(props: { label: string; items: string[] }) {
  return (
    <div>
      <h3 className="section-title">{props.label}</h3>
      {props.items.length === 0 ? <p className="meta">None</p> : (
        <ul>{props.items.map((item) => <li key={item}>{item}</li>)}</ul>
      )}
    </div>
  )
}

function Inspector(props: {
  selected: { id: string; formula: Formula; evidence: { uri: string; excerpt: string; observed_at: string }[]; accepted_at_revision?: string; actor_label?: string } | null
  atoms: { id: string; label: string; meaning: string; scope: string }[]
  stored: { response: QueryResponse } | null
  hash: string
}) {
  if (props.stored) {
    const support = props.stored.response.support_assertion_ids
    return (
      <>
        <p className="section-kicker">Inspector</p>
        <h2 className="section-title">Why</h2>
        <p>{props.stored.response.explanation}</p>
        <p className="meta">{support.length ? `Support: ${support.join(", ")}` : "No decisive support set."}</p>
        {isHash(props.stored.response.knowledge_hash) ? <p className="meta">Knowledge hash {props.stored.response.knowledge_hash}</p> : null}
      </>
    )
  }
  if (!props.selected) {
    return (
      <>
        <p className="section-kicker">Inspector</p>
        <h2 className="section-title">Evidence</h2>
        <p>Select a memory to see its meaning, evidence, and revision.</p>
      </>
    )
  }
  const evidence = props.selected.evidence[0]
  return (
    <>
      <p className="section-kicker">Inspector</p>
      <h2 className="section-title">{assertionTitle(props.selected.formula, props.atoms)}</h2>
      <code className="formula">{prettyFormula(props.selected.formula)}</code>
      <p className="evidence">{evidence?.excerpt}</p>
      <p className="meta">{evidence ? `${evidence.uri} · ${formatTimestamp(evidence.observed_at)}` : "No evidence recorded"}</p>
      {props.selected.actor_label ? <p className="meta">Actor {props.selected.actor_label}</p> : null}
      <p className="meta">Accepted in {revisionLabel(props.selected.accepted_at_revision ?? "")}</p>
      {isHash(props.hash) ? <p className="meta">Knowledge hash {props.hash}</p> : null}
    </>
  )
}

function ErrorPreview() {
  return (
    <div className="error-panel" role="alert">
      <h2 className="page-title">Could not load memory</h2>
      <p>This is a development preview of the error screen. Live mode shows this only after a failed API request, and it does not switch to fixture records.</p>
      <button className="primary" type="button">Retry</button>
    </div>
  )
}

function EmptyPreview() {
  return (
    <div>
      <p className="section-kicker">Memories</p>
      <h2 className="page-title">No accepted memory</h2>
      <p>This revision has an empty accepted set. That is different from a failed load.</p>
    </div>
  )
}

function downloadJson(value: unknown, filename: string) {
  const blob = new Blob([`${JSON.stringify(value, null, 2)}\n`], { type: "application/json" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

function isHash(value: string): boolean {
  return /^[0-9a-f]{64}$/.test(value)
}
