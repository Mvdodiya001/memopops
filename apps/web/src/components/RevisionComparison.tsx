import { useMemo } from "react"
import type { MemoryDocument } from "../api/types"
import { diffMemory } from "../visualization/graph"
import { prettyFormula } from "../model/formula"

export function RevisionComparison({
  before,
  after,
}: {
  before: MemoryDocument
  after: MemoryDocument
}) {
  const diff = useMemo(() => diffMemory(before, after), [before, after])
  if (before.workspace_id !== after.workspace_id)
    return <p role="alert">Cannot compare different workspaces.</p>
  return (
    <section className="revision-comparison">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Memory evolves</span>
          <h2>One change. A different decision context.</h2>
        </div>
        <span className="pill tone-neutral">{diff.unchanged.length} unchanged assertions</span>
      </div>
      <div className="comparison-grid">
        <div className="comparison-before">
          <span className="eyebrow">Before · historical snapshot</span>
          <code>{before.revision_id}</code>
          {diff.removed.map((a) => (
            <div className="diff-item removed" key={a.id}>
              <span>Removed from new revision</span>
              <strong>{prettyFormula(a.formula)}</strong>
              <code>{a.id}</code>
            </div>
          ))}
          {!diff.removed.length && <p>No removed assertions.</p>}
        </div>
        <div className="comparison-after">
          <span className="eyebrow">After · selected snapshot</span>
          <code>{after.revision_id}</code>
          {diff.added.map((a) => (
            <div className="diff-item added" key={a.id}>
              <span>Added to new revision</span>
              <strong>{prettyFormula(a.formula)}</strong>
              <code>{a.id}</code>
            </div>
          ))}
          {!diff.added.length && <p>No added assertions.</p>}
        </div>
      </div>
      <p className="meta">
        Historical proofs remain bound to their original premises. Affected conclusions need a new
        check.
      </p>
    </section>
  )
}
