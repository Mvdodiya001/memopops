import { afterEach, describe, expect, it, vi } from "vitest"

import source from "./client.ts?raw"
import { ApiError, buildCertificateQuery, getHistory, getMemory, getQueryResult, getRevisionImpact, messageFromPayload } from "./client"

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("api client", () => {
  it("reads known queries and paginated history/impact without issuing mutations", async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [], next_cursor: null }) })
    vi.stubGlobal("fetch", fetcher)
    await getQueryResult("team / one", "query/one", { token: "synthetic-browser-token" })
    await getHistory("demo", undefined, "9")
    await getRevisionImpact("demo", "revision/next", undefined, "query/previous")
    expect(fetcher.mock.calls[0][0]).toContain("team%20%2F%20one/queries/query%2Fone")
    expect(fetcher.mock.calls[1][0]).toContain("before_sequence=9")
    expect(fetcher.mock.calls[2][0]).toContain("before=query%2Fprevious")
    expect(fetcher.mock.calls.every(([, options]) => !options.method && !options.body)).toBe(true)
  })
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

  it("reads the live service error detail and sends solver mode", () => {
    expect(messageFromPayload({ detail: "Revision not found" }, 404).message).toBe("Revision not found")
    expect(messageFromPayload({ detail: "Idempotency key was used for another request" }, 409).code).toBe("CONFLICT")
    expect(messageFromPayload({ detail: [{ msg: "Field required" }] }, 422).message).toBe("Field required")
    expect(messageFromPayload({ detail: { code: "REVISION_CONFLICT", actual_revision: "rev_002" } }, 409).message).toContain("rev_002")
    expect(buildCertificateQuery({
      revision_id: "rev_001",
      idempotency_key: "query-1",
      query: { op: "atom", id: "release_ready" },
    }).proof_mode).toBe("certificate")
  })
})
