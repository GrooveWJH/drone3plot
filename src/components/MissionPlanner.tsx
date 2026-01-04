import { Canvas } from '@react-three/fiber'
import { GizmoHelper, GizmoViewport, Line, OrbitControls, TransformControls } from '@react-three/drei'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type * as THREE from 'three'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import PointCloudLayer from './PointCloudLayer'
import WaypointMarker from './WaypointMarker'
import Sidebar from './Sidebar'
import { loadPointCloud } from '../lib/pointCloudLoader'
import { cachePointCloudFile, getCachedPointCloudFile } from '../lib/pointCloudCache'
import {
  createNewTrajectoryName,
  deleteLocalTrajectory,
  findFallbackTrajectoryId,
  getLocalTrajectory,
  getTrajectoryOptions,
  saveLocalTrajectory,
} from '../lib/trajectoryStorage'
import type { PointCloudStats, TrajectoryFile, TransformMode, WaypointData } from '../types/mission'
import { UI_CONFIG } from '../config/ui'
import { TRAJECTORY_SOURCES } from '../config/trajectories'

const createId = () =>
  globalThis.crypto?.randomUUID?.() ?? `wp-${Math.random().toString(36).slice(2, 10)}`

const createWaypoint = (position: [number, number, number]): WaypointData => ({
  id: createId(),
  position,
  rotation: [0, 0, 0],
  takePhoto: false,
})

const offsetWaypoint = (position: [number, number, number]) => [
  position[0] + 2,
  position[1],
  position[2],
] as [number, number, number]

const originWaypoint: [number, number, number] = [0, 0, 0]

const formatNumber = (value: number) => new Intl.NumberFormat('en-US').format(value)
const clampRotation = (value: number) => Math.max(-180, Math.min(180, value))
const degToRad = (degrees: number) => (degrees * Math.PI) / 180
const radToDeg = (radians: number) => (radians * 180) / Math.PI
const normalizeDegrees = (value: number) => ((value % 360) + 360) % 360

const MissionPlanner = () => {
  const [waypoints, setWaypoints] = useState<WaypointData[]>([
    createWaypoint([0, 0, 0]),
    createWaypoint([4, 0, 2]),
  ])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [focusTargetId, setFocusTargetId] = useState<string | null>(null)
  const [mode] = useState<TransformMode>('translate')
  const [isTransforming, setIsTransforming] = useState(false)
  const [pointCloud, setPointCloud] = useState<Float32Array | null>(null)
  const [pointColors, setPointColors] = useState<Float32Array | null>(null)
  const [stats, setStats] = useState<PointCloudStats | null>(null)
  const budgetMB = UI_CONFIG.pointCloud.budgetMB
  const [cloudRotation, setCloudRotation] = useState<[number, number, number]>([0, 0, 0])
  const [cloudOffset, setCloudOffset] = useState<[number, number, number]>([0, 0, 0])
  const [cloudFileName, setCloudFileName] = useState<string | null>(null)
  const [cloudTransformEnabled, setCloudTransformEnabled] = useState(false)
  const [cloudTransformMode, setCloudTransformMode] = useState<'translate' | 'rotate'>('translate')
  const [isCloudTransforming, setIsCloudTransforming] = useState(false)
  const cloudGroupRef = useRef<THREE.Group>(null)
  const [pendingCloudTransform, setPendingCloudTransform] = useState<TrajectoryFile['cloudTransform'] | null>(null)
  const orbitRef = useRef<OrbitControlsImpl>(null)
  const focusAnimationRef = useRef<number | null>(null)
  const isFocusingRef = useRef(false)
  const waypointsRef = useRef<WaypointData[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const [trajectoryId, setTrajectoryId] = useState<string>(TRAJECTORY_SOURCES[0]?.id ?? 'default')
  const [trajectoryName, setTrajectoryName] = useState<string>('新轨迹')
  const [trajectoryOptions, setTrajectoryOptions] = useState<TrajectoryMeta[]>([])

  const saveCloudTransform = useCallback(
    (fileName: string, rotation: [number, number, number], offset: [number, number, number]) => {
      localStorage.setItem(
        `cloudTransform:${fileName}`,
        JSON.stringify({ rotation, offset })
      )
    },
    []
  )

  const applyCloudTransform = useCallback(
    (transform: NonNullable<TrajectoryFile['cloudTransform']>) => {
      setCloudRotation([
        clampRotation(transform.rotation[0]),
        clampRotation(transform.rotation[1]),
        clampRotation(transform.rotation[2]),
      ])
      setCloudOffset([transform.offset[0], transform.offset[1], transform.offset[2]])
      setPendingCloudTransform(null)
      saveCloudTransform(transform.fileName, transform.rotation, transform.offset)
    },
    [saveCloudTransform]
  )

  useEffect(() => {
    const group = cloudGroupRef.current
    if (!group) return
    group.position.set(cloudOffset[0], cloudOffset[1], cloudOffset[2])
    group.rotation.set(
      degToRad(cloudRotation[0]),
      degToRad(cloudRotation[1]),
      degToRad(cloudRotation[2])
    )
  }, [cloudOffset, cloudRotation, degToRad])

  const hydrateWaypoints = useCallback((trajectory: TrajectoryFile) => {
    setTrajectoryName(trajectory.name)
    if (trajectory.cloudTransform) {
      if (cloudFileName && trajectory.cloudTransform.fileName === cloudFileName) {
        applyCloudTransform(trajectory.cloudTransform)
      } else {
        setPendingCloudTransform(trajectory.cloudTransform)
      }
    } else {
      setPendingCloudTransform(null)
    }
    setWaypoints(
      trajectory.waypoints.map((waypoint) => ({
        id: createId(),
        position: [waypoint.x, waypoint.y, waypoint.z],
        rotation: [0, 0, degToRad(normalizeDegrees(waypoint.yaw))],
        takePhoto: waypoint.takePhoto,
      }))
    )
  }, [applyCloudTransform, cloudFileName])

  const loadTrajectory = useCallback(async (sourceId: string) => {
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
  }, [hydrateWaypoints, trajectoryOptions])

  const handleSelectTrajectory = useCallback(
    (sourceId: string) => {
      setTrajectoryId(sourceId)
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
      void loadTrajectory(trajectoryId)
    }
  }, [loadTrajectory, trajectoryId, trajectoryOptions.length])

  const handleAddWaypoint = () => {
    setWaypoints((prev) => {
      const last = prev[prev.length - 1]
      const nextPosition = last ? offsetWaypoint(last.position) : originWaypoint
      return [...prev, createWaypoint(nextPosition)]
    })
  }

  const handleUpdateWaypoint = (
    id: string,
    position: [number, number, number],
    rotation: [number, number, number],
    takePhoto?: boolean
  ) => {
    setWaypoints((prev) =>
      prev.map((waypoint) =>
        waypoint.id === id
          ? {
              ...waypoint,
              position,
              rotation,
              takePhoto: takePhoto ?? waypoint.takePhoto,
            }
          : waypoint
      )
    )
  }

  const handleTogglePhoto = (id: string, value: boolean) => {
    setWaypoints((prev) =>
      prev.map((waypoint) => (waypoint.id === id ? { ...waypoint, takePhoto: value } : waypoint))
    )
  }

  useEffect(() => {
    waypointsRef.current = waypoints
  }, [waypoints])

  const focusOnWaypoint = useCallback((waypointId: string) => {
    const targetWaypoint = waypointsRef.current.find((waypoint) => waypoint.id === waypointId)
    if (!targetWaypoint || !orbitRef.current) return
    if (focusAnimationRef.current !== null) {
      cancelAnimationFrame(focusAnimationRef.current)
      focusAnimationRef.current = null
    }
    const startTarget = orbitRef.current.target.clone()
    const endTarget = {
      x: targetWaypoint.position[0],
      y: targetWaypoint.position[1],
      z: targetWaypoint.position[2],
    }
    const duration = Math.max(0, UI_CONFIG.camera.focusDuration) * 1000
    if (duration === 0) {
      orbitRef.current.target.set(endTarget.x, endTarget.y, endTarget.z)
      orbitRef.current.update()
      isFocusingRef.current = false
      return
    }
    isFocusingRef.current = true
    const startTime = performance.now()
    const animate = (time: number) => {
      const elapsed = time - startTime
      const t = Math.min(1, elapsed / duration)
      const ease = t * (2 - t)
      orbitRef.current?.target.set(
        startTarget.x + (endTarget.x - startTarget.x) * ease,
        startTarget.y + (endTarget.y - startTarget.y) * ease,
        startTarget.z + (endTarget.z - startTarget.z) * ease
      )
      orbitRef.current?.update()
      if (t < 1) {
        focusAnimationRef.current = requestAnimationFrame(animate)
      } else {
        focusAnimationRef.current = null
        isFocusingRef.current = false
      }
    }
    focusAnimationRef.current = requestAnimationFrame(animate)
  }, [])

  useEffect(() => {
    if (!focusTargetId) return
    focusOnWaypoint(focusTargetId)
    return () => {
      if (focusAnimationRef.current !== null) {
        cancelAnimationFrame(focusAnimationRef.current)
        focusAnimationRef.current = null
      }
    }
  }, [focusOnWaypoint, focusTargetId])

  const handleSelectWaypointFromSidebar = useCallback((id: string) => {
    setSelectedId(id)
    setFocusTargetId(id)
  }, [])

  const handleSelectWaypointFromScene = useCallback((id: string) => {
    setSelectedId(id)
  }, [])

  const buildTrajectoryPayload = (): TrajectoryFile => {
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
  }

  const saveTrajectory = () => {
    if (!trajectoryId) return
    const payload = buildTrajectoryPayload()
    const result = saveLocalTrajectory(trajectoryId, payload, trajectoryName, TRAJECTORY_SOURCES)
    setTrajectoryName(result.label)
    refreshTrajectoryOptions()
  }

  const exportTrajectoryFile = () => {
    if (!trajectoryId) return
    const payload = buildTrajectoryPayload()
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${trajectoryName || trajectoryId}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const createNewTrajectory = () => {
    const newId = `local-${Date.now()}`
    const newName = createNewTrajectoryName('DefaultTrajectory', TRAJECTORY_SOURCES)
    setTrajectoryId(newId)
    setTrajectoryName(newName)
    setWaypoints([])
  }

  const deleteTrajectory = useCallback(() => {
    if (!trajectoryId) return
    deleteLocalTrajectory(trajectoryId)
    const nextOptions = getTrajectoryOptions(TRAJECTORY_SOURCES)
    setTrajectoryOptions(nextOptions)
    const fallback = findFallbackTrajectoryId(TRAJECTORY_SOURCES, nextOptions)
    setTrajectoryId(fallback)
  }, [trajectoryId])

  const handleDeleteWaypoint = (id: string) => {
    setWaypoints((prev) => prev.filter((waypoint) => waypoint.id !== id))
    setSelectedId((prev) => (prev === id ? null : prev))
  }

  const handleReorderWaypoint = (id: string, direction: 'up' | 'down') => {
    setWaypoints((prev) => {
      const index = prev.findIndex((waypoint) => waypoint.id === id)
      if (index < 0) return prev
      const targetIndex = direction === 'up' ? index - 1 : index + 1
      if (targetIndex < 0 || targetIndex >= prev.length) return prev
      const next = [...prev]
      const [moved] = next.splice(index, 1)
      next.splice(targetIndex, 0, moved)
      return next
    })
  }

  const handleFileSelect = useCallback(
    async (file: File) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      setCloudFileName(file.name)
      setCloudRotation([0, 0, 0])
      setCloudOffset([0, 0, 0])
      const savedTransform = localStorage.getItem(`cloudTransform:${file.name}`)
      if (savedTransform) {
        try {
          const parsed = JSON.parse(savedTransform) as {
            rotation?: [number, number, number]
            offset?: [number, number, number]
          }
          if (parsed.rotation && parsed.rotation.length === 3) {
            setCloudRotation([
              clampRotation(parsed.rotation[0]),
              clampRotation(parsed.rotation[1]),
              clampRotation(parsed.rotation[2]),
            ])
          }
          if (parsed.offset && parsed.offset.length === 3) {
            setCloudOffset([parsed.offset[0], parsed.offset[1], parsed.offset[2]])
          }
        } catch {
          // ignore invalid cache
        }
      }

      if (pendingCloudTransform && pendingCloudTransform.fileName === file.name) {
        applyCloudTransform(pendingCloudTransform)
      }

      setIsLoading(true)
      setError(null)

      try {
        const result = await loadPointCloud(file, {
          maxMegabytes: budgetMB,
          onProgress: (progress) => {
            setStats({
              totalPoints: progress.totalPoints,
              loadedPoints: progress.acceptedPoints,
              sampleEvery: progress.sampleEvery,
              budgetMB,
            })
          },
          signal: controller.signal,
        })

        setPointCloud(result.points)
        setPointColors(result.colors)
        setStats({
          totalPoints: result.totalPoints,
          loadedPoints: result.acceptedPoints,
          sampleEvery: result.sampleEvery,
          budgetMB,
        })
        void cachePointCloudFile(file)
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : 'Failed to load LAS file.')
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false)
        }
      }
    },
    [applyCloudTransform, budgetMB, pendingCloudTransform]
  )

  useEffect(() => {
    const hydrateCachedFile = async () => {
      const cached = await getCachedPointCloudFile()
      if (!cached) return
      await handleFileSelect(cached)
    }
    void hydrateCachedFile()
  }, [handleFileSelect])


  const pointsColor = useMemo(
    () => (pointColors ? '#ffffff' : pointCloud ? '#5a666e' : '#7f8b92'),
    [pointCloud, pointColors]
  )
  const pointRadius = UI_CONFIG.pointCloud.radius
  const pointSizeAttenuation = !UI_CONFIG.pointCloud.fixedPixelSize
  const pathPoints = useMemo(() => {
    if (waypoints.length <= 1) return null
    return waypoints.map((waypoint) => [...waypoint.position] as [number, number, number])
  }, [waypoints])

  return (
    <div className="app-shell">
      <header className="app-topbar">
        <div className="brand">
          <div className="brand-mark">D3</div>
          <div>
            <p className="brand-title">Drone3Plot</p>
            <span className="brand-sub">Mission planning cockpit</span>
          </div>
        </div>
        <div className="topbar-meta">
          <div className="meta-card">
            <span>Trajectory</span>
            <strong>{trajectoryName}</strong>
          </div>
          <div className="meta-card">
            <span>Point Cloud</span>
            <strong>{stats ? `${formatNumber(stats.loadedPoints)} pts` : 'No data'}</strong>
          </div>
          <div className="meta-card">
            <span>Budget</span>
            <strong>{UI_CONFIG.pointCloud.budgetMB}MB</strong>
          </div>
        </div>
      </header>
      <div className="workspace">
        <Sidebar
          stats={stats}
          isLoading={isLoading}
          error={error}
          onFileSelect={handleFileSelect}
          onAddWaypoint={handleAddWaypoint}
          waypoints={waypoints}
          selectedId={selectedId}
          onSelectWaypoint={handleSelectWaypointFromSidebar}
          onDeleteWaypoint={handleDeleteWaypoint}
          onReorderWaypoint={handleReorderWaypoint}
          onUpdateWaypoint={handleUpdateWaypoint}
          onTogglePhoto={handleTogglePhoto}
          trajectoryName={trajectoryName}
          trajectoryId={trajectoryId}
          trajectoryOptions={trajectoryOptions}
          onSelectTrajectory={handleSelectTrajectory}
          onSaveTrajectory={saveTrajectory}
          onExportTrajectoryFile={exportTrajectoryFile}
          onCreateTrajectory={createNewTrajectory}
          onDeleteTrajectory={deleteTrajectory}
          onRenameTrajectory={setTrajectoryName}
          hasPointCloud={Boolean(pointCloud)}
          cloudRotation={cloudRotation}
          cloudOffset={cloudOffset}
          cloudTransformEnabled={cloudTransformEnabled}
          cloudTransformMode={cloudTransformMode}
          onToggleCloudTransform={() => setCloudTransformEnabled((prev) => !prev)}
          onSetCloudTransformMode={setCloudTransformMode}
          onSetCloudRotation={(axis, value) => {
            setCloudRotation((prev) => {
              const next = [...prev] as [number, number, number]
              const index = axis === 'x' ? 0 : axis === 'y' ? 1 : 2
              next[index] = clampRotation(value)
              if (cloudFileName) {
                saveCloudTransform(cloudFileName, next, cloudOffset)
              }
              return next
            })
          }}
          onTranslateCloud={(axis, value) => {
            setCloudOffset((prev) => {
              const next = [...prev] as [number, number, number]
              const index = axis === 'x' ? 0 : axis === 'y' ? 1 : 2
              next[index] = value
              if (cloudFileName) {
                saveCloudTransform(cloudFileName, cloudRotation, next)
              }
              return next
            })
          }}
        />
        <main className="viewport">
          <Canvas
            camera={{ position: [12, 12, 12], fov: 45, up: [0, 0, 1] }}
          onPointerMissed={() => {
            if (isFocusingRef.current) return
            setSelectedId(null)
          }}
          >
            <color attach="background" args={['#f7efe1']} />
            {!pointCloud && <fog attach="fog" args={['#d8cbb8', 30, 120]} />}
            <ambientLight intensity={0.6} />
            <directionalLight position={[10, 18, 6]} intensity={0.9} />
            <gridHelper
              args={[
                UI_CONFIG.grid.size,
                UI_CONFIG.grid.coarseDivisions,
                UI_CONFIG.grid.coarseColor,
                UI_CONFIG.grid.coarseColor,
              ]}
              rotation={[Math.PI / 2, 0, 0]}
            />
            <gridHelper
              args={[
                UI_CONFIG.grid.size,
                UI_CONFIG.grid.fineDivisions,
                UI_CONFIG.grid.fineColor,
                UI_CONFIG.grid.fineColor,
              ]}
              rotation={[Math.PI / 2, 0, 0]}
            />
            <Line
              points={[
                [0, 0, 0],
                [UI_CONFIG.axes.length, 0, 0],
              ]}
              color={UI_CONFIG.axes.colors.x}
              lineWidth={UI_CONFIG.axes.width}
            />
            <Line
              points={[
                [0, 0, 0],
                [0, UI_CONFIG.axes.length, 0],
              ]}
              color={UI_CONFIG.axes.colors.y}
              lineWidth={UI_CONFIG.axes.width}
            />
            <Line
              points={[
                [0, 0, 0],
                [0, 0, UI_CONFIG.axes.length],
              ]}
              color={UI_CONFIG.axes.colors.z}
              lineWidth={UI_CONFIG.axes.width}
            />
            <group ref={cloudGroupRef}>
              <PointCloudLayer
                points={pointCloud}
                colors={pointColors}
                color={pointsColor}
                radius={pointRadius}
                sizeAttenuation={pointSizeAttenuation}
              />
            </group>
            {cloudTransformEnabled && (
              <TransformControls
                mode={cloudTransformMode}
                object={cloudGroupRef}
                onDraggingChanged={(event) => setIsCloudTransforming(event.value)}
                onObjectChange={() => {
                  const group = cloudGroupRef.current
                  if (!group) return
                  const nextRotation: [number, number, number] = [
                    clampRotation(radToDeg(group.rotation.x)),
                    clampRotation(radToDeg(group.rotation.y)),
                    clampRotation(radToDeg(group.rotation.z)),
                  ]
                  group.rotation.set(
                    degToRad(nextRotation[0]),
                    degToRad(nextRotation[1]),
                    degToRad(nextRotation[2])
                  )
                  setCloudRotation(nextRotation)
                  const nextOffset: [number, number, number] = [
                    group.position.x,
                    group.position.y,
                    group.position.z,
                  ]
                  setCloudOffset(nextOffset)
                  if (cloudFileName) {
                    saveCloudTransform(cloudFileName, nextRotation, nextOffset)
                  }
                }}
              />
            )}
            {pathPoints && (
              <Line
                points={pathPoints}
                color={UI_CONFIG.path.color}
                lineWidth={UI_CONFIG.path.width}
                transparent
                opacity={UI_CONFIG.path.opacity}
              />
            )}
            <GizmoHelper alignment="top-right" margin={[72, 72]}>
              <GizmoViewport
                axisColors={[
                  UI_CONFIG.axes.colors.x,
                  UI_CONFIG.axes.colors.y,
                  UI_CONFIG.axes.colors.z,
                ]}
                labelColor="#25302c"
                labels={['X', 'Y', 'Z']}
              />
            </GizmoHelper>
            {waypoints.map((waypoint, index) => (
              <WaypointMarker
                key={waypoint.id}
                waypoint={waypoint}
                index={index}
                mode={mode}
                selected={selectedId === waypoint.id}
                onSelect={() => handleSelectWaypointFromScene(waypoint.id)}
                onUpdate={handleUpdateWaypoint}
                onTransforming={setIsTransforming}
              />
            ))}
            <OrbitControls
              ref={orbitRef}
              makeDefault
              enableDamping
              enabled={!isTransforming && !isCloudTransforming}
            />
          </Canvas>
        </main>
      </div>
    </div>
  )
}

export default MissionPlanner
