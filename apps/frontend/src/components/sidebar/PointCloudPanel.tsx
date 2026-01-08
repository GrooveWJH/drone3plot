import { useRef } from 'react'
import type { PointCloudStats } from '../../types/mission'

export type PointCloudPanelProps = {
  stats: PointCloudStats | null
  isLoading: boolean
  error: string | null
  onFileSelect: (file: File) => void
  onClosePointCloud: () => void
  fileName: string | null
}

const formatNumber = (value: number) => new Intl.NumberFormat('en-US').format(value)

const PointCloudPanel = ({
  stats,
  isLoading,
  error,
  onFileSelect,
  onClosePointCloud,
  fileName,
}: PointCloudPanelProps) => {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const totalTarget = stats
    ? Math.max(1, Math.ceil(stats.totalPoints / Math.max(1, stats.sampleEvery)))
    : null
  const progress = stats && totalTarget ? Math.min(1, stats.loadedPoints / totalTarget) : null
  return (
    <section className="dock-card">
      <div className="dock-card-head">
        <h2>点云</h2>
        <span className="chip">LAS / LAZ / PCD</span>
      </div>
      <div className="field">
        <label htmlFor="las-file">导入点云</label>
        <div className="inline-actions">
          <button
            className="ghost with-icon"
            type="button"
            onClick={() => inputRef.current?.click()}
          >
            <span className="material-symbols-outlined" aria-hidden="true">
              folder_open
            </span>
            选择文件
          </button>
          <button
            className="ghost danger with-icon"
            type="button"
            onClick={onClosePointCloud}
            disabled={!fileName}
          >
            <span className="material-symbols-outlined" aria-hidden="true">
              close
            </span>
            关闭
          </button>
        </div>
        <span className="field-hint">{fileName ?? '未选择文件'}</span>
        <input
          ref={inputRef}
          id="las-file"
          type="file"
          accept=".las,.laz,.pcd"
          className="file-input"
          onChange={(event) => {
            const file = event.target.files?.[0]
            if (file) onFileSelect(file)
            event.currentTarget.value = ''
          }}
        />
      </div>
      {isLoading && (
        <div className="status-pill">正在加载点云…</div>
      )}
      {isLoading && progress !== null && (
        <div className="progress-block">
          <div className="progress-track">
            <div
              className="progress-fill"
              style={{ width: `${Math.round(progress * 100)}%` }}
            />
          </div>
          <div className="progress-meta">
            <span>
              {formatNumber(Math.min(stats.loadedPoints, totalTarget))} / {formatNumber(totalTarget)}
            </span>
            <span>{Math.round(progress * 100)}%</span>
          </div>
        </div>
      )}
      {error && <div className="status-pill error">{error}</div>}
    </section>
  )
}

export default PointCloudPanel
