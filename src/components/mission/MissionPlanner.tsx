import { useCallback, useEffect, useRef, useState } from 'react'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import Sidebar from '../Sidebar'
import MissionTopbar from './MissionTopbar'
import MissionViewport from './MissionViewport'
import MissionDock from './MissionDock'
import { useControlStatus } from './hooks/useControlStatus'
import { useCloudTransformState } from './hooks/useCloudTransformState'
import { useCloudTransformSync } from './hooks/useCloudTransformSync'
import { usePerfObservers } from '../../lib/pointcloud/src/usePerfObservers'
import { usePointCloudLoader } from '../../lib/pointcloud/src/usePointCloudLoader'
import { useSlamPose } from './hooks/useSlamPose'
import { useTrajectoryState } from './hooks/useTrajectoryState'
import { useWaypointsState } from './hooks/useWaypointsState'
import { normalizeDegrees, radToDeg } from './utils'

const MissionPlanner = () => {
  const orbitRef = useRef<OrbitControlsImpl | null>(null)
  const invalidateRef = useRef<(() => void) | null>(null)
  const [isOrbiting, setIsOrbiting] = useState(false)
  const [isTransforming, setIsTransforming] = useState(false)
  const [isCloudTransforming, setIsCloudTransforming] = useState(false)
  const [isDashboardOpen, setIsDashboardOpen] = useState(false)
  const [isMediaOpen, setIsMediaOpen] = useState(false)
  const [isTrajectoryLocked, setIsTrajectoryLocked] = useState(false)
  const dashboardToggleRef = useRef<HTMLButtonElement | null>(null)

  usePerfObservers()

  const { controlState, batteryPercent } = useControlStatus()
  const { dronePose } = useSlamPose()
  const {
    cloudRotation,
    cloudOffset,
    cloudFileName,
    cloudTransformEnabled,
    cloudTransformMode,
    cloudGroupRef,
    setCloudTransformEnabled,
    setCloudTransformMode,
    onSetCloudRotation,
    onTranslateCloud,
    onCloudObjectChange,
    prepareCloudForFile,
    resetCloudTransform,
    registerTrajectoryCloudTransform,
  } = useCloudTransformState()
  const {
    pointCloud,
    pointColors,
    pointCloudChunks,
    pointCloudChunkVersion,
    hasPointCloud,
    fileName: pointCloudFileName,
    stats,
    isLoading,
    error,
    pointsColor,
    pointRadius,
    pointSizeAttenuation,
    handleFileSelect,
    clearPointCloud,
  } = usePointCloudLoader({
    onPrepareFile: prepareCloudForFile,
    onResetCloudTransform: resetCloudTransform,
    isInteracting: isOrbiting || isTransforming || isCloudTransforming,
  })
  useCloudTransformSync({
    cloudGroupRef,
    cloudRotation,
    cloudOffset,
    hasPointCloud,
  })
  const {
    waypoints,
    selectedId,
    mode,
    pathPoints,
    isFocusingRef,
    setSelectedId,
    setWaypoints,
    handleAddWaypoint,
    handleUpdateWaypoint,
    handleDeleteWaypoint,
    handleReorderWaypoint,
    handleTogglePhoto,
    handleSelectWaypointFromSidebar,
    handleSelectWaypointFromScene,
  } = useWaypointsState(orbitRef)
  const {
    trajectoryId,
    trajectoryName,
    trajectoryOptions,
    setTrajectoryName,
    handleSelectTrajectory,
    saveTrajectory,
    exportTrajectoryFile,
    deleteTrajectory,
  } = useTrajectoryState({
    waypoints,
    setWaypoints,
    cloudFileName,
    cloudRotation,
    cloudOffset,
    registerCloudTransform: registerTrajectoryCloudTransform,
  })

  const buildTrajectoryPayload = useCallback(
    () => ({
      trajectory_id: trajectoryId,
      name: trajectoryName,
      updated_at: Date.now(),
      points: waypoints.map((waypoint) => ({
        x: waypoint.position[0],
        y: waypoint.position[1],
        z: waypoint.position[2],
        yaw: normalizeDegrees(radToDeg(waypoint.rotation[2])),
        takePhoto: Boolean(waypoint.takePhoto),
      })),
    }),
    [trajectoryId, trajectoryName, waypoints]
  )

  useEffect(() => {
    if (!isTrajectoryLocked) return
    const initialPayload = buildTrajectoryPayload()
    if (initialPayload.points.length === 0) return
    let isActive = true
    const sendTrajectory = () => {
      if (!isActive) return
      const payload = buildTrajectoryPayload()
      if (payload.points.length === 0) return
      fetch('/api/trajectory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }).catch(() => {})
    }
    sendTrajectory()
    const timer = window.setInterval(sendTrajectory, 1000)
    return () => {
      isActive = false
      window.clearInterval(timer)
    }
  }, [buildTrajectoryPayload, isTrajectoryLocked])

  const requestRender = useCallback(() => {
    invalidateRef.current?.()
  }, [])

  useEffect(() => {
    if (isOrbiting || isTransforming || isCloudTransforming) {
      requestRender()
    }
  }, [isOrbiting, isTransforming, isCloudTransforming, requestRender])

  const handleAddWaypointLocked = useCallback(() => {
    if (isTrajectoryLocked) return
    handleAddWaypoint()
  }, [handleAddWaypoint, isTrajectoryLocked])

  const handleDeleteWaypointLocked = useCallback(
    (id: string) => {
      if (isTrajectoryLocked) return
      handleDeleteWaypoint(id)
    },
    [handleDeleteWaypoint, isTrajectoryLocked]
  )

  const handleReorderWaypointLocked = useCallback(
    (id: string, direction: 'up' | 'down') => {
      if (isTrajectoryLocked) return
      handleReorderWaypoint(id, direction)
    },
    [handleReorderWaypoint, isTrajectoryLocked]
  )

  const handleUpdateWaypointLocked = useCallback(
    (
      id: string,
      position: [number, number, number],
      rotation: [number, number, number],
      takePhoto?: boolean
    ) => {
      if (isTrajectoryLocked) return
      handleUpdateWaypoint(id, position, rotation, takePhoto)
    },
    [handleUpdateWaypoint, isTrajectoryLocked]
  )

  const handleTogglePhotoLocked = useCallback(
    (id: string, value: boolean) => {
      if (isTrajectoryLocked) return
      handleTogglePhoto(id, value)
    },
    [handleTogglePhoto, isTrajectoryLocked]
  )

  const handleSelectWaypointLocked = useCallback(
    (id: string) => {
      if (isTrajectoryLocked) return
      handleSelectWaypointFromSidebar(id)
    },
    [handleSelectWaypointFromSidebar, isTrajectoryLocked]
  )

  const handleSelectWaypointSceneLocked = useCallback(
    (id: string) => {
      if (isTrajectoryLocked) return
      handleSelectWaypointFromScene(id)
    },
    [handleSelectWaypointFromScene, isTrajectoryLocked]
  )

  return (
    <div className="app-shell">
      <MissionTopbar trajectoryName={trajectoryName} stats={stats} />
      <div className="workspace">
        <Sidebar
          stats={stats}
          isLoading={isLoading}
          error={error}
          onFileSelect={handleFileSelect}
          onClosePointCloud={clearPointCloud}
          pointCloudFileName={pointCloudFileName}
          onAddWaypoint={handleAddWaypointLocked}
          waypoints={waypoints}
          selectedId={selectedId}
          onSelectWaypoint={handleSelectWaypointLocked}
          onDeleteWaypoint={handleDeleteWaypointLocked}
          onReorderWaypoint={handleReorderWaypointLocked}
          onUpdateWaypoint={handleUpdateWaypointLocked}
          onTogglePhoto={handleTogglePhotoLocked}
          trajectoryName={trajectoryName}
          trajectoryId={trajectoryId}
          trajectoryOptions={trajectoryOptions}
          onSelectTrajectory={handleSelectTrajectory}
          onSaveTrajectory={saveTrajectory}
          onExportTrajectoryFile={exportTrajectoryFile}
          onDeleteTrajectory={deleteTrajectory}
          onRenameTrajectory={setTrajectoryName}
          hasPointCloud={hasPointCloud}
          cloudRotation={cloudRotation}
          cloudOffset={cloudOffset}
          cloudTransformEnabled={cloudTransformEnabled}
          cloudTransformMode={cloudTransformMode}
          onToggleCloudTransform={() => setCloudTransformEnabled((prev) => !prev)}
          onSetCloudTransformMode={setCloudTransformMode}
          onSetCloudRotation={onSetCloudRotation}
          onTranslateCloud={onTranslateCloud}
          isTrajectoryLocked={isTrajectoryLocked}
        />
        <MissionViewport
          cloudFileName={cloudFileName}
          pointCloud={pointCloud}
          pointCloudChunks={pointCloudChunks}
          pointCloudChunkVersion={pointCloudChunkVersion}
          pointColors={pointColors}
          pointsColor={pointsColor}
          pointRadius={pointRadius}
          pointSizeAttenuation={pointSizeAttenuation}
          waypoints={waypoints}
          selectedId={selectedId}
          mode={mode}
          pathPoints={pathPoints}
          cloudTransformEnabled={cloudTransformEnabled}
          cloudTransformMode={cloudTransformMode}
          dronePose={dronePose}
          isTrajectoryLocked={isTrajectoryLocked}
          onToggleTrajectoryLock={() => setIsTrajectoryLocked((prev) => !prev)}
          isTransforming={isTransforming}
          isCloudTransforming={isCloudTransforming}
          onSetIsOrbiting={setIsOrbiting}
          onSetIsTransforming={setIsTransforming}
          onSetIsCloudTransforming={setIsCloudTransforming}
          onSelectWaypoint={handleSelectWaypointSceneLocked}
          onUpdateWaypoint={handleUpdateWaypointLocked}
          onPointerMissed={() => {
            if (isFocusingRef.current) return
            setSelectedId(null)
          }}
          onRequestRender={requestRender}
          onInvalidate={(fn) => {
            invalidateRef.current = fn
          }}
          onCloudObjectChange={onCloudObjectChange}
          renderManagerDeps={[
            hasPointCloud,
            pointColors,
            waypoints,
            selectedId,
            pathPoints,
            cloudRotation,
            cloudOffset,
            cloudTransformEnabled,
            cloudTransformMode,
            dronePose,
          ]}
          renderManagerActive={isOrbiting || isTransforming || isCloudTransforming}
          cloudGroupRef={cloudGroupRef}
          orbitRef={orbitRef}
        />
      </div>
      <MissionDock
        controlState={controlState}
        batteryPercent={batteryPercent}
        isDashboardOpen={isDashboardOpen}
        isMediaOpen={isMediaOpen}
        dashboardToggleRef={dashboardToggleRef}
        onToggleDashboard={() => {
          setIsDashboardOpen((prev) => !prev)
          setIsMediaOpen(false)
        }}
        onToggleMedia={() => {
          setIsMediaOpen((prev) => !prev)
          setIsDashboardOpen(false)
        }}
        onCloseDashboard={() => {
          dashboardToggleRef.current?.focus()
          setIsDashboardOpen(false)
        }}
        onCloseMedia={() => setIsMediaOpen(false)}
      />
    </div>
  )
}

export default MissionPlanner
