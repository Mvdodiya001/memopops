import type { ReactNode } from "react"

import type { ResultPresentation } from "../model/copy"

export function ResultCard(props: {
  presentation: ResultPresentation
  formulaText?: string
  onCheckCurrent?: () => void
  children?: ReactNode
}) {
  const { presentation } = props
  return (
    <article className="result-card" aria-live="polite">
      <h2>{presentation.title}</h2>
      <p className="lede">{presentation.explanation}</p>
      {presentation.assurance ? <p className={`pill tone-${presentation.tone}`}>{presentation.assurance}</p> : null}
      {props.formulaText ? <code className="formula">{props.formulaText}</code> : null}
      {presentation.historical ? <p className="pill historical">Earlier revision</p> : null}
      {presentation.currentAction && props.onCheckCurrent ? (
        <button className="secondary" type="button" onClick={props.onCheckCurrent}>{presentation.currentAction}</button>
      ) : null}
      {props.children}
    </article>
  )
}
