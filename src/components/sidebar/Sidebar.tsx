import type { PointCloudStats, TrajectoryMeta, WaypointData } from '../../types/mission'
import CloudTransformPanel from './CloudTransformPanel'
import PointCloudPanel from './PointCloudPanel'
import TrajectoryPanel from './TrajectoryPanel'
import WaypointPanel from './WaypointPanel'

export type SidebarProps = {
  stats: PointCloudStats | null
  isLoading: boolean
  error: string | null
  onFileSelect: (file: File) => void
  onAddWaypoint: () => void
  waypoints: WaypointData[]
  selectedId: string | null
  onSelectWaypoint: (id: string) => void
  onDeleteWaypoint: (id: string) => void
  onReorderWaypoint: (id: string, direction: 'up' | 'down') => void
  onUpdateWaypoint: (
    id: string,
    position: [number, number, number],
    rotation: [number, number, number],
    takePhoto?: boolean
  ) => void
  onTogglePhoto: (id: string, value: boolean) => void
  trajectoryId: string
  trajectoryName: string
  trajectoryOptions: TrajectoryMeta[]
  onSelectTrajectory: (id: string) => void
  onSaveTrajectory: () => void
  onExportTrajectoryFile: () => void
  onCreateTrajectory: () => void
  onDeleteTrajectory: () => void
  onRenameTrajectory: (value: string) => void
  hasPointCloud: boolean
  cloudRotation: [number, number, number]
  cloudTransformEnabled: boolean
  cloudTransformMode: 'translate' | 'rotate'
  onToggleCloudTransform: () => void
  onSetCloudTransformMode: (mode: 'translate' | 'rotate') => void
  onSetCloudRotation: (axis: 'x' | 'y' | 'z', value: number) => void
  cloudOffset: [number, number, number]
  onTranslateCloud: (axis: 'x' | 'y' | 'z', value: number) => void
}

const Sidebar = ({
  stats,
  isLoading,
  error,
  onFileSelect,
  onAddWaypoint,
  waypoints,
  selectedId,
  onSelectWaypoint,
  onDeleteWaypoint,
  onReorderWaypoint,
  onUpdateWaypoint,
  onTogglePhoto,
  trajectoryId,
  trajectoryName,
  trajectoryOptions,
  onSelectTrajectory,
  onSaveTrajectory,
  onExportTrajectoryFile,
  onCreateTrajectory,
  onDeleteTrajectory,
  onRenameTrajectory,
  hasPointCloud,
  cloudRotation,
  cloudTransformEnabled,
  cloudTransformMode,
  onToggleCloudTransform,
  onSetCloudTransformMode,
  onSetCloudRotation,
  cloudOffset,
  onTranslateCloud,
}: SidebarProps) => (
  <aside className="control-dock">
    <div className="dock-hero">
      <h1>Mission Control</h1>
      <p>Draft, iterate, and export precise trajectories.</p>
    </div>

    <PointCloudPanel
      stats={stats}
      isLoading={isLoading}
      error={error}
      onFileSelect={onFileSelect}
    />

    <TrajectoryPanel
      trajectoryId={trajectoryId}
      trajectoryName={trajectoryName}
      trajectoryOptions={trajectoryOptions}
      onSelectTrajectory={onSelectTrajectory}
      onSaveTrajectory={onSaveTrajectory}
      onExportTrajectoryFile={onExportTrajectoryFile}
      onCreateTrajectory={onCreateTrajectory}
      onDeleteTrajectory={onDeleteTrajectory}
      onRenameTrajectory={onRenameTrajectory}
    />

    {hasPointCloud && (
      <CloudTransformPanel
        cloudTransformEnabled={cloudTransformEnabled}
        cloudTransformMode={cloudTransformMode}
        onToggleCloudTransform={onToggleCloudTransform}
        onSetCloudTransformMode={onSetCloudTransformMode}
        cloudRotation={cloudRotation}
        cloudOffset={cloudOffset}
        onSetCloudRotation={onSetCloudRotation}
        onTranslateCloud={onTranslateCloud}
      />
    )}

    <WaypointPanel
      onAddWaypoint={onAddWaypoint}
      waypoints={waypoints}
      selectedId={selectedId}
      onSelectWaypoint={onSelectWaypoint}
      onDeleteWaypoint={onDeleteWaypoint}
      onReorderWaypoint={onReorderWaypoint}
      onUpdateWaypoint={onUpdateWaypoint}
      onTogglePhoto={onTogglePhoto}
    />
  </aside>
)

export default Sidebar
