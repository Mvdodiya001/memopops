import { useState } from "react"
import type { MouseEvent, ReactNode } from "react"

import type { Section } from "../model/location"

export function Shell(props: {
  banner?: ReactNode
  workspaceLabel: string
  subtitle: string
  section: Section
  revisionId: string | null
  revisions: { id: string; label: string }[]
  onRevision: (revisionId: string) => void
  historical: boolean
  connectionLabel: string
  connectionTone: "ok" | "pending" | "bad"
  hrefForSection: (section: Section) => string
  onNavigate: (href: string) => void
  main: ReactNode
  inspector: ReactNode
}) {
  const [navOpen, setNavOpen] = useState(false)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const toneClass = props.connectionTone === "ok" ? "tone-positive" : props.connectionTone === "bad" ? "tone-conflict" : "tone-pending"

  function follow(event: MouseEvent<HTMLAnchorElement>, href: string) {
    event.preventDefault()
    setNavOpen(false)
    props.onNavigate(href)
  }

  return (
    <>
      <a className="skip" href="#content">Skip to content</a>
      {props.banner}
      <div className="app">
        <nav className={navOpen ? "nav open" : "nav"} aria-label="Workspace">
          <a className="brand" href={props.hrefForSection("memory")} onClick={(event) => follow(event, props.hrefForSection("memory"))}>
            <strong>memopops</strong>
            <span>Shared memory, with reasons.</span>
          </a>
          <ul className="nav-list">
            {(["memory", "queries", "history"] as const).map((section) => (
              <li key={section}>
                <a
                  href={props.hrefForSection(section)}
                  aria-current={props.section === section ? "page" : undefined}
                  onClick={(event) => follow(event, props.hrefForSection(section))}
                >
                  {section === "memory" ? "Memory" : section === "queries" ? "Queries" : "History"}
                </a>
              </li>
            ))}
          </ul>
          <div className="workspace-note">
            <span>Workspace</span>
            <strong>{props.workspaceLabel}</strong>
            <span className={`connection ${toneClass}`}>
              <i aria-hidden="true" />
              {props.connectionLabel}
            </span>
          </div>
        </nav>
        <header className="header">
          <div className="header-copy">
            <h1>{props.workspaceLabel}</h1>
            <p className="meta">{props.subtitle}</p>
          </div>
          <div className="header-actions">
            <button className="menu-button" type="button" aria-expanded={navOpen} onClick={() => setNavOpen((open) => !open)}>
              Menu
            </button>
            <label className="revision-control">
              <span>Revision</span>
              <select
                value={props.revisionId ?? ""}
                onChange={(event) => props.onRevision(event.target.value)}
                disabled={props.revisions.length === 0}
              >
                {props.revisionId === null ? <option value="">Select a revision</option> : null}
                {props.revisions.map((revision) => (
                  <option key={revision.id} value={revision.id}>{revision.label}</option>
                ))}
              </select>
            </label>
            {props.historical ? <span className="pill historical">Earlier revision</span> : <span className="pill tone-neutral">Current</span>}
            <button className="details-button" type="button" aria-expanded={detailsOpen} onClick={() => setDetailsOpen((open) => !open)}>
              Details
            </button>
          </div>
        </header>
        <main className="main" id="content">{props.main}</main>
        <aside className={detailsOpen ? "inspector open" : "inspector"} aria-label="Inspector">
          {props.inspector}
        </aside>
      </div>
    </>
  )
}
