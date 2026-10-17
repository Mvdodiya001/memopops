export type Section = "memory" | "queries" | "history"
export type DataSource = "api" | "development"
export type FixturePreview = "empty" | "error"

export type AppLocation = {
  workspaceId: string | null
  section: Section
  revisionId: string | null
  selectedId: string | null
  source: DataSource
  preview: FixturePreview | null
}

const SECTIONS: readonly Section[] = ["memory", "queries", "history"]

export function parseLocation(url: URL): AppLocation {
  const parts = url.pathname.split("/").filter(Boolean)
  let workspaceId: string | null = null
  let section: Section = "memory"
  if (parts[0] === "w" && parts[1]) {
    workspaceId = decodeURIComponent(parts[1])
    if (isSection(parts[2])) section = parts[2]
  }
  const source: DataSource = url.searchParams.get("source") === "development" ? "development" : "api"
  const previewParam = url.searchParams.get("preview")
  const preview = source === "development" && isPreview(previewParam) ? previewParam : null
  return {
    workspaceId,
    section,
    revisionId: emptyToNull(url.searchParams.get("revision")),
    selectedId: emptyToNull(url.searchParams.get("selected")),
    source,
    preview,
  }
}

export function hrefFor(current: URL, patch: Partial<AppLocation>): string {
  const next: AppLocation = { ...parseLocation(current), ...patch }
  const url = new URL(current.origin)
  url.pathname = next.workspaceId ? `/w/${encodeURIComponent(next.workspaceId)}/${next.section}` : "/"
  if (next.revisionId) url.searchParams.set("revision", next.revisionId)
  if (next.selectedId) url.searchParams.set("selected", next.selectedId)
  if (next.source === "development") url.searchParams.set("source", "development")
  if (next.preview && next.source === "development") url.searchParams.set("preview", next.preview)
  return `${url.pathname}${url.search}`
}

export function isSection(value: string | undefined): value is Section {
  return SECTIONS.includes(value as Section)
}

function isPreview(value: string | null): value is FixturePreview {
  return value === "empty" || value === "error"
}

function emptyToNull(value: string | null): string | null {
  return value ? value : null
}
