import { useState } from 'react'
import type { PointCloudStats, WaypointData } from '../types/mission'
import { UI_CONFIG } from '../config/ui'

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
  onUpdateWaypoint: (id: string, position: [number, number, number], rotation: [number, number, number]) => void
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
        <h2>Point Cloud</h2>
        <div className="field">
          <label htmlFor="las-file">Load LAS/LAZ</label>
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
              <span>Total points</span>
              <strong>{formatNumber(stats.totalPoints)}</strong>
            </div>
            <div>
              <span>Loaded points</span>
              <strong>{formatNumber(stats.loadedPoints)}</strong>
            </div>
            <div>
              <span>Sample every</span>
              <strong>{stats.sampleEvery}</strong>
            </div>
          </div>
        )}
        {isLoading && <div className="status">Streaming LAS chunks…</div>}
        {error && <div className="status error">{error}</div>}
      </section>

      <section className="panel-section">
        <h2>Cloud Rotation</h2>
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
          <h2>Waypoints</h2>
          <button className="primary" onClick={onAddWaypoint}>
            Add waypoint
          </button>
        </div>
        <div className="waypoint-list">
          {waypoints.length === 0 && <p className="empty">No waypoints yet.</p>}
          {waypoints.map((waypoint, index) => (
            <div
              key={waypoint.id}
              className={`waypoint-row ${selectedId === waypoint.id ? 'selected' : ''}`}
            >
              <div className="waypoint-meta">
                <button className="ghost" onClick={() => onSelectWaypoint(waypoint.id)}>
                  #{index + 1}
                </button>
                <div className="waypoint-coords">
                  <div className="coord-row xyz-row">
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
                              waypoint.rotation
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
                                waypoint.rotation
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
                              waypoint.rotation
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
                                waypoint.rotation
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
                              waypoint.rotation
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
                                waypoint.rotation
                              )
                          )
                        }}
                      />
                    </label>
                  </div>
                  <div className="coord-row yaw-row">
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
                              [0, degToRad(normalized), 0]
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
                              [0, degToRad(normalized), 0]
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
                    <button
                      className="icon danger"
                      onClick={() => onDeleteWaypoint(waypoint.id)}
                      aria-label="Delete"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              </div>
              <div className="waypoint-actions">
                <button
                  className="icon"
                  onClick={() => onReorderWaypoint(waypoint.id, 'up')}
                  disabled={index === 0}
                  aria-label="Move up"
                >
                  ↑
                </button>
                <button
                  className="icon"
                  onClick={() => onReorderWaypoint(waypoint.id, 'down')}
                  disabled={index === waypoints.length - 1}
                  aria-label="Move down"
                >
                  ↓
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="panel-section hint">
        <h2>Hints</h2>
        <ul>
          <li>Click a waypoint to edit.</li>
          <li>Use Move/Rotate to set position and heading.</li>
          <li>Point cloud is streamed with a fixed memory budget.</li>
        </ul>
      </section>
    </aside>
  )
}

export default Sidebar
