import { useEffect, useRef, useState } from "react"

export function ConflictDialog(props: {
  open: boolean
  expectedRevision: string
  proposedTitle: string
  proposedFormula: string
  proposedEvidence: string
  currentTitle: string
  currentFormula: string
  currentEvidence: string
  preview: { leaves: string; enters: string; affected: string; note: string; confirmLabel: string }
  onClose: () => void
  onConfirm: () => void
}) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const previouslyFocused = useRef<HTMLElement | null>(null)
  const [previewing, setPreviewing] = useState(false)

  useEffect(() => {
    if (!props.open) {
      setPreviewing(false)
      return
    }
    previouslyFocused.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const root = dialogRef.current
    if (!root) return
    const focusable = () =>
      Array.from(root.querySelectorAll<HTMLElement>("button, [href], input, select, textarea")).filter((node) => !node.hasAttribute("disabled"))
    focusable()[0]?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault()
        props.onClose()
        return
      }
      if (event.key !== "Tab") return
      const items = focusable()
      if (items.length === 0) return
      const first = items[0]
      const last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("keydown", onKey)
      previouslyFocused.current?.focus()
    }
  }, [props.open, props.onClose, previewing])

  if (!props.open) return null
  return (
    <div className="sheet-backdrop" onMouseDown={props.onClose}>
      <div
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="conflict-title"
        ref={dialogRef}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <h2 id="conflict-title">{previewing ? "Replace this assertion" : "Review conflict"}</h2>
        <p className="meta">Expected revision {props.expectedRevision}. The current memory stays unchanged until a confirmed commit.</p>
        {previewing ? (
          <>
            <p className="callout">Leaves: {props.preview.leaves}</p>
            <p className="callout">Enters: {props.preview.enters}</p>
            <p className="callout">Affected conclusion: {props.preview.affected}</p>
            <p>{props.preview.note}</p>
            <div className="cluster">
              <button className="primary" type="button" onClick={props.onConfirm}>{props.preview.confirmLabel}</button>
              <button className="secondary" type="button" onClick={() => setPreviewing(false)}>Back</button>
            </div>
          </>
        ) : (
          <>
            <section>
              <h3 className="section-title">Proposed</h3>
              <p>{props.proposedTitle}</p>
              <code className="formula">{props.proposedFormula}</code>
              <p className="evidence">{props.proposedEvidence}</p>
            </section>
            <section>
              <h3 className="section-title">Accepted</h3>
              <p>{props.currentTitle}</p>
              <code className="formula">{props.currentFormula}</code>
              <p className="evidence">{props.currentEvidence}</p>
            </section>
            <div className="cluster">
              <button className="secondary" type="button" onClick={props.onClose}>Keep current memory</button>
              <button className="primary" type="button" onClick={() => setPreviewing(true)}>Replace this assertion</button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
