import { useEffect, useState } from 'react'
import { type DrcState, useDrcStateMachine } from '../state/drcStateMachine'

export type ControlState = DrcState

export const useControlStatus = () => {
  const { drcState, updateStatus, markUnavailable } = useDrcStateMachine()
  const [batteryPercent, setBatteryPercent] = useState<number | null>(null)

  useEffect(() => {
    let isMounted = true

    const fetchStatus = async () => {
      try {
        const response = await fetch('/api/drone/status')
        if (!response.ok) throw new Error('status')
        const payload = (await response.json()) as {
          drone?: {
            drc_state?: string | null
            last_error?: string | null
          }
          error?: string
        }
        const rawState = payload.drone?.drc_state ?? 'disconnected'
        const nextState = (rawState as ControlState) ?? 'disconnected'
        if (isMounted) {
          updateStatus(nextState, payload.drone?.last_error ?? null)
        }
        return nextState
      } catch {
        if (isMounted) {
          markUnavailable()
        }
        return 'unavailable' as ControlState
      }
    }

    const fetchBattery = async () => {
      try {
        const response = await fetch('/api/telemetry')
        if (!response.ok) throw new Error('telemetry')
        const payload = (await response.json()) as {
          battery?: { percent?: number }
        }
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
  }, [markUnavailable, updateStatus])

  return { controlState: drcState, batteryPercent }
}
