import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { getMemory, getQueryResult } from "../api/client"
import type { MemoryDocument, ProposalDocument, QueryResponse } from "../api/types"
import { GraphCanvas } from "../components/GraphCanvas"
import { projectMemory } from "../visualization/graph"

export function MemoryGraphView({
  memory,
  token,
  proposals = [],
  onSelect,
}: {
  memory: MemoryDocument
  token: string
  proposals?: ProposalDocument[]
  onSelect?: (id: string) => void
}) {
  const [formulas, setFormulas] = useState(false),
    [evidence, setEvidence] = useState(true)
  const [input, setInput] = useState(""),
    [queryId, setQueryId] = useState("")
  const query = useQuery({
    queryKey: ["known-query", memory.workspace_id, queryId],
    queryFn: ({ signal }) => getQueryResult(memory.workspace_id, queryId, { token, signal }),
    enabled: Boolean(queryId),
  })
  const graph = useMemo(
    () => projectMemory(memory, { query: query.data, proposals, formulas, evidence }),
    [memory, query.data, proposals, formulas, evidence],
  )
  return (
    <>
      <div className="graph-options">
        <div className="cluster">
          <label>
            <input
              type="checkbox"
              checked={evidence}
              onChange={(e) => setEvidence(e.target.checked)}
            />{" "}
            Evidence
          </label>
          <label>
            <input
              type="checkbox"
              checked={formulas}
              onChange={(e) => setFormulas(e.target.checked)}
            />{" "}
            Formula structure
          </label>
        </div>
        <form
          className="cluster"
          onSubmit={(e) => {
            e.preventDefault()
            setQueryId(input.trim())
          }}
        >
          <label className="sr-only" htmlFor="known-query">
            Query ID
          </label>
          <input
            id="known-query"
            placeholder="Open a known query ID"
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <button type="submit">Show support</button>
          {queryId && (
            <button
              type="button"
              onClick={() => {
                setQueryId("")
                setInput("")
              }}
            >
              Clear query
            </button>
          )}
        </form>
      </div>
      {query.isFetching && <p role="status">Loading recorded query…</p>}
      {query.isError && (
        <p role="alert" className="callout">
          This query could not be loaded. Check its ID and workspace.
        </p>
      )}
      <GraphCanvas
        graph={graph}
        title="Accepted memory and its sources"
        onSelect={(key) => {
          if (key.startsWith("assertion:")) onSelect?.(key.slice(10))
        }}
      />
      <p className="meta">
        Projection of API records · {memory.assertions.length} accepted assertions · revision{" "}
        {memory.revision_id}. Query support is a dependency relationship, not a proof-step execution
        trace.
      </p>
    </>
  )
}

export function QuerySupport({ result, token }: { result: QueryResponse; token: string }) {
  const memory = useQuery({
    queryKey: ["memory", result.workspace_id, result.revision_id],
    queryFn: ({ signal }) => getMemory(result.workspace_id, result.revision_id, { token, signal }),
  })
  const graph = useMemo(
    () =>
      memory.data &&
      memory.data.workspace_id === result.workspace_id &&
      memory.data.revision_id === result.revision_id
        ? projectMemory(memory.data, { query: result })
        : null,
    [memory.data, result],
  )
  return graph ? (
    <GraphCanvas graph={graph} title="Support for this result" />
  ) : memory.isError ? (
    <p className="callout">Support snapshot unavailable.</p>
  ) : (
    <p role="status">Loading support snapshot…</p>
  )
}
