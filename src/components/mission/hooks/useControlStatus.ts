import { useEffect, useState } from 'react'

export type ControlState =
  | 'drc_ready'
  | 'waiting_for_user'
  | 'disconnected'
  | 'error'
  | 'unavailable'

export const useControlStatus = () => {
  const [controlState, setControlState] = useState<ControlState>('disconnected')
  const [batteryPercent, setBatteryPercent] = useState<number | null>(null)

  useEffect(() => {
    let isMounted = true

    const fetchStatus = async () => {
      try {
        const response = await fetch('/api/control/auth/status')
        if (!response.ok) throw new Error('status')
        const payload = (await response.json()) as { state?: string; error?: string }
        const nextState = (payload.state ?? (payload.error ? 'unavailable' : 'disconnected')) as ControlState
        if (isMounted) setControlState(nextState)
        return nextState
      } catch {
        if (isMounted) setControlState('unavailable')
        return 'unavailable'
      }
    }

    const fetchBattery = async () => {
      try {
        const response = await fetch('/api/telemetry')
        if (!response.ok) throw new Error('telemetry')
        const payload = (await response.json()) as { battery?: { percent?: number } }
        const percent = payload?.battery?.percent
        if (typeof percent === 'number' && Number.isFinite(percent)) {
          const clamped = Math.max(0, Math.min(100, percent))
          if (isMounted) setBatteryPercent(clamped)
        } else if (isMounted) {
          setBatteryPercent(null)
        }
      } catch {
        if (isMounted) setBatteryPercent(null)
      }
    }

    const poll = async () => {
      const state = await fetchStatus()
      if (state === 'drc_ready') {
        await fetchBattery()
      } else if (isMounted) {
        setBatteryPercent(null)
      }
    }

    void poll()
    const timer = window.setInterval(poll, 3000)
    return () => {
      isMounted = false
      window.clearInterval(timer)
    }
  }, [])

  return { controlState, batteryPercent }
}
