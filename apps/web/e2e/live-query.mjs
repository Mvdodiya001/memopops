import { mkdir, writeFile } from "node:fs/promises"
import { spawn } from "node:child_process"
import http from "node:http"
import path from "node:path"
import { setTimeout as delay } from "node:timers/promises"

const baseUrl = process.env.E2E_BASE_URL ?? "http://127.0.0.1:4173"
const chrome = process.env.CHROME_PATH ?? "google-chrome"
const workspaceId = process.env.E2E_WORKSPACE_ID ?? "workspace_demo"
const revisionId = process.env.E2E_REVISION_ID ?? "rev_001"
const token = process.env.E2E_TOKEN ?? "local-reader-token"
const port = 9333
const screenshotDir = new URL("../review/", import.meta.url)

const chromeProcess = spawn(chrome, [
  "--headless=new",
  "--no-sandbox",
  "--disable-gpu",
  "--no-proxy-server",
  `--remote-debugging-port=${port}`,
  "--remote-allow-origins=*",
  "--window-size=1440,900",
  "about:blank",
], { stdio: ["ignore", "ignore", "pipe"] })
let chromeLog = ""
chromeProcess.stderr?.on("data", (chunk) => {
  chromeLog += chunk.toString()
})

async function main() {
try {
  const browser = await waitForBrowser()
  const page = await createPage(browser)
  await navigate(page, `${baseUrl}/`)
  await waitForText(page, "Connect to the memory service")
  await fill(page, "Workspace", workspaceId)
  await fill(page, "Revision", revisionId)
  await fill(page, "Bearer token", token)
  await clickButton(page, "Connect")
  await waitForText(page, "Queries")
  await clickLink(page, "Queries")
  await fill(page, "Atom", "release_ready")
  await clickButton(page, "Check")
  await waitForText(page, "Follows from memory")
  await waitForText(page, "Proof verified")
  const body = await pageText(page)
  if (body.includes("Development fixtures")) {
    throw new Error("Live query showed development fixtures.")
  }
  console.log("e2e passed: release_ready follows from seeded memory")
} catch (error) {
  await mkdir(screenshotDir, { recursive: true }).catch(() => undefined)
  const shot = path.join(screenshotDir.pathname, "e2e-failure.png")
  try {
    const browser = await waitForBrowser()
    const pages = await browser.get("/json")
    const page = pages.find((item) => item.type === "page")
    if (page) {
      const session = await openSession(page.webSocketDebuggerUrl)
      const image = await session.send("Page.captureScreenshot", { format: "png" })
      await writeFile(shot, Buffer.from(image.data, "base64"))
      console.error(`wrote ${shot}`)
      session.close()
    }
  } catch (captureError) {
    console.error("could not capture failure screenshot", captureError)
  }
  throw error
} finally {
  chromeProcess.kill()
}
}

async function waitForBrowser() {
  const started = Date.now()
  while (Date.now() - started < 20000) {
    try {
      return await Devtools.connect(port)
    } catch (error) {
      console.error("devtools", error instanceof Error ? error.message : error)
      await delay(200)
    }
  }
  throw new Error(`Chrome DevTools did not start\n${chromeLog.slice(-500)}`)
}

async function createPage(browser) {
  const created = await browser.put("/json/new?")
  const page = openSession(created.webSocketDebuggerUrl)
  await page.send("Page.enable")
  await page.send("Runtime.enable")
  return page
}

function navigate(page, url) {
  return page.send("Page.navigate", { url })
}

async function waitForText(page, text) {
  const started = Date.now()
  while (Date.now() - started < 15000) {
    const body = await pageText(page)
    if (body.includes(text)) return
    await delay(200)
  }
  const body = await pageText(page)
  throw new Error(`Timed out waiting for ${text}\n${body.slice(0, 1200)}`)
}

async function pageText(page) {
  const result = await page.send("Runtime.evaluate", {
    expression: "document.body ? document.body.innerText : ''",
    returnByValue: true,
  })
  return String(result.result?.value ?? "")
}

async function fill(page, label, value) {
  const expression = `(() => {
    const labels = [...document.querySelectorAll("label")]
    const match = labels.find((node) => node.innerText.includes(${JSON.stringify(label)}))
    const input = match && match.querySelector("input")
    if (!input) return false
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set
    setter.call(input, ${JSON.stringify(value)})
    input.dispatchEvent(new Event("input", { bubbles: true }))
    return true
  })()`
  const result = await page.send("Runtime.evaluate", { expression, returnByValue: true })
  if (result.result?.value !== true) throw new Error(`Could not fill ${label}`)
}

async function clickButton(page, name) {
  await click(page, "button", name)
}

async function clickLink(page, name) {
  await click(page, "a", name)
}

async function click(page, tag, name) {
  const expression = `(() => {
    const node = [...document.querySelectorAll(${JSON.stringify(tag)})].find((item) => item.innerText.trim() === ${JSON.stringify(name)})
    if (!node) return false
    node.click()
    return true
  })()`
  const result = await page.send("Runtime.evaluate", { expression, returnByValue: true })
  if (result.result?.value !== true) throw new Error(`Could not click ${name}`)
}

function openSession(webSocketUrl) {
  return Devtools.session(webSocketUrl)
}

function httpJson(debugPort, pathname, method = "GET") {
  return new Promise((resolve, reject) => {
    const request = http.request({ hostname: "127.0.0.1", port: debugPort, path: pathname, method, timeout: 1000 }, (response) => {
      let body = ""
      response.on("data", (chunk) => { body += chunk })
      response.on("end", () => {
        try {
          resolve(JSON.parse(body))
        } catch (error) {
          reject(error)
        }
      })
    })
    request.on("error", reject)
    request.on("timeout", () => request.destroy(new Error("devtools timeout")))
    request.end()
  })
}

const Devtools = {
  async connect(debugPort) {
    await httpJson(debugPort, "/json/version")
    return {
      get(pathname) {
        return httpJson(debugPort, pathname)
      },
      put(pathname) {
        return httpJson(debugPort, pathname, "PUT")
      },
    }
  },
  session(url) {
    const socket = new WebSocket(url)
    let nextId = 1
    const pending = new Map()
    const opened = new Promise((resolve, reject) => {
      socket.addEventListener("open", () => resolve())
      socket.addEventListener("error", () => reject(new Error("devtools socket failed")))
    })
    socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data)
      const waiter = pending.get(message.id)
      if (!waiter) return
      pending.delete(message.id)
      if (message.error) waiter.reject(new Error(message.error.message))
      else waiter.resolve(message.result)
    })
    return {
      async send(method, params = {}) {
        await opened
        const id = nextId++
        const result = new Promise((resolve, reject) => pending.set(id, { resolve, reject }))
        socket.send(JSON.stringify({ id, method, params }))
        return result
      },
      close() {
        socket.close()
      },
    }
  },
}

await main()
