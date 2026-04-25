import { useEffect } from 'react'

export function usePolling(
  fetchFn: () => void,
  interval: number,
  enabled = true,
): void {
  useEffect(() => {
    if (!enabled) return
    fetchFn()
    const id = setInterval(fetchFn, interval)
    return () => clearInterval(id)
  }, [fetchFn, interval, enabled])
}
