import { useId, useMemo, useState } from "react"
import { boundedGraph, layoutGraph, type GraphModel } from "../visualization/graph"

export function GraphCanvas({
  graph,
  title = "Memory relationships",
  selectedKey,
  onSelect,
}: {
  graph: GraphModel
  title?: string
  selectedKey?: string | null
  onSelect?: (key: string) => void
}) {
  const [selection, setSelection] = useState<string | null>(null)
  const [zoom, setZoom] = useState(1)
  const [search, setSearch] = useState("")
  const marker = useId().replace(/:/g, "")
  const selected = selectedKey ?? selection
  const displayed = useMemo(() => boundedGraph(graph, selected), [graph, selected])
  const layout = useMemo(() => layoutGraph(displayed), [displayed])
  const node = graph.nodes.find((n) => n.key === selected)
  const choose = (key: string) => {
    setSelection(key)
    onSelect?.(key)
  }
  return (
    <section className="graph-panel" aria-label={title}>
      <div className="graph-toolbar">
        <div>
          <span className="eyebrow">Relationship view</span>
          <h3>{title}</h3>
        </div>
        <div className="cluster">
          <button
            type="button"
            onClick={() => setZoom((z) => Math.max(0.6, z - 0.2))}
            aria-label="Zoom out"
          >
            −
          </button>
          <span className="meta">{Math.round(zoom * 100)}%</span>
          <button
            type="button"
            onClick={() => setZoom((z) => Math.min(2.5, z + 0.2))}
            aria-label="Zoom in"
          >
            +
          </button>
          <button type="button" onClick={() => setZoom(1)}>
            Fit
          </button>
        </div>
      </div>
      <div className="graph-viewport">
        <svg
          style={{
            width: `${zoom * 100}%`,
            height: layout.height * zoom,
            minWidth: zoom > 1 ? `${zoom * 100}%` : undefined,
          }}
          viewBox={`0 0 ${layout.width} ${layout.height}`}
          role="img"
          aria-label={`${title}. ${displayed.nodes.length} records. Keyboard inspection is available in the record list below.`}
        >
          <defs>
            <marker
              id={marker}
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="5"
              markerHeight="5"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" />
            </marker>
          </defs>
          {displayed.edges.map((edge) => {
            const from = layout.positions.get(edge.from)!,
              to = layout.positions.get(edge.to)!
            const forward = to.x >= from.x
            const x1 = from.x + (forward ? 244 : 0),
              x2 = to.x + (forward ? 0 : 244)
            return (
              <path
                key={edge.key}
                className={`graph-edge ${edge.highlighted || edge.from === selected || edge.to === selected ? "active" : ""} ${edge.relation === "BASED_ON" ? "dashed" : ""}`}
                d={`M${x1},${from.y + 42} C${(x1 + x2) / 2},${from.y + 42} ${(x1 + x2) / 2},${to.y + 42} ${x2},${to.y + 42}`}
                markerEnd={`url(#${marker})`}
              >
                <title>{edge.relation}</title>
              </path>
            )
          })}
          {displayed.nodes.map((item) => {
            const p = layout.positions.get(item.key)!
            return (
              <g
                key={item.key}
                className={`graph-node kind-${item.kind} ${selected === item.key ? "selected" : ""}`}
                transform={`translate(${p.x} ${p.y})`}
                onClick={() => choose(item.key)}
              >
                <title>
                  {item.label} — {item.recordId ?? item.key}
                </title>
                <rect width="244" height="84" rx="12" />
                <text x="16" y="23" className="node-kind">
                  {item.kind.toUpperCase()}
                </text>
                <text x="16" y="47" className="node-label">
                  {item.label.length > 29 ? `${item.label.slice(0, 28)}…` : item.label}
                </text>
                <text x="16" y="68" className="node-id">
                  {(item.recordId ?? "Derived formula view").slice(0, 31)}
                </text>
              </g>
            )
          })}
        </svg>
      </div>
      <div className="graph-legend">
        <span>
          <i className="legend-dot" />
          Accepted records
        </span>
        <span>
          <i className="legend-line" />
          Relationship projection
        </span>
        <span>
          <i className="legend-line support" />
          Selected / query support
        </span>
      </div>
      {displayed.warnings.map((warning, i) => (
        <p className="callout" key={i}>
          {warning}
        </p>
      ))}
      {node ? (
        <div className="graph-detail" aria-live="polite">
          <div>
            <span className="eyebrow">
              {node.kind} ·{" "}
              {node.source === "api"
                ? "API record"
                : node.source === "derived"
                  ? "Derived view"
                  : "Recorded artifact"}
            </span>
            <h3>{node.label}</h3>
            <code>{node.recordId ?? node.key}</code>
          </div>
          <p className="preserve-lines">{node.detail}</p>
          <p className="meta">
            {[
              ...new Set(
                graph.edges
                  .filter((e) => e.from === node.key || e.to === node.key)
                  .map((e) => e.relation),
              ),
            ].join(" · ")}
          </p>
        </div>
      ) : (
        <p className="graph-hint">
          Select a record to inspect its formula, source, and relationships.
        </p>
      )}
      <details className="record-list">
        <summary>Browse all {graph.nodes.length} records and relationships</summary>
        <label>
          Find a record
          <input value={search} onChange={(e) => setSearch(e.target.value)} type="search" />
        </label>
        <ul>
          {graph.nodes
            .filter((n) =>
              `${n.label} ${n.recordId ?? ""}`.toLowerCase().includes(search.toLowerCase()),
            )
            .map((n) => (
              <li key={n.key}>
                <button
                  type="button"
                  aria-pressed={selected === n.key}
                  onClick={() => choose(n.key)}
                >
                  {n.kind} · {n.label}
                </button>
                <span className="meta">
                  {graph.edges
                    .filter((e) => e.from === n.key)
                    .map(
                      (e) =>
                        `${e.relation} → ${graph.nodes.find((x) => x.key === e.to)?.label ?? e.to}`,
                    )
                    .join("; ")}
                </span>
              </li>
            ))}
        </ul>
      </details>
    </section>
  )
}
