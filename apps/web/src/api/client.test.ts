import { afterEach, describe, expect, it, vi } from "vitest"

import source from "./client.ts?raw"
import { ApiError, getMemory } from "./client"

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("api client", () => {
  it("reports a network failure instead of returning fixture data", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")))
    const error = await getMemory("workspace_demo", "rev_002").then(
      () => null,
      (caught: unknown) => caught,
    )
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ code: "NETWORK", status: 0, retryable: true })
  })

  it("keeps fixture records out of the client module", () => {
    expect(source).not.toContain("fixtures")
    expect(source).not.toContain("development")
  })
})
