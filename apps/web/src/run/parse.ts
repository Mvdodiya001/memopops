import type { Formula, MemoryDocument } from "../api/types"
import type { SupportQuery } from "../visualization/graph"

export type Obj = Record<string, unknown>
export const CHAPTERS = [
  ["preflight", "Ready to remember", "A workspace and a consistent starting point."],
  ["memory", "Shared memory", "Accepted assertions, preserved with their sources."],
  ["reader", "An answer with reasons", "Trace the reader's result to its accepted premises."],
  ["uncertain", "Unknown stays unknown", "Missing knowledge is a reason to abstain."],
  [
    "writer",
    "A conflict, contained",
    "Writer access and operator validation are separate safeguards.",
  ],
  [
    "correction",
    "Correct the premise",
    "A new revision preserves history and exposes affected support.",
  ],
  [
    "resume",
    "Recheck before acting",
    "A resumed reader checks the new head before recording a decision.",
  ],
  [
    "verify",
    "Check the certificate",
    "Recorded independent checker results for original and modified certificates.",
  ],
  [
    "graph",
    "Why the graph matters",
    "Membership, provenance, and query dependencies are connected records.",
  ],
] as const
export type RunData = {
  workspace: string
  take: string
  baseline: string
  corrected: string
  requested: string
  fallback: boolean
  scenes: Record<string, Obj>
  journals: Record<string, { mode: string; events: Obj[] }>
  files: string[]
  cypher: string
  warnings: string[]
}
const RESULTS = ["PROVED", "REFUTED", "UNKNOWN", "INCONSISTENT_MEMORY", "SOLVER_UNKNOWN"]
const PROOFS = ["VERIFIED", "NOT_REQUESTED", "BUDGET_EXCEEDED", "FAILED"]
export function object(value: unknown): Obj {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Obj) : {}
}
export function text(value: unknown): string {
  return typeof value === "string" ? value : ""
}
export function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : []
}
function checkTree(value: unknown, depth = 0): void {
  if (depth > 80) throw new Error("The recording is nested too deeply.")
  if (typeof value === "string" && value.length > 20_000)
    throw new Error("A recording field is too long.")
  if (Array.isArray(value)) {
    if (value.length > 5000) throw new Error("A recording array is too large.")
    value.forEach((v) => checkTree(v, depth + 1))
  } else if (value && typeof value === "object")
    Object.values(value).forEach((v) => checkTree(v, depth + 1))
}
export function parseFormula(value: unknown, depth = 0): Formula {
  if (depth > 64) throw new Error("Formula exceeds the display depth limit.")
  const f = object(value)
  if (f.op === "atom" && typeof f.id === "string" && f.id.length > 0 && f.id.length <= 128)
    return { op: "atom", id: f.id }
  if (f.op === "not") return { op: "not", arg: parseFormula(f.arg, depth + 1) }
  if (
    ["and", "or", "implies", "iff"].includes(text(f.op)) &&
    Array.isArray(f.args) &&
    f.args.length === 2
  )
    return {
      op: f.op as "and" | "or" | "implies" | "iff",
      args: [parseFormula(f.args[0], depth + 1), parseFormula(f.args[1], depth + 1)],
    }
  throw new Error("The recording contains an invalid Boolean formula.")
}
export function parseRunFiles(files: { name: string; content: string }[]): RunData {
  if (files.length > 12) throw new Error("Choose at most 12 files from one take.")
  if (new Set(files.map((f) => f.name)).size !== files.length)
    throw new Error("Duplicate filenames. Choose files from one take only.")
  const parsed = new Map<string, unknown>()
  let total = 0
  for (const f of files) {
    const bytes = new TextEncoder().encode(f.content).length
    total += bytes
    if (bytes > 5 * 1024 * 1024 || total > 20 * 1024 * 1024)
      throw new Error("Recording exceeds the 5 MiB per-file or 20 MiB total limit.")
    if (f.name.endsWith(".json")) {
      let value: unknown
      try {
        value = JSON.parse(f.content)
      } catch {
        throw new Error(`Invalid JSON in ${f.name}.`)
      }
      checkTree(value)
      parsed.set(f.name, value)
    }
  }
  const summary = object(parsed.get("summary.json"))
  if (!text(summary.workspace_id) || !Object.keys(object(summary.scenes)).length)
    throw new Error("Choose a summary.json containing a workspace and recorded scenes.")
  const workspace = text(summary.workspace_id)
  const scenes: Record<string, Obj> = Object.create(null) as Record<string, Obj>
  for (const [key] of CHAPTERS)
    if (key in object(summary.scenes)) {
      const raw = object(object(summary.scenes)[key])
      if (!Object.keys(raw).length) throw new Error(`Invalid ${key} scene.`)
      scenes[key] = raw
    }
  const baseline =
    text(summary.baseline_revision_id) ||
    text(scenes.preflight?.head_revision_id) ||
    text(scenes.memory?.revision_id)
  const corrected = text(scenes.correction?.revision_id)
  if (baseline && text(scenes.memory?.revision_id) && baseline !== scenes.memory.revision_id)
    throw new Error("Baseline revision does not match the memory scene.")
  const journals: RunData["journals"] = Object.create(null) as RunData["journals"]
  let count = 0
  for (const name of ["reader.json", "reader-docs.json", "writer.json"])
    if (parsed.has(name)) {
      const journal = object(parsed.get(name))
      if (journal.workspace_id !== workspace) throw new Error(`Workspace mismatch in ${name}.`)
      if (!["live_model", "scripted_replay"].includes(text(journal.mode)))
        throw new Error(`Unsupported journal mode in ${name}.`)
      if (!Array.isArray(journal.events)) throw new Error(`Missing event array in ${name}.`)
      count += journal.events.length
      if (count > 2000) throw new Error("Recording exceeds 2,000 events.")
      const events = journal.events.map((v) => {
        const e = object(v)
        if (!Object.keys(e).length) throw new Error(`Invalid event in ${name}.`)
        if (e.result !== undefined && !RESULTS.includes(text(e.result)))
          throw new Error("Unsupported logical result.")
        if (e.proof_status !== undefined && !PROOFS.includes(text(e.proof_status)))
          throw new Error("Unsupported proof status.")
        if (Array.isArray(e.assertions)) {
          const ids = e.assertions.map((a) => text(object(a).id))
          if (new Set(ids).size !== ids.length)
            throw new Error("Duplicate assertion IDs in a snapshot.")
          e.assertions.forEach((a) => {
            const item = object(a)
            if (!text(item.id)) throw new Error("Missing assertion ID.")
            parseFormula(item.formula)
          })
        }
        return e
      })
      journals[name] = { mode: text(journal.mode), events }
    }
  const bindings = new Map<string, string>()
  const queryFields = new Map<string, Obj>()
  const assertionFields = new Map<string, string>()
  for (const journal of Object.values(journals))
    for (const e of journal.events) {
      if (
        e.support_assertion_ids !== undefined &&
        (!Array.isArray(e.support_assertion_ids) ||
          e.support_assertion_ids.some((id) => typeof id !== "string"))
      )
        throw new Error("Invalid query support IDs.")
      if (Array.isArray(e.assertions))
        for (const raw of e.assertions) {
          const a = object(raw),
            key = `${text(e.revision_id)}:${text(a.id)}`,
            formula = JSON.stringify(parseFormula(a.formula))
          if (assertionFields.has(key) && assertionFields.get(key) !== formula)
            throw new Error("Conflicting assertions for one immutable snapshot.")
          assertionFields.set(key, formula)
        }
    }
  const bind = (v: unknown) => {
    const e = object(v),
      query = text(e.query_id),
      revision = text(e.revision_id)
    if (e.result !== undefined && !RESULTS.includes(text(e.result)))
      throw new Error("Unsupported logical result.")
    if (e.proof_status !== undefined && !PROOFS.includes(text(e.proof_status)))
      throw new Error("Unsupported proof status.")
    if (query && revision) {
      if (bindings.has(query) && bindings.get(query) !== revision)
        throw new Error("A query is bound to conflicting revisions.")
      bindings.set(query, revision)
      const fields = queryFields.get(query) ?? {}
      for (const field of ["result", "proof_status", "support_assertion_ids"])
        if (e[field] !== undefined) {
          const value = field === "support_assertion_ids" ? [...strings(e[field])].sort() : e[field]
          if (
            fields[field] !== undefined &&
            JSON.stringify(fields[field]) !== JSON.stringify(value)
          )
            throw new Error("Conflicting outcomes for one query.")
          fields[field] = value
        }
      queryFields.set(query, fields)
    }
  }
  Object.values(journals)
    .flatMap((j) => j.events)
    .forEach(bind)
  Object.values(scenes).forEach((s) => {
    bind(s.decision)
    if (s.mode !== undefined && !["live_model", "scripted_replay"].includes(text(s.mode)))
      throw new Error("Unsupported scene mode.")
  })
  const warnings = [
    "Imported outcomes are recorded reports, not independently authenticated by this browser.",
    "Step order is recorded; no cross-session event timestamps are available.",
  ]
  if (!journals["reader.json"])
    warnings.push("Reader journal missing: detailed steps and offline memory may be unavailable.")
  return {
    workspace,
    take: String(summary.take ?? "Unnamed").slice(0, 128),
    baseline,
    corrected,
    requested: text(summary.requested_model_mode),
    fallback: summary.fallback_used === true,
    scenes,
    journals,
    files: files.map((f) => f.name),
    cypher: files.find((f) => f.name === "graph-queries.cypher")?.content ?? "",
    warnings,
  }
}

export async function importRun(files: FileList | File[]): Promise<RunData> {
  const selected = Array.from(files)
  if (
    selected.length > 12 ||
    selected.some((f) => f.size > 5 * 1024 * 1024) ||
    selected.reduce((n, f) => n + f.size, 0) > 20 * 1024 * 1024
  )
    throw new Error("Select at most 12 files, 5 MiB each, and 20 MiB in total.")
  return parseRunFiles(
    await Promise.all(selected.map(async (f) => ({ name: f.name, content: await f.text() }))),
  )
}

export function recordedMemory(run: RunData, revision: string): MemoryDocument | null {
  const snapshots = Object.values(run.journals)
    .flatMap((j) => j.events)
    .filter(
      (e) =>
        e.tool === "inspect_memory" && e.revision_id === revision && Array.isArray(e.assertions),
    )
  const snapshot = snapshots.at(-1)
  if (!snapshot) return null
  return {
    workspace_id: run.workspace,
    revision_id: revision,
    knowledge_hash: revision === run.baseline ? text(run.scenes.memory?.knowledge_hash) : "",
    semantics_version: "boolean-v1",
    atoms: strings(snapshot.atom_ids).map((id) => ({
      id,
      label: id,
      meaning: id,
      scope: run.workspace,
    })),
    assertions: (snapshot.assertions as unknown[]).map((v) => {
      const a = object(v)
      return { id: text(a.id), formula: parseFormula(a.formula), evidence: [] }
    }),
  }
}

export function chapterEvents(run: RunData, chapter: string): Obj[] {
  if (chapter === "writer") return run.journals["writer.json"]?.events ?? []
  if (chapter === "uncertain") return run.journals["reader-docs.json"]?.events ?? []
  if (chapter !== "reader" && chapter !== "resume") return []
  const queryId = text(object(run.scenes[chapter]?.decision).query_id)
  return (run.journals["reader.json"]?.events ?? []).filter((e) => {
    if (e.query_id === queryId && queryId) return true
    if (chapter === "resume")
      return (
        e.code === "REVISION_CONFLICT" || Boolean(run.corrected && e.revision_id === run.corrected)
      )
    return e.tool === "inspect_memory" && e.revision_id === run.baseline
  })
}

export function chapterQuery(run: RunData, chapter: string): SupportQuery | null {
  const decision = object(run.scenes[chapter]?.decision)
  const event = chapterEvents(run, chapter).find(
    (e) => e.tool === "query_conclusion" && e.query_id === decision.query_id,
  )
  if (!event || !RESULTS.includes(text(event.result)) || !PROOFS.includes(text(event.proof_status)))
    return null
  return {
    query_id: text(event.query_id),
    workspace_id: run.workspace,
    revision_id: text(event.revision_id),
    result: event.result as SupportQuery["result"],
    proof_status: event.proof_status as SupportQuery["proof_status"],
    support_assertion_ids: strings(event.support_assertion_ids),
  }
}
