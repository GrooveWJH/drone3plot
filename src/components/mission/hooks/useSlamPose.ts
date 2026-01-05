import { useEffect, useMemo, useState } from 'react'
import { io } from 'socket.io-client'
import type { ControlState } from './useControlStatus'

export type SlamSnapshot = {
  x: number | null
  y: number | null
  z: number | null
  yaw: number | null
  status: string | null
}

export type DronePose = {
  x: number
  y: number
  z: number
  yaw: number
}

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value)

export const useSlamPose = (controlState: ControlState) => {
  const [slamSnapshot, setSlamSnapshot] = useState<SlamSnapshot | null>(null)

  useEffect(() => {
    const socket = io('/pose')
    socket.on('pose', (payload) => {
      if (!payload) return
      const { x, y, z, yaw, status } = payload as {
        x?: number | null
        y?: number | null
        z?: number | null
        yaw?: number | null
        status?: string | null
      }
      setSlamSnapshot({
        x: x ?? null,
        y: y ?? null,
        z: z ?? null,
        yaw: yaw ?? null,
        status: status ?? null,
      })
    })
    return () => {
      socket.disconnect()
    }
  }, [])

  const dronePose = useMemo<DronePose | null>(() => {
    if (controlState !== 'drc_ready') return null
    if (!slamSnapshot) return null
    if (slamSnapshot.status !== 'running') return null
    if (
      !isFiniteNumber(slamSnapshot.x) ||
      !isFiniteNumber(slamSnapshot.y) ||
      !isFiniteNumber(slamSnapshot.z) ||
      !isFiniteNumber(slamSnapshot.yaw)
    ) {
      return null
    }
    return {
      x: slamSnapshot.x,
      y: slamSnapshot.y,
      z: slamSnapshot.z,
      yaw: slamSnapshot.yaw,
    }
  }, [controlState, slamSnapshot])

  return { slamSnapshot, dronePose }
}
