import { useState } from 'react'
import type { PointCloudStats, WaypointData } from '../types/mission'
import { UI_CONFIG } from '../config/ui'
import type { TrajectoryMeta } from '../types/mission'

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
  onExportTrajectory: () => void
  onCreateTrajectory: () => void
  onRenameTrajectory: (value: string) => void
  cloudRotation: [number, number, number]
  onRotateCloud: (axis: 'x' | 'y' | 'z', delta: number) => void
}

const formatNumber = (value: number) => new Intl.NumberFormat('en-US').format(value)
const radToDeg = (radians: number) => (radians * 180) / Math.PI
const degToRad = (degrees: number) => (degrees * Math.PI) / 180
const normalizeDegrees = (value: number) => ((value % 360) + 360) % 360

type DraftField = 'x' | 'y' | 'z' | 'yaw'
type DraftMap = Record<string, Partial<Record<DraftField, string>>>

type Axis = 'x' | 'y' | 'z'

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
  onExportTrajectory,
  onCreateTrajectory,
  onRenameTrajectory,
  cloudRotation,
  onRotateCloud,
}: SidebarProps) => {
  const [drafts, setDrafts] = useState<DraftMap>({})

  const setDraft = (id: string, field: DraftField, value: string) => {
    setDrafts((prev) => ({
      ...prev,
      [id]: { ...prev[id], [field]: value },
    }))
  }

  const clearDraft = (id: string, field: DraftField) => {
    setDrafts((prev) => {
      const entry = { ...(prev[id] ?? {}) }
      delete entry[field]
      if (Object.keys(entry).length === 0) {
        const { [id]: _removed, ...rest } = prev
        return rest
      }
      return { ...prev, [id]: entry }
    })
  }

  const commitNumber = (value: string, onCommit: (num: number) => void) => {
    const trimmed = value.trim()
    if (trimmed === '') return false
    const parsed = Number(trimmed)
    if (!Number.isFinite(parsed)) return false
    onCommit(parsed)
    return true
  }

  const handleBlur = (
    id: string,
    field: DraftField,
    value: string,
    onCommit: (num: number) => void
  ) => {
    const committed = commitNumber(value, onCommit)
    if (!committed) {
      clearDraft(id, field)
      return
    }
    clearDraft(id, field)
  }
  return (
    <aside className="panel">
      <div className="panel-header">
        <div>
          <h1>Drone Mission Planner</h1>
          <p>Point cloud as a reference, waypoints as the mission core.</p>
        </div>
      </div>

      <section className="panel-section">
        <h2>点云</h2>
        <div className="field">
          <label htmlFor="las-file">加载 LAS/LAZ</label>
          <input
            id="las-file"
            type="file"
            accept=".las,.laz"
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) onFileSelect(file)
              event.currentTarget.value = ''
            }}
          />
        </div>
        {stats && (
          <div className="stats">
            <div>
              <span>总点数</span>
              <strong>{formatNumber(stats.totalPoints)}</strong>
            </div>
            <div>
              <span>加载点数</span>
              <strong>{formatNumber(stats.loadedPoints)}</strong>
            </div>
            <div>
              <span>采样步长</span>
              <strong>{stats.sampleEvery}</strong>
            </div>
          </div>
        )}
        {isLoading && <div className="status">正在加载 LAS…</div>}
        {error && <div className="status error">{error}</div>}
      </section>

      <section className="panel-section">
        <h2>航线</h2>
        <div className="field">
          <label htmlFor="trajectory-select">选择航线</label>
          <select
            id="trajectory-select"
            value={trajectoryId}
            onChange={(event) => onSelectTrajectory(event.target.value)}
          >
            {trajectoryOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="trajectory-name">航线名称</label>
          <input
            id="trajectory-name"
            type="text"
            value={trajectoryName}
            onChange={(event) => onRenameTrajectory(event.target.value)}
          />
        </div>
        <div className="trajectory-actions">
          <button className="ghost" onClick={onCreateTrajectory}>
            新建航线
          </button>
          <button className="primary" onClick={onExportTrajectory}>
            保存航线
          </button>
        </div>
        <p className="field-help">
          保存后会下载 JSON 文件，请放入 trajectories 目录。
        </p>
      </section>

      <section className="panel-section">
        <h2>点云旋转</h2>
        <div className="rotation-grid">
          {(['x', 'y', 'z'] as Axis[]).map((axis) => (
            <div key={axis} className="rotation-row">
              <span className="rotation-label">{axis.toUpperCase()}</span>
              <div className="rotation-buttons">
                <button
                  className="icon"
                  onClick={() => onRotateCloud(axis, -UI_CONFIG.pointCloud.rotationStep)}
                >
                  -{UI_CONFIG.pointCloud.rotationStep}
                </button>
                <button
                  className="icon"
                  onClick={() => onRotateCloud(axis, UI_CONFIG.pointCloud.rotationStep)}
                >
                  +{UI_CONFIG.pointCloud.rotationStep}
                </button>
              </div>
              <span className="rotation-value">{cloudRotation[axis === 'x' ? 0 : axis === 'y' ? 1 : 2]}°</span>
            </div>
          ))}
        </div>
      </section>

      <section className="panel-section">
        <div className="section-header">
          <h2>航点</h2>
          <button className="primary" onClick={onAddWaypoint}>
            添加航点
          </button>
        </div>
        <div className="waypoint-list">
          {waypoints.length === 0 && <p className="empty">暂无航点</p>}
          {waypoints.map((waypoint, index) => (
            <div
              key={waypoint.id}
              className={`waypoint-row ${selectedId === waypoint.id ? 'selected' : ''}`}
            >
              <div className="waypoint-meta">
                <button className="ghost" onClick={() => onSelectWaypoint(waypoint.id)}>
                  #{index + 1}
                </button>
                <div className="waypoint-coords compact">
                  <div className="coord-row compact-row">
                    <label>
                      x
                      <input
                        type="text"
                        inputMode="decimal"
                        value={drafts[waypoint.id]?.x ?? waypoint.position[0].toFixed(2)}
                        onChange={(event) => {
                          const value = event.target.value
                          setDraft(waypoint.id, 'x', value)
                          commitNumber(value, (parsed) =>
                            onUpdateWaypoint(
                              waypoint.id,
                              [parsed, waypoint.position[1], waypoint.position[2]],
                              waypoint.rotation,
                              waypoint.takePhoto
                            )
                          )
                        }}
                        onBlur={(event) => {
                          handleBlur(
                            waypoint.id,
                            'x',
                            event.target.value,
                            (parsed) =>
                              onUpdateWaypoint(
                                waypoint.id,
                                [parsed, waypoint.position[1], waypoint.position[2]],
                                waypoint.rotation,
                                waypoint.takePhoto
                              )
                          )
                        }}
                      />
                    </label>
                    <label>
                      y
                      <input
                        type="text"
                        inputMode="decimal"
                        value={drafts[waypoint.id]?.y ?? waypoint.position[1].toFixed(2)}
                        onChange={(event) => {
                          const value = event.target.value
                          setDraft(waypoint.id, 'y', value)
                          commitNumber(value, (parsed) =>
                            onUpdateWaypoint(
                              waypoint.id,
                              [waypoint.position[0], parsed, waypoint.position[2]],
                              waypoint.rotation,
                              waypoint.takePhoto
                            )
                          )
                        }}
                        onBlur={(event) => {
                          handleBlur(
                            waypoint.id,
                            'y',
                            event.target.value,
                            (parsed) =>
                              onUpdateWaypoint(
                                waypoint.id,
                                [waypoint.position[0], parsed, waypoint.position[2]],
                                waypoint.rotation,
                                waypoint.takePhoto
                              )
                          )
                        }}
                      />
                    </label>
                    <label>
                      z
                      <input
                        type="text"
                        inputMode="decimal"
                        value={drafts[waypoint.id]?.z ?? waypoint.position[2].toFixed(2)}
                        onChange={(event) => {
                          const value = event.target.value
                          setDraft(waypoint.id, 'z', value)
                          commitNumber(value, (parsed) =>
                            onUpdateWaypoint(
                              waypoint.id,
                              [waypoint.position[0], waypoint.position[1], parsed],
                              waypoint.rotation,
                              waypoint.takePhoto
                            )
                          )
                        }}
                        onBlur={(event) => {
                          handleBlur(
                            waypoint.id,
                            'z',
                            event.target.value,
                            (parsed) =>
                              onUpdateWaypoint(
                                waypoint.id,
                                [waypoint.position[0], waypoint.position[1], parsed],
                                waypoint.rotation,
                                waypoint.takePhoto
                              )
                          )
                        }}
                      />
                    </label>
                    <label>
                      yaw
                      <input
                        type="text"
                        inputMode="decimal"
                        value={
                          drafts[waypoint.id]?.yaw ??
                          normalizeDegrees(radToDeg(waypoint.rotation[1])).toFixed(1)
                        }
                        onChange={(event) => {
                          const value = event.target.value
                          setDraft(waypoint.id, 'yaw', value)
                          commitNumber(value, (parsed) => {
                            const normalized = normalizeDegrees(parsed)
                            onUpdateWaypoint(
                              waypoint.id,
                              waypoint.position,
                              [0, degToRad(normalized), 0],
                              waypoint.takePhoto
                            )
                          })
                        }}
                        onBlur={(event) => {
                          const raw = event.target.value
                          const committed = commitNumber(raw, (parsed) => {
                            const normalized = normalizeDegrees(parsed)
                            onUpdateWaypoint(
                              waypoint.id,
                              waypoint.position,
                              [0, degToRad(normalized), 0],
                              waypoint.takePhoto
                            )
                          })
                          if (!committed) {
                            clearDraft(waypoint.id, 'yaw')
                            return
                          }
                          clearDraft(waypoint.id, 'yaw')
                        }}
                      />
                    </label>
                  </div>
                  <div className="coord-row compact-actions">
                    <label className="toggle-inline">
                      <input
                        type="checkbox"
                        checked={Boolean(waypoint.takePhoto)}
                        onChange={(event) => onTogglePhoto(waypoint.id, event.target.checked)}
                      />
                      拍照
                    </label>
                    <button
                      className="icon danger"
                      onClick={() => onDeleteWaypoint(waypoint.id)}
                      aria-label="删除"
                    >
                      删除
                    </button>
                  </div>
                </div>
              </div>
              <div className="waypoint-actions">
                <button
                  className="icon"
                  onClick={() => onReorderWaypoint(waypoint.id, 'up')}
                  disabled={index === 0}
                  aria-label="上移"
                >
                  ↑
                </button>
                <button
                  className="icon"
                  onClick={() => onReorderWaypoint(waypoint.id, 'down')}
                  disabled={index === waypoints.length - 1}
                  aria-label="下移"
                >
                  ↓
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

    </aside>
  )
}

export default Sidebar
