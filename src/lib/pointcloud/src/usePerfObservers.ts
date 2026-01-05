import { useEffect } from 'react'

let lastPerfLogAt = 0

const logPerf = (label: string, duration: number) => {
  const now = performance.now()
  const delta = lastPerfLogAt ? now - lastPerfLogAt : 0
  lastPerfLogAt = now
  const timestamp = new Date().toISOString()
  console.log(
    `[perf] ${timestamp} ${label}: ${duration.toFixed(7)}ms (+${delta.toFixed(7)}ms)`
  )
}

export const usePerfObservers = () => {
  useEffect(() => {
    if (typeof PerformanceObserver === 'undefined') return undefined
    const supported = PerformanceObserver.supportedEntryTypes ?? []

    const observer = new PerformanceObserver((list) => {
      list.getEntries().forEach((entry) => {
        if (entry.entryType === 'gc') {
          logPerf('gc', entry.duration)
        } else if (entry.entryType === 'longtask') {
          logPerf('longtask', entry.duration)
        }
      })
    })

    const entryTypes = []
    if (supported.includes('longtask')) entryTypes.push('longtask')
    if (supported.includes('gc')) entryTypes.push('gc')
    if (entryTypes.length === 0) return undefined
    observer.observe({ entryTypes })

    return () => observer.disconnect()
  }, [])
}
