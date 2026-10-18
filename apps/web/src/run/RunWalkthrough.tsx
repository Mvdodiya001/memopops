import { useEffect, useMemo, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { getMemory, getQueryResult } from "../api/client"
import { GraphCanvas } from "../components/GraphCanvas"
import { RevisionComparison } from "../components/RevisionComparison"
import { Shell } from "../components/Shell"
import { hrefFor, type AppLocation } from "../model/location"
import { matchesRecordedMemory, projectMemory } from "../visualization/graph"
import {
  CHAPTERS,
  chapterEvents,
  chapterQuery,
  importRun,
  object,
  recordedMemory,
  text,
  type RunData,
} from "./parse"

export function RunWalkthrough({
  run,
  onRun,
  location,
  navigate,
  connection,
}: {
  run: RunData | null
  onRun: (run: RunData | null) => void
  location: AppLocation
  navigate: (href: string) => void
  connection?: { workspaceId: string; token: string }
}) {
  const [chapter, setChapter] = useState(0)
  const [error, setError] = useState("")
  const [pending, setPending] = useState(false)
  const generation = useRef(0)
  const [key, title, caption] = CHAPTERS[chapter]
  const scene = run?.scenes[key]
  const revision = run
    ? ["correction", "resume"].includes(key)
      ? run.corrected
      : run.baseline
    : ""
  const canEnrich = Boolean(run && connection?.workspaceId === run.workspace)
  const snapshot = useQuery({
    queryKey: ["run-memory", run?.workspace, revision],
    queryFn: ({ signal }) =>
      getMemory(run!.workspace, revision, { token: connection?.token, signal }),
    enabled: canEnrich && Boolean(revision),
    retry: false,
  })
  const before = useQuery({
    queryKey: ["run-memory", run?.workspace, run?.baseline],
    queryFn: ({ signal }) =>
      getMemory(run!.workspace, run!.baseline, { token: connection?.token, signal }),
    enabled: canEnrich && Boolean(run?.baseline) && key === "correction",
    retry: false,
  })
  const recorded = useMemo(() => (run ? recordedMemory(run, revision) : null), [run, revision])
  const recordedBefore = useMemo(() => (run ? recordedMemory(run, run.baseline) : null), [run])
  const query = useMemo(() => (run ? chapterQuery(run, key) : null), [run, key])
  const details = useQuery({
    queryKey: ["run-query", run?.workspace, query?.query_id],
    queryFn: ({ signal }) =>
      getQueryResult(run!.workspace, query!.query_id, { token: connection?.token, signal }),
    enabled: canEnrich && Boolean(query?.query_id),
    retry: false,
  })
  const mismatch = Boolean(
    snapshot.data &&
      !matchesRecordedMemory(snapshot.data, recorded, run?.workspace ?? "", revision),
  )
  const beforeMismatch = Boolean(
    before.data &&
      !matchesRecordedMemory(
        before.data,
        recordedBefore,
        run?.workspace ?? "",
        run?.baseline ?? "",
      ),
  )
  const priorMemory = beforeMismatch ? recordedBefore : (before.data ?? recordedBefore)
  const memory = mismatch ? recorded : (snapshot.data ?? recorded)
  const queryMismatch = Boolean(
    details.data &&
      query &&
      (details.data.query_id !== query.query_id ||
        details.data.revision_id !== query.revision_id ||
        details.data.workspace_id !== run?.workspace ||
        details.data.result !== query.result ||
        details.data.proof_status !== query.proof_status ||
        JSON.stringify([...details.data.support_assertion_ids].sort()) !==
          JSON.stringify([...query.support_assertion_ids].sort())),
  )
  const graph = useMemo(() => {
    if (!memory) return null
    const quarantine = object(scene?.quarantine)
    const receipt = run
      ? chapterEvents(run, key).find(
          (e) =>
            e.tool === "record_decision" && e.persisted === true && e.query_id === query?.query_id,
        )
      : undefined
    return projectMemory(memory, {
      query: queryMismatch ? query : (details.data ?? query),
      querySource: details.data && !queryMismatch ? "api" : "recorded-artifact",
      decision: receipt
        ? {
            decision_id: text(receipt.decision_id),
            query_id: text(receipt.query_id),
            revision_id: text(receipt.revision_id),
            outcome: text(receipt.outcome),
            persisted: true,
          }
        : undefined,
      source: snapshot.data && !mismatch ? "api" : "recorded-artifact",
      proposals:
        key === "writer" && quarantine.status === "QUARANTINED" && text(quarantine.proposal_id)
          ? [
              {
                proposal_id: text(quarantine.proposal_id),
                base_revision_id: text(quarantine.base_revision_id) || run!.baseline,
                status: "QUARANTINED",
                reason: text(quarantine.reason) || "Recorded quarantine result",
              },
            ]
          : [],
    })
  }, [memory, query, details.data, queryMismatch, snapshot.data, mismatch, scene, key, run])
  const events = run ? chapterEvents(run, key) : []
  const otherEvents = useMemo(() => {
    if (!run) return []
    const mapped = new Set(
      CHAPTERS.filter(([id]) => run.scenes[id]).flatMap(([id]) => chapterEvents(run, id)),
    )
    return Object.entries(run.journals).flatMap(([file, journal]) =>
      journal.events
        .map((event, index) => ({ file, event, index }))
        .filter(({ event }) => !mapped.has(event)),
    )
  }, [run])
  const decision = object(scene?.decision)
  const mode = text(scene?.mode) || (key === "writer" ? run?.journals["writer.json"]?.mode : "")
  const sceneMode =
    mode === "live_model"
      ? "Live model recorded"
      : mode === "scripted_replay"
        ? "Scripted replay recorded"
        : ["reader", "uncertain", "writer", "resume"].includes(key)
          ? "Mode unavailable"
          : "Service / operator record"
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (
        event.target instanceof Element &&
        event.target.closest("input, textarea, select, button, summary, a")
      )
        return
      if (event.key === "ArrowRight") setChapter((n) => Math.min(8, n + 1))
      if (event.key === "ArrowLeft") setChapter((n) => Math.max(0, n - 1))
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [])
  return (
    <Shell
      workspaceLabel={run?.workspace ?? "Run walkthrough"}
      subtitle={
        run
          ? `Recorded run · Take ${run.take} · ${sceneMode}`
          : "See the decisions behind shared memory."
      }
      section="run"
      revisionId={revision || null}
      revisions={revision ? [{ id: revision, label: revision }] : []}
      onRevision={() => undefined}
      historical={true}
      connectionLabel="Recorded artifacts"
      connectionTone="pending"
      hrefForSection={(section) =>
        hrefFor(new URL(window.location.href), {
          ...location,
          workspaceId: connection?.workspaceId ?? run?.workspace ?? null,
          section,
        })
      }
      onNavigate={navigate}
      inspector={
        <>
          <span className="eyebrow">Recording context</span>
          <h2>Every outcome has a source.</h2>
          <p>
            This view presents a recorded run. API enrichment adds historical details without
            rerunning the agents.
          </p>
          {run && (
            <>
              {otherEvents.length > 0 && (
                <details>
                  <summary>{otherEvents.length} other recorded events</summary>
                  <p className="meta">
                    Source-file order; these events were not assigned to a completed chapter.
                  </p>
                  <ul>
                    {otherEvents.map(({ file, event, index }) => (
                      <li key={`${file}:${index}`}>
                        <span className="meta">
                          {file} · step {index + 1}
                        </span>
                        <p>
                          {text(event.tool)} · {text(event.outcome)} · {text(event.revision_id)}
                        </p>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
              <dl className="context-list">
                <dt>Take</dt>
                <dd>{run.take}</dd>
                <dt>Requested model</dt>
                <dd>{run.requested || "Unspecified"}</dd>
                <dt>Fallback reported</dt>
                <dd>{run.fallback ? "Yes" : "No"}</dd>
                <dt>Enrichment</dt>
                <dd>{canEnrich ? "Matching API workspace" : "Offline / no matching connection"}</dd>
              </dl>
              <details>
                <summary>Source files and limitations</summary>
                <ul>
                  {run.files.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
                {run.warnings.map((w) => (
                  <p key={w} className="meta">
                    {w}
                  </p>
                ))}
              </details>
            </>
          )}
        </>
      }
      main={
        <>
          <div className="run-import">
            <div>
              <span className="eyebrow">Recorded walkthrough</span>
              <h2>{run ? `Take ${run.take}` : "Open the story behind a run"}</h2>
              <p className="meta">
                Select summary.json and the reader/writer journals from one demo take. Files stay in
                this page.
              </p>
            </div>
            <div className="cluster">
              <label className="file-button">
                {pending ? "Reading…" : run ? "Replace recording" : "Open recording"}
                <input
                  type="file"
                  multiple
                  accept=".json,.cypher"
                  disabled={pending}
                  onChange={(e) => {
                    const files = e.target.files
                    if (!files?.length) return
                    const id = ++generation.current
                    setPending(true)
                    setError("")
                    void importRun(files)
                      .then((data) => {
                        if (id === generation.current) {
                          onRun(data)
                          setChapter(0)
                        }
                      })
                      .catch((caught: unknown) => {
                        if (id === generation.current)
                          setError(
                            caught instanceof Error ? caught.message : "Could not read recording.",
                          )
                      })
                      .finally(() => {
                        if (id === generation.current) setPending(false)
                      })
                    e.target.value = ""
                  }}
                />
              </label>
              {run && (
                <button
                  type="button"
                  onClick={() => {
                    generation.current++
                    setPending(false)
                    onRun(null)
                    setError("")
                  }}
                >
                  Clear
                </button>
              )}
            </div>
          </div>
          {error && (
            <p className="callout" role="alert">
              {error}
            </p>
          )}
          {!run ? (
            <div className="run-empty">
              <span className="eyebrow">Memory → reasoning → correction</span>
              <h1>
                Watch knowledge become
                <br />a decision you can trace.
              </h1>
              <p>
                A guided view of accepted facts, checked support, conflicting observations, and the
                reader's next decision.
              </p>
              <div className="story-preview">
                <span>Shared memory</span>
                <span>Supported answer</span>
                <span>Correction</span>
                <span>Recheck</span>
              </div>
              <p className="meta">
                Generate a take with the existing demo runner, then open its artifacts here. No API
                connection is required.
              </p>
            </div>
          ) : (
            <>
              <nav className="chapter-rail" aria-label="Run chapters">
                {CHAPTERS.map(([id, label], i) => (
                  <button
                    type="button"
                    key={id}
                    aria-current={chapter === i ? "step" : undefined}
                    onClick={() => setChapter(i)}
                  >
                    <span>{String(i + 1).padStart(2, "0")}</span>
                    <span>{label}</span>
                    {!run.scenes[id] && <small>Not recorded</small>}
                  </button>
                ))}
              </nav>
              <div className="chapter-heading">
                <div>
                  <span className="eyebrow">
                    Chapter {chapter + 1} / 9 · {sceneMode}
                  </span>
                  <h1>{title}</h1>
                  <p>{caption}</p>
                </div>
                <span className={`pill ${scene ? "tone-neutral" : "tone-pending"}`}>
                  {scene ? "Recorded" : "Not recorded"}
                </span>
              </div>
              {!scene ? (
                <p className="callout">This chapter was not included in the recording.</p>
              ) : (
                <>
                  {(mismatch || queryMismatch || beforeMismatch) && (
                    <p role="alert" className="callout">
                      API records disagree with the recording. Conflicting enrichment is not
                      applied.
                    </p>
                  )}
                  {(snapshot.isError || details.isError) && (
                    <p className="meta">
                      Some API details are unavailable. Recorded outcomes are retained.
                    </p>
                  )}
                  {key === "preflight" && (
                    <div className="outcome-card">
                      <span className="eyebrow">Readiness at the time of the run</span>
                      <h2>{text(scene.health) || "Readiness recorded"}</h2>
                      <code>{text(scene.head_revision_id)}</code>
                      <p>
                        Workspace memory is revision-bound. This recorded readiness result does not
                        report current service health.
                      </p>
                    </div>
                  )}
                  {Object.keys(decision).length > 0 && (
                    <div className={`outcome-card outcome-${text(decision.result).toLowerCase()}`}>
                      <span className="eyebrow">
                        Recorded decision · {text(decision.revision_id)}
                      </span>
                      <h2>
                        {text(decision.result) || "Result unavailable"}
                        <span>
                          {text(decision.choice) === "ship"
                            ? "Proceed"
                            : text(decision.choice) === "hold"
                              ? "Block"
                              : text(decision.choice) === "abstain"
                                ? "Abstain"
                                : "Decision unavailable"}
                        </span>
                      </h2>
                      <p>
                        Certificate: {text(decision.proof_status) || "Not included"} ·{" "}
                        {text(decision.choice) === "abstain"
                          ? "Local journal abstention; no persisted Decision node."
                          : "Reported decision receipt; no external deployment is executed."}
                      </p>
                    </div>
                  )}
                  {key === "writer" && (
                    <div className="flow-steps">
                      <div>
                        <span>01 · Writer</span>
                        <h3>Observation submitted</h3>
                        <p>
                          Writer tool outcomes appear below; writer credentials cannot activate
                          memory.
                        </p>
                      </div>
                      <div>
                        <span>02 · Operator</span>
                        <h3>{text(object(scene.quarantine).status) || "Validation recorded"}</h3>
                        <p>
                          Validation HTTP {String(scene.quarantine_status ?? "unavailable")} · head{" "}
                          {text(scene.head_revision_id)}
                        </p>
                        <p>Quarantined observations remain outside accepted membership.</p>
                      </div>
                    </div>
                  )}
                  {key === "correction" && memory && priorMemory && (
                    <RevisionComparison before={priorMemory} after={memory} />
                  )}
                  {key === "correction" && (
                    <div className="outcome-card">
                      <span className="eyebrow">Dependency impact</span>
                      <h2>
                        {String(object(scene.impact).total_count ?? "Unavailable")} affected
                        result(s)
                      </h2>
                      <p>
                        Results that used changed support need rechecking. This does not declare the
                        old proof false.
                      </p>
                    </div>
                  )}
                  {key === "verify" && (
                    <div className="verification-grid">
                      {[
                        ["Original certificate", scene.valid_exit, 0],
                        ["Modified certificate", scene.tampered_exit, 1],
                      ].map(([label, exit, expected]) => (
                        <div className="outcome-card" key={String(label)}>
                          <span className="eyebrow">Recorded CLI result</span>
                          <h2>{String(label)}</h2>
                          <p className={exit === expected ? "tone-positive" : "tone-conflict"}>
                            Exit {String(exit ?? "unavailable")} ·{" "}
                            {exit === expected
                              ? expected === 0
                                ? "Accepted"
                                : "Rejected"
                              : "Unexpected / incomplete"}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                  {key === "graph" && (
                    <div className="outcome-card">
                      <span className="eyebrow">FalkorDB query scene</span>
                      <h2>
                        {scene.skipped === true
                          ? "Graph query scene skipped"
                          : "Stored relationships, inspected"}
                      </h2>
                      <p>
                        Recorded query row counts:{" "}
                        {Array.isArray(scene.row_counts)
                          ? scene.row_counts.join(" / ")
                          : "not included"}
                        . These are query rows, not graph node totals.
                      </p>
                      {run.cypher && (
                        <details>
                          <summary>Inspect recorded Cypher</summary>
                          <pre>{run.cypher}</pre>
                        </details>
                      )}
                    </div>
                  )}
                  {graph && !["preflight", "verify"].includes(key) ? (
                    <>
                      <GraphCanvas
                        graph={graph}
                        title={
                          key === "resume"
                            ? "Rechecked support"
                            : key === "reader"
                              ? "The support behind the answer"
                              : "Revision and accepted knowledge"
                        }
                      />
                      <p className="meta">
                        {snapshot.data && !mismatch
                          ? "Historical details read from API."
                          : "Journal snapshot: evidence excerpts are not included in these artifacts."}{" "}
                        Relationships are a projection of available records, not a trace of database
                        execution.
                      </p>
                    </>
                  ) : (
                    !["preflight", "verify"].includes(key) && (
                      <p className="callout">
                        A matching snapshot was not included. Connect to this workspace to load
                        historical details.
                      </p>
                    )
                  )}
                  {events.length > 0 && (
                    <details className="event-records">
                      <summary>{events.length} recorded tool events</summary>
                      <ol>
                        {events.map((e, i) => (
                          <li key={i}>
                            <span className="eyebrow">
                              Step {i + 1} · {text(e.tool)}
                            </span>
                            <strong>{text(e.result) || text(e.outcome) || "Recorded"}</strong>
                            <p className="meta">
                              {text(e.detail)} {text(e.revision_id) || text(e.expected_revision_id)}{" "}
                              {text(e.code)}
                            </p>
                          </li>
                        ))}
                      </ol>
                    </details>
                  )}
                </>
              )}
              <div className="chapter-controls">
                <button
                  type="button"
                  disabled={chapter === 0}
                  onClick={() => setChapter((n) => n - 1)}
                >
                  ← Previous
                </button>
                <span className="meta">
                  Recorded run · Take {run.take} · {revision || "Revision unavailable"}
                </span>
                <button
                  type="button"
                  disabled={chapter === 8}
                  onClick={() => setChapter((n) => n + 1)}
                >
                  Next chapter →
                </button>
              </div>
            </>
          )}
        </>
      }
    />
  )
}
