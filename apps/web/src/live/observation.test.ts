import { describe, expect, it } from "vitest"
import { pollInterval } from "./observation"

describe("read observation policy", () => {
  it("stops hidden-page polling and bounds failure backoff", () => {
    expect(pollInterval(false, { status: "success", errorUpdateCount: 0 })).toBe(false)
    expect(pollInterval(true, { status: "success", errorUpdateCount: 0 })).toBe(3000)
    expect(pollInterval(true, { status: "error", errorUpdateCount: 1 })).toBe(6000)
    expect(pollInterval(true, { status: "error", errorUpdateCount: 20 }, 5000)).toBe(30000)
    expect(pollInterval(true, { status: "success", errorUpdateCount: 20 }, 5000)).toBe(5000)
  })
})
