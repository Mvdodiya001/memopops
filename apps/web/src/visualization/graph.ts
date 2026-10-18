import type { MemoryDocument, QueryResponse, ProposalDocument } from "../api/types"
import { prettyFormula } from "../model/formula"

export type GraphNode = {
  key: string
  kind: "revision" | "assertion" | "formula" | "evidence" | "query" | "proposal" | "decision"
  label: string
  recordId?: string
  detail: string
  revisionId: string
  source: "api" | "recorded-artifact" | "derived"
}
export type GraphEdge = {
  key: string
  from: string
  to: string
  relation: string
  highlighted?: boolean
}
export type GraphModel = { nodes: GraphNode[]; edges: GraphEdge[]; warnings: string[] }
export type SupportQuery = Pick<
  QueryResponse,
  "query_id" | "revision_id" | "result" | "proof_status" | "support_assertion_ids"
> & { workspace_id?: string }

export function projectMemory(
  memory: MemoryDocument,
  options: {
    query?: SupportQuery | null
    querySource?: GraphNode["source"]
    decision?: {
      decision_id: string
      query_id: string
      revision_id: string
      outcome: string
      persisted: boolean
    }
    proposals?: ProposalDocument[]
    formulas?: boolean
    evidence?: boolean
    source?: GraphNode["source"]
  } = {},
): GraphModel {
  const nodes: GraphNode[] = [],
    edges: GraphEdge[] = [],
    warnings: string[] = []
  const base = {
    revisionId: memory.revision_id,
    source: options.source ?? ("api" as GraphNode["source"]),
  }
  const revision = `revision:${memory.revision_id}`
  const edge = (from: string, to: string, relation: string, highlighted = false) =>
    edges.push({ key: `${from}/${relation}/${to}`, from, to, relation, highlighted })
  nodes.push({
    ...base,
    key: revision,
    kind: "revision",
    recordId: memory.revision_id,
    label: "Accepted snapshot",
    detail: `Revision ${memory.revision_id}\nKnowledge hash: ${memory.knowledge_hash || "not included in recording"}`,
  })
  const query = options.query
  const matches =
    query &&
    query.revision_id === memory.revision_id &&
    (!query.workspace_id || query.workspace_id === memory.workspace_id)
  if (query && !matches)
    warnings.push("Query belongs to a different snapshot; support is not overlaid.")
  const evidence = new Map<string, string>(),
    assertions = new Set(memory.assertions.map((a) => a.id))
  for (const item of [...memory.assertions].sort((a, b) => a.id.localeCompare(b.id))) {
    const key = `assertion:${item.id}`
    nodes.push({
      ...base,
      key,
      kind: "assertion",
      recordId: item.id,
      label: prettyFormula(item.formula),
      detail: `${prettyFormula(item.formula)}\nIncluded in revision ${memory.revision_id}\n${item.evidence.length} evidence record(s)`,
    })
    edge(revision, key, "INCLUDES")
    if (options.formulas) {
      const f = `formula:${item.id}`
      nodes.push({
        ...base,
        source: "derived",
        key: f,
        kind: "formula",
        label: prettyFormula(item.formula),
        detail: `Presentation key, not stored Formula ID\n${JSON.stringify(item.formula, null, 2)}`,
      })
      edge(key, f, "ENCODES")
    }
    if (options.evidence !== false)
      for (const source of item.evidence) {
        const e = `evidence:${source.id}`,
          value = JSON.stringify(source)
        if (!evidence.has(source.id)) {
          evidence.set(source.id, value)
          nodes.push({
            ...base,
            key: e,
            kind: "evidence",
            recordId: source.id,
            label: source.excerpt || source.uri,
            detail: `${source.excerpt}\n${source.uri}\nObserved ${source.observed_at}`,
          })
        } else if (evidence.get(source.id) !== value)
          warnings.push(`Conflicting content for evidence ${source.id}.`)
        edge(key, e, "SUPPORTED_BY")
      }
  }
  if (matches) {
    const key = `query:${query.query_id}`
    nodes.push({
      ...base,
      source: options.querySource ?? base.source,
      key,
      kind: "query",
      recordId: query.query_id,
      label: query.result,
      detail: `Result ${query.result}\nCertificate ${query.proof_status}\nRevision ${query.revision_id}`,
    })
    edge(key, revision, "AT_REVISION")
    for (const id of query.support_assertion_ids) {
      if (assertions.has(id))
        edge(
          key,
          `assertion:${id}`,
          "USES_PREMISE",
          ["PROVED", "REFUTED"].includes(query.result) && query.proof_status === "VERIFIED",
        )
      else warnings.push(`Support assertion ${id} is unavailable in this snapshot.`)
    }
  }
  const decision = options.decision
  if (
    decision?.persisted &&
    decision.decision_id &&
    matches &&
    decision.query_id === query.query_id &&
    decision.revision_id === memory.revision_id &&
    ["PROCEED", "BLOCK"].includes(decision.outcome)
  ) {
    const key = `decision:${decision.decision_id}`
    nodes.push({
      ...base,
      source: "recorded-artifact",
      key,
      kind: "decision",
      recordId: decision.decision_id,
      label: decision.outcome,
      detail: `Recorded persisted decision receipt\n${decision.outcome}\nNo external deployment is executed.`,
    })
    edge(key, `query:${query.query_id}`, "BASED_ON")
    edge(key, revision, "AT_REVISION")
  }
  for (const item of options.proposals ?? [])
    if (item.base_revision_id === memory.revision_id) {
      const key = `proposal:${item.proposal_id}`
      nodes.push({
        ...base,
        key,
        kind: "proposal",
        recordId: item.proposal_id,
        label: "Quarantined observation",
        detail: `${item.reason}\nExcluded from accepted memory.\n${JSON.stringify(item.submitted_request?.mutations ?? [], null, 2)}`,
      })
      edge(key, revision, "BASED_ON")
    }
  return { nodes, edges, warnings }
}

export function boundedGraph(graph: GraphModel, selected?: string | null): GraphModel {
  if (graph.nodes.length <= 120 && graph.edges.length <= 240) return graph
  const support = new Set(graph.edges.filter((e) => e.highlighted).flatMap((e) => [e.from, e.to]))
  const priority = (n: GraphNode) =>
    n.key === selected
      ? 0
      : n.kind === "revision" || n.kind === "query"
        ? 1
        : support.has(n.key)
          ? 2
          : 3
  const nodes = [...graph.nodes]
    .sort((a, b) => priority(a) - priority(b) || a.key.localeCompare(b.key))
    .slice(0, 120)
  const keys = new Set(nodes.map((n) => n.key))
  return {
    nodes,
    edges: graph.edges.filter((e) => keys.has(e.from) && keys.has(e.to)).slice(0, 240),
    warnings: [
      ...graph.warnings,
      `Focused view: ${nodes.length} of ${graph.nodes.length} records, up to 240 relationships. Browse all records below.`,
    ],
  }
}

export function layoutGraph(graph: GraphModel) {
  const columns = [
    ["decision"],
    ["revision", "query", "proposal"],
    ["assertion"],
    ["formula"],
    ["evidence"],
  ]
  const active = columns
    .map((kinds) =>
      graph.nodes
        .filter((n) => kinds.includes(n.kind))
        .sort(
          (a, b) => kinds.indexOf(a.kind) - kinds.indexOf(b.kind) || a.key.localeCompare(b.key),
        ),
    )
    .filter((items) => items.length)
  const positions = new Map<string, { x: number; y: number }>()
  active.forEach((items, column) =>
    items.forEach((n, row) => positions.set(n.key, { x: 24 + column * 294, y: 24 + row * 100 })),
  )
  return {
    positions,
    width: Math.max(600, active.length * 294),
    height: Math.max(280, 40 + Math.max(0, ...active.map((items) => items.length)) * 100),
  }
}

export function diffMemory(before: MemoryDocument, after: MemoryDocument) {
  const oldIds = new Set(before.assertions.map((a) => a.id)),
    newIds = new Set(after.assertions.map((a) => a.id))
  return {
    added: after.assertions.filter((a) => !oldIds.has(a.id)),
    removed: before.assertions.filter((a) => !newIds.has(a.id)),
    unchanged: after.assertions.filter((a) => oldIds.has(a.id)),
  }
}

export function matchesRecordedMemory(
  api: MemoryDocument,
  recorded: MemoryDocument | null,
  workspace: string,
  revision: string,
) {
  if (api.workspace_id !== workspace || api.revision_id !== revision) return false
  if (!recorded) return true
  if (recorded.knowledge_hash && recorded.knowledge_hash !== api.knowledge_hash) return false
  const fingerprint = (memory: MemoryDocument) =>
    JSON.stringify(memory.assertions.map((a) => [a.id, prettyFormula(a.formula)]).sort())
  return fingerprint(api) === fingerprint(recorded)
}
