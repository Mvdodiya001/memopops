import { useEffect, useState } from "react"
import { lazy, Suspense } from "react"

import { LiveApp } from "./live/LiveApp"
import { parseLocation } from "./model/location"

const FixtureApp = lazy(() => import("./dev/FixtureApp").then((module) => ({ default: module.FixtureApp })))

export function App() {
  const [href, setHref] = useState(() => window.location.href)
  useEffect(() => {
    const onPop = () => setHref(window.location.href)
    window.addEventListener("popstate", onPop)
    return () => window.removeEventListener("popstate", onPop)
  }, [])
  const location = parseLocation(new URL(href))
  function navigate(next: string, replace = false) {
    window.history[replace ? "replaceState" : "pushState"](null, "", next)
    setHref(window.location.href)
  }
  if (location.source === "development") {
    return (
      <Suspense fallback={<p className="main">Loading development fixtures…</p>}>
        <FixtureApp location={location} navigate={navigate} />
      </Suspense>
    )
  }
  return <LiveApp location={location} navigate={navigate} />
}
