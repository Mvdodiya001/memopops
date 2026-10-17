import { afterEach, describe, expect, it, vi } from "vitest"

import source from "./client.ts?raw"
import { ApiError, buildCertificateQuery, getMemory, messageFromPayload } from "./client"

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
