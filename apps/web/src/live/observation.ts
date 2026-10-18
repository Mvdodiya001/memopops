import { useEffect, useState } from "react"

export function usePageVisible() {
  const [visible, setVisible] = useState(() => document.visibilityState === "visible")
  useEffect(() => {
    const update = () => setVisible(document.visibilityState === "visible")
    document.addEventListener("visibilitychange", update)
    return () => document.removeEventListener("visibilitychange", update)
  }, [])
  return visible
}

export function pollInterval(
  visible: boolean,
  state: { status: string; errorUpdateCount: number },
  interval = 3000,
) {
  return visible
    ? state.status === "error"
      ? Math.min(30000, interval * 2 ** Math.min(3, state.errorUpdateCount))
      : interval
    : false
}
