import type { RefObject } from 'react'
import type { ControlState } from './hooks/useControlStatus'

export type MissionDockProps = {
  controlState: ControlState
  batteryPercent: number | null
  isDashboardOpen: boolean
  isMediaOpen: boolean
  onToggleDashboard: () => void
  onToggleMedia: () => void
  onCloseDashboard: () => void
  onCloseMedia: () => void
  dashboardToggleRef: RefObject<HTMLButtonElement | null>
}

const MissionDock = ({
  controlState,
  batteryPercent,
  isDashboardOpen,
  isMediaOpen,
  onToggleDashboard,
  onToggleMedia,
  onCloseDashboard,
  onCloseMedia,
  dashboardToggleRef,
}: MissionDockProps) => (
  <>
    <div className="dashboard-dock">
      <button
        className="dashboard-tab with-icon"
        type="button"
        ref={dashboardToggleRef}
        onClick={onToggleDashboard}
      >
        <span
          className={`dashboard-status-dot ${controlState === 'drc_ready' ? 'online' : 'offline'}`}
          aria-hidden="true"
        />
        <span className="material-symbols-outlined" aria-hidden="true">
          flight
        </span>
        无人机控制
      </button>
      {controlState === 'drc_ready' && batteryPercent !== null && (
        <div className="dashboard-battery" aria-label={`电量 ${batteryPercent}%`}>
          <div className="dashboard-battery-fill" style={{ width: `${batteryPercent}%` }} />
        </div>
      )}
    </div>
    <div className="media-dock">
      <button
        className="media-tab with-icon"
        type="button"
        onClick={onToggleMedia}
        aria-label={isMediaOpen ? '折叠图片库' : '展开图片库'}
      >
        <span className="material-symbols-outlined" aria-hidden="true">
          photo
        </span>
        <span className="material-symbols-outlined" aria-hidden="true">
          {isMediaOpen ? 'chevron_right' : 'chevron_left'}
        </span>
      </button>
    </div>
    <div className={`dashboard-overlay ${isDashboardOpen ? 'is-open' : ''}`} aria-hidden={!isDashboardOpen}>
      <div className="dashboard-panel">
        <div className="dashboard-header">
          <span>无人机控制面板</span>
          <button
            className="icon dashboard-close with-icon"
            type="button"
            onClick={onCloseDashboard}
          >
            <span className="material-symbols-outlined" aria-hidden="true">
              expand_more
            </span>
            </button>
          </div>
        <iframe title="dashboard" src="/dashboard" />
      </div>
    </div>
    <div className={`media-drawer ${isMediaOpen ? 'is-open' : ''}`} aria-hidden={!isMediaOpen}>
      <div className="media-drawer-panel">
        <div className="media-drawer-header">
          <span>图片库</span>
          <button className="icon with-icon" type="button" onClick={onCloseMedia}>
            <span className="material-symbols-outlined" aria-hidden="true">
              chevron_right
            </span>
          </button>
        </div>
        <iframe title="media" src="/media" />
      </div>
    </div>
  </>
)

export default MissionDock
