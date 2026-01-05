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

const MissionPlanner = () => {
  const orbitRef = useRef<OrbitControlsImpl | null>(null)
  const invalidateRef = useRef<(() => void) | null>(null)
  const [isOrbiting, setIsOrbiting] = useState(false)
  const [isTransforming, setIsTransforming] = useState(false)
  const [isCloudTransforming, setIsCloudTransforming] = useState(false)
  const [isDashboardOpen, setIsDashboardOpen] = useState(false)
  const [isMediaOpen, setIsMediaOpen] = useState(false)
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

  const requestRender = useCallback(() => {
    invalidateRef.current?.()
  }, [])

  useEffect(() => {
    if (isOrbiting || isTransforming || isCloudTransforming) {
      requestRender()
    }
  }, [isOrbiting, isTransforming, isCloudTransforming, requestRender])

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
          isTransforming={isTransforming}
          isCloudTransforming={isCloudTransforming}
          onSetIsOrbiting={setIsOrbiting}
          onSetIsTransforming={setIsTransforming}
          onSetIsCloudTransforming={setIsCloudTransforming}
          onSelectWaypoint={handleSelectWaypointFromScene}
          onUpdateWaypoint={handleUpdateWaypoint}
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
