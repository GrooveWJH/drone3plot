import { useCallback, useEffect, useState } from 'react'
import {
  deleteLocalTrajectory,
  findFallbackTrajectoryId,
  findLocalTrajectoryIdByLabel,
  getLocalTrajectory,
  getTrajectoryOptions,
  saveLocalTrajectory,
} from '../../../lib/trajectoryStorage'
import type { TrajectoryFile, TrajectoryMeta, WaypointData } from '../../../types/mission'
import { TRAJECTORY_SOURCES } from '../../../config/trajectories'
import {
  TRAJECTORY_ID_STORAGE_KEY,
  createId,
  degToRad,
  normalizeDegrees,
  radToDeg,
} from '../utils'

type UseTrajectoryStateParams = {
  waypoints: WaypointData[]
  setWaypoints: React.Dispatch<React.SetStateAction<WaypointData[]>>
  cloudFileName: string | null
  cloudRotation: [number, number, number]
  cloudOffset: [number, number, number]
  registerCloudTransform: (transform: TrajectoryFile['cloudTransform'] | null) => void
}

export const useTrajectoryState = ({
  waypoints,
  setWaypoints,
  cloudFileName,
  cloudRotation,
  cloudOffset,
  registerCloudTransform,
}: UseTrajectoryStateParams) => {
  const [trajectoryId, setTrajectoryId] = useState<string>(() => {
    if (typeof window === 'undefined') return TRAJECTORY_SOURCES[0]?.id ?? 'default'
    const cached = window.localStorage.getItem(TRAJECTORY_ID_STORAGE_KEY)
    return cached || TRAJECTORY_SOURCES[0]?.id || 'default'
  })
  const [trajectoryName, setTrajectoryName] = useState<string>('新轨迹')
  const [trajectoryOptions, setTrajectoryOptions] = useState<TrajectoryMeta[]>([])

  const hydrateWaypoints = useCallback(
    (trajectory: TrajectoryFile) => {
      setTrajectoryName(trajectory.name)
      registerCloudTransform(trajectory.cloudTransform ?? null)
      setWaypoints(
        trajectory.waypoints.map((waypoint) => ({
          id: createId(),
          position: [waypoint.x, waypoint.y, waypoint.z],
          rotation: [0, 0, degToRad(normalizeDegrees(waypoint.yaw))],
          takePhoto: waypoint.takePhoto,
        }))
      )
    },
    [registerCloudTransform, setWaypoints]
  )

  const loadTrajectory = useCallback(
    async (sourceId: string) => {
      const source = trajectoryOptions.find((item) => item.id === sourceId)
      if (!source) return
      if (source.source === 'local') {
        const cached = getLocalTrajectory(sourceId)
        if (cached) hydrateWaypoints(cached)
        return
      }

      if (source.url) {
        const response = await fetch(source.url)
        if (!response.ok) return
        const data = (await response.json()) as TrajectoryFile
        hydrateWaypoints(data)
      }
    },
    [hydrateWaypoints, trajectoryOptions]
  )

  const handleSelectTrajectory = useCallback(
    (sourceId: string) => {
      setTrajectoryId(sourceId)
      window.localStorage.setItem(TRAJECTORY_ID_STORAGE_KEY, sourceId)
      void loadTrajectory(sourceId)
    },
    [loadTrajectory]
  )

  const refreshTrajectoryOptions = useCallback(() => {
    setTrajectoryOptions(getTrajectoryOptions(TRAJECTORY_SOURCES))
  }, [])

  useEffect(() => {
    refreshTrajectoryOptions()
  }, [refreshTrajectoryOptions])

  useEffect(() => {
    if (trajectoryOptions.length > 0) {
      const exists = trajectoryOptions.some((item) => item.id === trajectoryId)
      if (!exists) {
        const fallback = findFallbackTrajectoryId(TRAJECTORY_SOURCES, trajectoryOptions)
        setTrajectoryId(fallback)
        window.localStorage.setItem(TRAJECTORY_ID_STORAGE_KEY, fallback)
        void loadTrajectory(fallback)
        return
      }
      void loadTrajectory(trajectoryId)
    }
  }, [loadTrajectory, trajectoryId, trajectoryOptions.length])

  const buildTrajectoryPayload = useCallback((): TrajectoryFile => {
    const payload: TrajectoryFile = {
      name: trajectoryName,
      createdAt: new Date().toISOString(),
      waypoints: waypoints.map((waypoint) => ({
        x: waypoint.position[0],
        y: waypoint.position[1],
        z: waypoint.position[2],
        yaw: normalizeDegrees(radToDeg(waypoint.rotation[2])),
        takePhoto: Boolean(waypoint.takePhoto),
      })),
    }
    if (cloudFileName) {
      payload.cloudTransform = {
        fileName: cloudFileName,
        rotation: [cloudRotation[0], cloudRotation[1], cloudRotation[2]],
        offset: [cloudOffset[0], cloudOffset[1], cloudOffset[2]],
      }
    }
    return payload
  }, [cloudFileName, cloudOffset, cloudRotation, trajectoryName, waypoints])

  const saveTrajectory = useCallback(() => {
    if (!trajectoryId) return
    const payload = buildTrajectoryPayload()
    const existingId = findLocalTrajectoryIdByLabel(trajectoryName)
    const targetId = existingId ?? `local-${Date.now()}`
    const result = saveLocalTrajectory(targetId, payload, trajectoryName)
    setTrajectoryId(targetId)
    window.localStorage.setItem(TRAJECTORY_ID_STORAGE_KEY, targetId)
    setTrajectoryName(result.label)
    refreshTrajectoryOptions()
  }, [buildTrajectoryPayload, refreshTrajectoryOptions, trajectoryId, trajectoryName])

  const exportTrajectoryFile = useCallback(() => {
    if (!trajectoryId) return
    const payload = buildTrajectoryPayload()
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${trajectoryName || trajectoryId}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }, [buildTrajectoryPayload, trajectoryId, trajectoryName])

  const deleteTrajectory = useCallback(() => {
    if (!trajectoryId) return
    deleteLocalTrajectory(trajectoryId)
    const nextOptions = getTrajectoryOptions(TRAJECTORY_SOURCES)
    setTrajectoryOptions(nextOptions)
    const fallback = findFallbackTrajectoryId(TRAJECTORY_SOURCES, nextOptions)
    setTrajectoryId(fallback)
    window.localStorage.setItem(TRAJECTORY_ID_STORAGE_KEY, fallback)
  }, [trajectoryId])

  return {
    trajectoryId,
    trajectoryName,
    trajectoryOptions,
    setTrajectoryName,
    handleSelectTrajectory,
    saveTrajectory,
    exportTrajectoryFile,
    deleteTrajectory,
  }
}
