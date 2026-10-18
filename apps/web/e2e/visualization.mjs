import { mkdir, writeFile } from "node:fs/promises"
import { spawn } from "node:child_process"
import { fileURLToPath } from "node:url"
import path from "node:path"
import { setTimeout as delay } from "node:timers/promises"

// Run against visual_harness.py only. All records and credentials here are synthetic.
const root = fileURLToPath(new URL("../../../", import.meta.url))
const fixture = await fetch("http://127.0.0.1:8010/__fixture/visualization")
  .then((response) => response.json())
  .catch(() => ({}))
if (fixture.synthetic_visualization_harness !== true)
  throw new Error("Refusing to write: start the isolated visual_harness.py service on port 8010.")
const output = path.join(root, ".artifacts/frontend-browser")
await mkdir(output, { recursive: true })
const chrome = spawn(
  process.env.CHROME_PATH ?? "google-chrome",
  [
    "--headless=new",
    "--no-sandbox",
    "--disable-gpu",
    "--no-proxy-server",
    "--remote-debugging-port=9334",
    "--remote-allow-origins=*",
    `--user-data-dir=${path.join(output, "chrome-profile")}`,
    "about:blank",
  ],
  { stdio: "ignore" },
)
const base = process.env.E2E_BASE_URL ?? "http://127.0.0.1:4173"
const requests = [],
  errors = []
let socket
try {
  let target
  for (let i = 0; i < 100; i++) {
    try {
      target = await fetch("http://127.0.0.1:9334/json/new?", { method: "PUT" }).then((r) =>
        r.json(),
      )
      break
    } catch {
      await delay(200)
    }
  }
  if (!target) throw new Error("Chrome did not start")
  socket = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true })
    socket.addEventListener("error", reject, { once: true })
  })
  let id = 0
  const pending = new Map()
  socket.addEventListener("message", ({ data }) => {
    const m = JSON.parse(data)
    if (m.method === "Network.requestWillBeSent") requests.push(m.params.request)
    if (m.method === "Runtime.exceptionThrown") errors.push(m.params.exceptionDetails.text)
    const waiter = pending.get(m.id)
    if (waiter) {
      pending.delete(m.id)
      clearTimeout(waiter.timer)
      m.error ? waiter.reject(new Error(m.error.message)) : waiter.resolve(m.result)
    }
  })
  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const n = ++id
      const timer = setTimeout(() => {
        pending.delete(n)
        reject(new Error(`CDP timeout ${method}`))
      }, 20000)
      pending.set(n, { resolve, reject, timer })
      socket.send(JSON.stringify({ id: n, method, params }))
    })
  const evaluate = async (expression) => {
    const r = await send("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true,
    })
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.text)
    return r.result?.value
  }
  const wait = async (expression) => {
    for (let n = 0; n < 100; n++) {
      if (await evaluate(expression)) return
      await delay(150)
    }
    throw new Error(`Timed out: ${expression}\n${await evaluate("document.body.innerText")}`)
  }
  const click = async (tag, text) => {
    const ok = await evaluate(
      `(() => { const node = [...document.querySelectorAll(${JSON.stringify(tag)})].find(n => n.innerText.trim() === ${JSON.stringify(text)}); if (!node) return false; node.click(); return true })()`,
    )
    if (!ok) throw new Error(`Missing ${text}`)
    await delay(80)
  }
  const fill = async (label, value) => {
    const ok = await evaluate(
      `(() => { const node = [...document.querySelectorAll('label')].find(n => n.innerText.trim() === ${JSON.stringify(label)}); const input = node?.querySelector('input'); if (!input) return false; Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, ${JSON.stringify(value)}); input.dispatchEvent(new Event('input', {bubbles:true})); return true })()`,
    )
    if (!ok) throw new Error(`Missing input ${label}`)
  }
  const shot = async (name) => {
    const image = await send("Page.captureScreenshot", { format: "png" })
    await writeFile(path.join(output, `${name}.png`), Buffer.from(image.data, "base64"))
  }
  const viewport = (width, height) =>
    send("Emulation.setDeviceMetricsOverride", {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: false,
    })
  await send("Page.enable")
  await send("Runtime.enable")
  await send("Network.enable")
  await viewport(1440, 900)
  await send("Page.navigate", { url: base })
  await wait("document.body.innerText.includes('Connect to the memory service')")
  await fill("Bearer token", "local-reader-token")
  await click("button", "Connect")
  await wait("document.body.innerText.includes('Accepted memory and its sources')")
  await shot("memory-1440")
  await evaluate(
    "document.querySelector('.graph-node.kind-assertion').dispatchEvent(new MouseEvent('click', {bubbles:true}))",
  )
  await wait("document.body.innerText.includes('Included in revision')")
  await click("a", "Queries")
  await fill("Atom", "release_ready")
  await click("button", "Check")
  await wait(
    "document.body.innerText.includes('Proof verified') && document.body.innerText.includes('Support for this result')",
  )
  await shot("query-support-1440")
  await click("a", "Memory graph")
  const auth = { "Content-Type": "application/json", Authorization: "Bearer local-operator-token" }
  const write = async (body) => {
    const response = await fetch(
      "http://127.0.0.1:8010/api/v1/workspaces/workspace_demo/revisions",
      { method: "POST", headers: auth, body: JSON.stringify(body) },
    )
    const data = await response.json()
    return { ...data, httpStatus: response.status }
  }
  const failure = {
    client_ref: "test-failure",
    formula: { op: "not", arg: { op: "atom", id: "tests_pass" } },
    evidence: [
      {
        uri: "fixture://browser/failure",
        excerpt: "Synthetic browser failure",
        observed_at: "2026-10-18T00:00:00Z",
      },
    ],
  }
  const quarantine = await write({
    expected_revision: "rev_001",
    idempotency_key: crypto.randomUUID(),
    acceptance: "trusted_fixture",
    reason: "Synthetic inconsistent observation",
    mutations: [{ op: "add", assertion: failure }],
  })
  if (quarantine.httpStatus !== 200 || quarantine.status !== "QUARANTINED")
    throw new Error(`Expected quarantine ${JSON.stringify(quarantine)}`)
  await wait("document.body.innerText.includes('Synthetic inconsistent observation')")
  if ((await evaluate("document.querySelector('.revision-control select').value")) !== "rev_001")
    throw new Error("Quarantine changed the visible revision")
  const corrected = await write({
    expected_revision: "rev_001",
    idempotency_key: crypto.randomUUID(),
    acceptance: "trusted_fixture",
    reason: "Synthetic browser correction",
    mutations: [{ op: "replace", target_assertion_id: "as_tests_pass", assertion: failure }],
  })
  if (corrected.httpStatus !== 201)
    throw new Error(`Expected correction ${JSON.stringify(corrected)}`)
  await wait(
    `document.querySelector('.revision-control select').value === ${JSON.stringify(corrected.revision_id)}`,
  )
  await click("a", "History")
  await wait(
    "document.body.innerText.includes('One change. A different decision context.') && document.body.innerText.includes('affected historical result')",
  )
  await shot("history-impact-1440")
  await click("a", "Memory graph")
  await evaluate(
    "(() => { const select = document.querySelector('.revision-control select'); select.value = 'rev_001'; select.dispatchEvent(new Event('change', {bubbles:true})) })()",
  )
  await wait(
    "document.querySelector('.revision-control select').value === 'rev_001' && document.body.innerText.includes('Pinned historical snapshot')",
  )
  const next = await write({
    expected_revision: corrected.revision_id,
    idempotency_key: crypto.randomUUID(),
    acceptance: "trusted_fixture",
    reason: "Synthetic browser new head",
    mutations: [
      {
        op: "add",
        assertion: {
          client_ref: "docs-signed",
          formula: { op: "atom", id: "docs_signed" },
          evidence: failure.evidence,
        },
      },
    ],
  })
  if (next.httpStatus !== 201) throw new Error(`Expected another revision ${JSON.stringify(next)}`)
  await delay(3500)
  if ((await evaluate("document.querySelector('.revision-control select').value")) !== "rev_001")
    throw new Error("Observer replaced a pinned historical revision")
  await evaluate(
    "[...document.querySelectorAll('label')].find(n => n.innerText.includes('Follow current head')).querySelector('input').click()",
  )
  await wait(
    `document.querySelector('.revision-control select').value === ${JSON.stringify(next.revision_id)}`,
  )
  await click("button", "Disconnect")
  await wait("document.body.innerText.includes('Connect to the memory service')")
  await click("a", "Open a recorded walkthrough →")
  await wait("!!document.querySelector('input[type=file]')")
  const start = requests.length
  const importFiles = async (files) => {
    const doc = await send("DOM.getDocument")
    const input = await send("DOM.querySelector", {
      nodeId: doc.root.nodeId,
      selector: "input[type=file]",
    })
    await send("DOM.setFileInputFiles", { nodeId: input.nodeId, files })
  }
  const take = path.join(output, "take-synthetic")
  await importFiles(
    ["summary.json", "reader.json", "reader-docs.json", "writer.json", "graph-queries.cypher"].map(
      (name) => path.join(take, name),
    ),
  )
  await wait("document.body.innerText.includes('Take synthetic-browser')")
  const chapter = async (n) => {
    await evaluate(`document.querySelectorAll('.chapter-rail button')[${n}].click()`)
    await delay(120)
  }
  for (let n = 0; n < 9; n++) {
    await chapter(n)
    await wait(
      `document.querySelector('.chapter-heading').innerText.toUpperCase().includes('CHAPTER ${n + 1} / 9')`,
    )
  }
  await chapter(2)
  await wait(
    "document.body.innerText.includes('PROVED') && document.body.innerText.includes('The support behind the answer')",
  )
  await shot("recorded-reader-1440")
  await chapter(3)
  await wait("document.body.innerText.includes('Local journal abstention')")
  await chapter(4)
  await wait("document.body.innerText.includes('QUARANTINED')")
  await chapter(5)
  await wait("document.body.innerText.includes('One change. A different decision context.')")
  await chapter(6)
  await wait(
    "document.body.innerText.includes('REFUTED') && document.body.innerText.includes('Rechecked support')",
  )
  await chapter(7)
  await wait(
    "document.body.innerText.includes('Exit 0') && document.body.innerText.includes('Exit 1')",
  )
  await chapter(2)
  await click("button", "Focus mode")
  for (const [width, height] of [
    [1920, 1080],
    [1440, 900],
    [1024, 900],
    [390, 844],
  ]) {
    await viewport(width, height)
    await delay(100)
    if (await evaluate("document.documentElement.scrollWidth > innerWidth + 1"))
      throw new Error(`Horizontal overflow at ${width}`)
    await shot(`walkthrough-focus-${width}`)
  }
  await viewport(1440, 900)
  await send("Emulation.setEmulatedMedia", {
    features: [{ name: "prefers-reduced-motion", value: "reduce" }],
  })
  if (
    (await evaluate("getComputedStyle(document.querySelector('button')).transitionDuration")) !==
    "0s"
  )
    throw new Error("Reduced-motion transitions remain enabled")
  await evaluate(
    "document.body.dispatchEvent(new KeyboardEvent('keydown', {key:'ArrowRight', bubbles:true}))",
  )
  await wait(
    "document.querySelector('.chapter-heading').innerText.toUpperCase().includes('CHAPTER 4 / 9')",
  )
  const bad = path.join(output, "summary.json")
  await writeFile(bad, "{bad json")
  await importFiles([bad])
  await wait("document.body.innerText.includes('Invalid JSON')")
  await wait("document.body.innerText.includes('Take synthetic-browser')")
  const mutations = requests
    .slice(start)
    .filter((r) => ["POST", "PUT", "PATCH", "DELETE"].includes(r.method))
  if (mutations.length) throw new Error("Recorded walkthrough issued a mutation request")
  if (errors.length) throw new Error(`Browser exceptions: ${errors.join()}`)
  await writeFile(
    path.join(output, "browser-report.json"),
    JSON.stringify(
      {
        passed: true,
        replayMutationRequests: mutations.length,
        browserExceptions: errors,
        widths: [1920, 1440, 1024, 390],
        source: "synthetic LabSnapshotStore and scripted DemoRunner artifacts",
      },
      null,
      2,
    ),
  )
  console.log(
    "Visualization browser checks passed: live query/support, quarantine polling, head following, history impact, all recorded chapters, malformed import recovery, responsive focus, reduced motion and zero replay mutations.",
  )
} finally {
  socket?.close()
  chrome.kill()
}
