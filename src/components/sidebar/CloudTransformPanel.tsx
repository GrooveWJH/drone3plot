import { useState } from 'react'

type Axis = 'x' | 'y' | 'z'

export type CloudTransformPanelProps = {
  cloudTransformEnabled: boolean
  cloudTransformMode: 'translate' | 'rotate'
  onToggleCloudTransform: () => void
  onSetCloudTransformMode: (mode: 'translate' | 'rotate') => void
  cloudRotation: [number, number, number]
  cloudOffset: [number, number, number]
  onSetCloudRotation: (axis: Axis, value: number) => void
  onTranslateCloud: (axis: Axis, value: number) => void
}

const commitNumber = (value: string, onCommit: (num: number) => void) => {
  const trimmed = value.trim()
  if (trimmed === '') return false
  const parsed = Number(trimmed)
  if (!Number.isFinite(parsed)) return false
  onCommit(parsed)
  return true
}

const CloudTransformPanel = ({
  cloudTransformEnabled,
  cloudTransformMode,
  onToggleCloudTransform,
  onSetCloudTransformMode,
  cloudRotation,
  cloudOffset,
  onSetCloudRotation,
  onTranslateCloud,
}: CloudTransformPanelProps) => {
  const [cloudDrafts, setCloudDrafts] = useState<Partial<Record<Axis, string>>>({})
  const [rotationDrafts, setRotationDrafts] = useState<Partial<Record<Axis, string>>>({})

  const setCloudDraft = (axis: Axis, value: string) => {
    setCloudDrafts((prev) => ({ ...prev, [axis]: value }))
  }

  const clearCloudDraft = (axis: Axis) => {
    setCloudDrafts((prev) => {
      const next = { ...prev }
      delete next[axis]
      return next
    })
  }

  const setRotationDraft = (axis: Axis, value: string) => {
    setRotationDrafts((prev) => ({ ...prev, [axis]: value }))
  }

  const clearRotationDraft = (axis: Axis) => {
    setRotationDrafts((prev) => {
      const next = { ...prev }
      delete next[axis]
      return next
    })
  }

  return (
    <section className="dock-card">
      <div className="dock-card-head">
        <h2>点云变换</h2>
        <span className="chip muted">建模式操作</span>
      </div>
      <div className="transform-toolbar">
        <button
          className={`ghost ${cloudTransformEnabled ? 'active' : ''}`}
          onClick={onToggleCloudTransform}
        >
          {cloudTransformEnabled ? '关闭 3D 操作' : '开启 3D 操作'}
        </button>
        <div className="mode-toggle">
          <button
            className={cloudTransformMode === 'translate' ? 'active' : ''}
            onClick={() => onSetCloudTransformMode('translate')}
          >
            移动
          </button>
          <button
            className={cloudTransformMode === 'rotate' ? 'active' : ''}
            onClick={() => onSetCloudTransformMode('rotate')}
          >
            旋转
          </button>
        </div>
      </div>
      <div className="transform-columns">
        <div className="transform-block">
          <span className="transform-label">平移 (m)</span>
          <div className="axis-grid">
            {(['x', 'y', 'z'] as Axis[]).map((axis) => (
              <div key={axis} className="axis-row">
                <span className="axis-label">{axis.toUpperCase()}</span>
                <input
                  type="text"
                  inputMode="decimal"
                  value={
                    cloudDrafts[axis] ??
                    cloudOffset[axis === 'x' ? 0 : axis === 'y' ? 1 : 2].toFixed(2)
                  }
                  onChange={(event) => {
                    const value = event.target.value
                    setCloudDraft(axis, value)
                    commitNumber(value, (parsed) => onTranslateCloud(axis, parsed))
                  }}
                  onBlur={(event) => {
                    const raw = event.target.value
                    const committed = commitNumber(raw, (parsed) => onTranslateCloud(axis, parsed))
                    if (!committed) {
                      clearCloudDraft(axis)
                      return
                    }
                    clearCloudDraft(axis)
                  }}
                />
              </div>
            ))}
          </div>
        </div>
        <div className="transform-block">
          <span className="transform-label">旋转 (°)</span>
          <div className="axis-grid">
            {(['x', 'y', 'z'] as Axis[]).map((axis) => (
              <div key={axis} className="axis-row">
                <span className="axis-label">{axis.toUpperCase()}</span>
                <input
                  type="text"
                  inputMode="decimal"
                  value={
                    rotationDrafts[axis] ??
                    cloudRotation[axis === 'x' ? 0 : axis === 'y' ? 1 : 2].toFixed(1)
                  }
                  onChange={(event) => {
                    const value = event.target.value
                    setRotationDraft(axis, value)
                    commitNumber(value, (parsed) => onSetCloudRotation(axis, parsed))
                  }}
                  onBlur={(event) => {
                    const raw = event.target.value
                    const committed = commitNumber(raw, (parsed) => onSetCloudRotation(axis, parsed))
                    if (!committed) {
                      clearRotationDraft(axis)
                      return
                    }
                    clearRotationDraft(axis)
                  }}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

export default CloudTransformPanel
