import { Canvas } from '@react-three/fiber'
import { GizmoHelper, GizmoViewport, Line, OrbitControls } from '@react-three/drei'
import { useCallback, useMemo, useRef, useState } from 'react'
import PointCloudLayer from './PointCloudLayer'
import WaypointMarker from './WaypointMarker'
import Sidebar from './Sidebar'
import { loadLasPointCloud } from '../lib/pointCloudLoader'
import type { PointCloudStats, TransformMode, WaypointData } from '../types/mission'
import { UI_CONFIG } from '../config/ui'

const createId = () =>
  globalThis.crypto?.randomUUID?.() ?? `wp-${Math.random().toString(36).slice(2, 10)}`

const createWaypoint = (position: [number, number, number]): WaypointData => ({
  id: createId(),
  position,
  rotation: [0, 0, 0],
})

const offsetWaypoint = (position: [number, number, number]) => [
  position[0] + 2,
  position[1],
  position[2],
] as [number, number, number]

const originWaypoint: [number, number, number] = [0, 0, 0]

const MissionPlanner = () => {
  const [waypoints, setWaypoints] = useState<WaypointData[]>([
    createWaypoint([0, 0, 0]),
    createWaypoint([4, 0, 2]),
  ])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [mode] = useState<TransformMode>('translate')
  const [isTransforming, setIsTransforming] = useState(false)
  const [pointCloud, setPointCloud] = useState<Float32Array | null>(null)
  const [pointColors, setPointColors] = useState<Float32Array | null>(null)
  const [stats, setStats] = useState<PointCloudStats | null>(null)
  const budgetMB = UI_CONFIG.pointCloud.budgetMB
  const [cloudRotation, setCloudRotation] = useState<[number, number, number]>([0, 0, 0])
  const [cloudFileName, setCloudFileName] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

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
    rotation: [number, number, number]
  ) => {
    setWaypoints((prev) =>
      prev.map((waypoint) => (waypoint.id === id ? { ...waypoint, position, rotation } : waypoint))
    )
  }

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
      const savedRotation = localStorage.getItem(`cloudRotation:${file.name}`)
      if (savedRotation) {
        try {
          const parsed = JSON.parse(savedRotation) as [number, number, number]
          if (Array.isArray(parsed) && parsed.length === 3) {
            setCloudRotation([parsed[0], parsed[1], parsed[2]])
          }
        } catch {
          // ignore invalid cache
        }
      }

      setIsLoading(true)
      setError(null)

      try {
        const result = await loadLasPointCloud(file, {
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
          totalPoints: result.header.pointCount,
          loadedPoints: result.acceptedPoints,
          sampleEvery: result.sampleEvery,
          budgetMB,
        })
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
    [budgetMB]
  )


  const pointsColor = useMemo(
    () => (pointColors ? '#ffffff' : pointCloud ? '#93a4ad' : '#3b4b52'),
    [pointCloud, pointColors]
  )
  const pointRadius = UI_CONFIG.pointCloud.radius
  const pathPoints = useMemo(() => {
    if (waypoints.length <= 1) return null
    return waypoints.map((waypoint) => [...waypoint.position] as [number, number, number])
  }, [waypoints])

  return (
    <div className="app-shell">
      <Sidebar
        stats={stats}
        isLoading={isLoading}
        error={error}
        onFileSelect={handleFileSelect}
        onAddWaypoint={handleAddWaypoint}
        waypoints={waypoints}
        selectedId={selectedId}
        onSelectWaypoint={setSelectedId}
        onDeleteWaypoint={handleDeleteWaypoint}
        onReorderWaypoint={handleReorderWaypoint}
        onUpdateWaypoint={handleUpdateWaypoint}
        cloudRotation={cloudRotation}
        onRotateCloud={(axis, delta) => {
          setCloudRotation((prev) => {
            const next = [...prev] as [number, number, number]
            const index = axis === 'x' ? 0 : axis === 'y' ? 1 : 2
            next[index] = (next[index] + delta + 360) % 360
            if (cloudFileName) {
              localStorage.setItem(`cloudRotation:${cloudFileName}`, JSON.stringify(next))
            }
            return next
          })
        }}
      />
      <main className="viewport">
        <Canvas
          camera={{ position: [12, 12, 12], fov: 45 }}
          onPointerMissed={() => setSelectedId(null)}
        >
          <color attach="background" args={['#ffffff']} />
          {!pointCloud && <fog attach="fog" args={['#0c1519', 30, 120]} />}
          <ambientLight intensity={0.6} />
          <directionalLight position={[10, 18, 6]} intensity={0.9} />
          <gridHelper
            args={[
              UI_CONFIG.grid.size,
              UI_CONFIG.grid.coarseDivisions,
              UI_CONFIG.grid.coarseColor,
              UI_CONFIG.grid.coarseColor,
            ]}
          />
          <gridHelper
            args={[
              UI_CONFIG.grid.size,
              UI_CONFIG.grid.fineDivisions,
              UI_CONFIG.grid.fineColor,
              UI_CONFIG.grid.fineColor,
            ]}
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
              [0, 0, UI_CONFIG.axes.length],
            ]}
            color={UI_CONFIG.axes.colors.y}
            lineWidth={UI_CONFIG.axes.width}
          />
          <Line
            points={[
              [0, 0, 0],
              [0, UI_CONFIG.axes.length, 0],
            ]}
            color={UI_CONFIG.axes.colors.z}
            lineWidth={UI_CONFIG.axes.width}
          />
          <PointCloudLayer
            points={pointCloud}
            colors={pointColors}
            color={pointsColor}
            radius={pointRadius}
            rotation={[
              (cloudRotation[0] * Math.PI) / 180,
              (cloudRotation[1] * Math.PI) / 180,
              (cloudRotation[2] * Math.PI) / 180,
            ]}
          />
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
              axisColors={['#ef4444', '#3b82f6', '#22c55e']}
              labelColor="#111827"
              labels={['X', 'Z', 'Y']}
            />
          </GizmoHelper>
          {waypoints.map((waypoint, index) => (
            <WaypointMarker
              key={waypoint.id}
              waypoint={waypoint}
              index={index}
              mode={mode}
              selected={selectedId === waypoint.id}
              onSelect={() => setSelectedId(waypoint.id)}
              onUpdate={handleUpdateWaypoint}
              onTransforming={setIsTransforming}
            />
          ))}
          <OrbitControls makeDefault enableDamping enabled={!isTransforming} />
        </Canvas>
      </main>
    </div>
  )
}

export default MissionPlanner
