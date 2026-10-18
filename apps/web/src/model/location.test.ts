import { describe, expect, it } from "vitest"

import { hrefFor, parseLocation } from "./location"

describe("parseLocation", () => {
  it("opens a recorded run without an authenticated workspace and preserves existing routes", () => {
    expect(parseLocation(new URL("http://localhost/run")).section).toBe("run")
    expect(hrefFor(new URL("http://localhost/"), { section: "run" })).toBe("/run")
    expect(parseLocation(new URL("http://localhost/w/demo/memory")).section).toBe("memory")
  })
  it("uses development fixtures only for the explicit source parameter", () => {
    const development = parseLocation(new URL("http://localhost/w/workspace_demo/queries?revision=rev_001&selected=as_api_v2&source=development&preview=empty"))
    expect(development).toMatchObject({
      workspaceId: "workspace_demo",
      section: "queries",
      revisionId: "rev_001",
      selectedId: "as_api_v2",
      source: "development",
      preview: "empty",
    })
    expect(parseLocation(new URL("http://localhost/w/workspace_demo/memory?source=fixture")).source).toBe("api")
    expect(parseLocation(new URL("http://localhost/w/workspace_demo/memory?preview=error")).preview).toBe(null)
  })

  it("round-trips the workspace URL", () => {
    const current = new URL("http://localhost/")
    const href = hrefFor(current, {
      workspaceId: "workspace_demo",
      section: "history",
      revisionId: "rev_002",
      selectedId: "as_tests_fail",
      source: "development",
      preview: null,
    })
    expect(parseLocation(new URL(`http://localhost${href}`))).toMatchObject({
      workspaceId: "workspace_demo",
      section: "history",
      revisionId: "rev_002",
      selectedId: "as_tests_fail",
      source: "development",
    })
  })
})
