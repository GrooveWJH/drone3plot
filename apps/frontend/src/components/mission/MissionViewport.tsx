import type { RefObject } from 'react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { GizmoHelper, GizmoViewport, Line, OrbitControls, TransformControls } from '@react-three/drei'
import type { Group } from 'three'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import PointCloudLayer from '../../lib/pointcloud/src/PointCloudLayer'
import WaypointMarker from '../WaypointMarker'
import type { TransformMode, WaypointData } from '../../types/mission'
import { UI_CONFIG } from '../../config/ui'
import WaypointShape from '../WaypointShape'
import GpuUploadTimer from '../../lib/pointcloud/src/GpuUploadTimer'
import AdaptiveRenderManager from '../../lib/pointcloud/src/AdaptiveRenderManager'
import { degToRad } from './utils'

let lastFrameLogAt = 0

export type MissionViewportProps = {
  cloudFileName: string | null
  pointCloud: Float32Array | null
  pointColors: Float32Array | null
  pointCloudChunks: Array<{ points: Float32Array; colors: Float32Array | null }>
  pointCloudChunkVersion: number
  pointsColor: string
  pointRadius: number
  pointSizeAttenuation: boolean
  waypoints: WaypointData[]
  selectedId: string | null
  mode: TransformMode
  pathPoints: [number, number, number][] | null
  cloudTransformEnabled: boolean
  cloudTransformMode: 'translate' | 'rotate'
  dronePose: { x: number; y: number; z: number; yaw: number | null } | null
  isTrajectoryLocked: boolean
  onToggleTrajectoryLock: () => void
  isTransforming: boolean
  isCloudTransforming: boolean
  onSetIsOrbiting: (value: boolean) => void
  onSetIsTransforming: (value: boolean) => void
  onSetIsCloudTransforming: (value: boolean) => void
  onSelectWaypoint: (id: string) => void
  onUpdateWaypoint: (
    id: string,
    position: [number, number, number],
    rotation: [number, number, number],
    takePhoto?: boolean
  ) => void
  onPointerMissed: () => void
  onRequestRender: () => void
  onInvalidate: (fn: () => void) => void
  onCloudObjectChange: () => void
  renderManagerDeps: unknown[]
  renderManagerActive: boolean
  cloudGroupRef: RefObject<Group | null>
  orbitRef: RefObject<OrbitControlsImpl | null>
}

const MissionViewport = ({
  cloudFileName,
  pointCloud,
  pointColors,
  pointCloudChunks,
  pointCloudChunkVersion,
  pointsColor,
  pointRadius,
  pointSizeAttenuation,
  waypoints,
  selectedId,
  mode,
  pathPoints,
  cloudTransformEnabled,
  cloudTransformMode,
  dronePose,
  isTrajectoryLocked,
  onToggleTrajectoryLock,
  isTransforming,
  isCloudTransforming,
  onSetIsOrbiting,
  onSetIsTransforming,
  onSetIsCloudTransforming,
  onSelectWaypoint,
  onUpdateWaypoint,
  onPointerMissed,
  onRequestRender,
  onInvalidate,
  onCloudObjectChange,
  renderManagerDeps,
  renderManagerActive,
  cloudGroupRef,
  orbitRef,
}: MissionViewportProps) => {
  const [fps, setFps] = useState<number | null>(null)
  const [cloudGroupObject, setCloudGroupObject] = useState<Group | null>(null)
  const handleFps = useCallback((value: number) => {
    setFps(value)
  }, [])

  useEffect(() => {
    const raf = requestAnimationFrame(() => {
      setCloudGroupObject(cloudGroupRef.current ?? null)
    })
    return () => cancelAnimationFrame(raf)
  }, [cloudGroupRef, pointCloud, pointCloudChunks.length])

  useEffect(() => {
    if (!pointCloud && pointCloudChunks.length === 0) return undefined
    const timingLabel = '[pointcloud] first-frame'
    const start = performance.now()
    const raf1 = requestAnimationFrame(() => {
      const raf2 = requestAnimationFrame(() => {
        const now = performance.now()
        const delta = lastFrameLogAt ? now - lastFrameLogAt : 0
        const timestamp = new Date().toISOString()
        console.log(
          `${timingLabel} ${timestamp}: ${(now - start).toFixed(7)}ms (+${delta.toFixed(7)}ms)`
        )
        lastFrameLogAt = now
      })
      return () => cancelAnimationFrame(raf2)
    })
    return () => cancelAnimationFrame(raf1)
  }, [pointCloud, pointColors, pointCloudChunks.length])

  return (
    <main className="viewport">
      {fps !== null && (
        <div className={`viewport-file${cloudFileName ? ' has-filename' : ''}`}>
          <span className="viewport-filename">{cloudFileName ?? ''}</span>
          <span className="viewport-sep">·</span>
          <span className="viewport-fps">FPS {fps.toFixed(0)}</span>
        </div>
      )}
      <div
        className={`trajectory-lock ${isTrajectoryLocked ? 'is-locked' : ''}`}
        data-trajectory-lock-state
        data-locked={isTrajectoryLocked}
      >
        <button
          className="ghost with-icon trajectory-lock-button"
          type="button"
          onClick={onToggleTrajectoryLock}
        >
          <span className="material-symbols-outlined" aria-hidden="true">
            {isTrajectoryLocked ? 'lock' : 'lock_open'}
          </span>
          {isTrajectoryLocked ? '已锁定' : '锁定轨迹'}
        </button>
      </div>
      <Canvas
        frameloop="demand"
        camera={{ position: [12, 12, 12], fov: 45, up: [0, 0, 1] }}
        onPointerMissed={onPointerMissed}
      >
        <FpsTracker onFps={handleFps} />
        <AdaptiveRenderManager
          deps={renderManagerDeps}
          active={renderManagerActive}
          onInvalidate={onInvalidate}
        />
        <GpuUploadTimer enabled={Boolean(pointCloud) || pointCloudChunks.length > 0} />
        <color attach="background" args={['#f7efe1']} />
        {!pointCloud && pointCloudChunks.length === 0 && (
          <fog attach="fog" args={['#d8cbb8', 30, 120]} />
        )}
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
            chunks={pointCloudChunks}
            chunkVersion={pointCloudChunkVersion}
            color={pointsColor}
            radius={pointRadius}
            sizeAttenuation={pointSizeAttenuation}
            chunkSize={UI_CONFIG.pointCloud.chunkSize}
            chunkBatch={UI_CONFIG.pointCloud.chunkBatch}
          />
        </group>
        {cloudTransformEnabled && (
          <TransformControls
            mode={cloudTransformMode}
            object={cloudGroupObject ?? undefined}
            onPointerDown={() => onSetIsCloudTransforming(true)}
            onPointerUp={() => onSetIsCloudTransforming(false)}
            onObjectChange={onCloudObjectChange}
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
        {dronePose && (
          <group
            position={[dronePose.x, dronePose.y, dronePose.z]}
            rotation={[0, 0, degToRad(dronePose.yaw ?? 0)]}
          >
            <WaypointShape
              sphereColor="#22c55e"
              coneColor="#38bdf8"
              sphereEmissive="#22c55e"
              coneEmissive="#38bdf8"
              sphereEmissiveIntensity={0.4}
              coneEmissiveIntensity={0.35}
            />
          </group>
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
            isLocked={isTrajectoryLocked}
            onSelect={() => onSelectWaypoint(waypoint.id)}
            onUpdate={onUpdateWaypoint}
            onTransforming={onSetIsTransforming}
          />
        ))}
        <OrbitControls
          ref={orbitRef}
          makeDefault
          enableDamping
          enabled={!isTransforming && !isCloudTransforming}
          onStart={() => onSetIsOrbiting(true)}
          onEnd={() => onSetIsOrbiting(false)}
          onChange={onRequestRender}
        />
      </Canvas>
    </main>
  )
}

export default MissionViewport

type FpsTrackerProps = {
  onFps: (value: number) => void
}

const FpsTracker = ({ onFps }: FpsTrackerProps) => {
  const lastSampleRef = useRef<number | null>(null)
  const frameCountRef = useRef(0)

  useFrame(() => {
    if (lastSampleRef.current === null) {
      lastSampleRef.current = performance.now()
      return
    }
    frameCountRef.current += 1
    const now = performance.now()
    const elapsed = now - lastSampleRef.current
    if (elapsed < 200) return
    const nextFps = (frameCountRef.current / elapsed) * 1000
    frameCountRef.current = 0
    lastSampleRef.current = now
    onFps(nextFps)
  })

  return null
}
