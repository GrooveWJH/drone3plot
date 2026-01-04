import type { PointCloudStats } from '../../types/mission'

export type PointCloudPanelProps = {
  stats: PointCloudStats | null
  isLoading: boolean
  error: string | null
  onFileSelect: (file: File) => void
}

const formatNumber = (value: number) => new Intl.NumberFormat('en-US').format(value)

const PointCloudPanel = ({ stats, isLoading, error, onFileSelect }: PointCloudPanelProps) => (
  <section className="dock-card">
    <div className="dock-card-head">
      <h2>点云</h2>
      <span className="chip">LAS / LAZ / PCD</span>
    </div>
    <div className="field">
      <label htmlFor="las-file">导入点云</label>
      <input
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
    {stats && (
      <div className="stats-grid">
        <div className="stat-card">
          <span>总点数</span>
          <strong>{formatNumber(stats.totalPoints)}</strong>
        </div>
        <div className="stat-card">
          <span>加载点数</span>
          <strong>{formatNumber(stats.loadedPoints)}</strong>
        </div>
        <div className="stat-card">
          <span>采样步长</span>
          <strong>{stats.sampleEvery}</strong>
        </div>
      </div>
    )}
    {isLoading && <div className="status-pill">正在加载 LAS…</div>}
    {error && <div className="status-pill error">{error}</div>}
  </section>
)

export default PointCloudPanel
