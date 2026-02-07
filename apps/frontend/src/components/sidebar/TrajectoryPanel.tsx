import type { TrajectoryMeta } from "../../types/mission";

export type TrajectoryPanelProps = {
	trajectoryId: string;
	trajectoryName: string;
	trajectoryOptions: TrajectoryMeta[];
	onSelectTrajectory: (id: string) => void;
	onSaveTrajectory: () => void;
	onExportTrajectoryFile: () => void;
	onDeleteTrajectory: () => void;
	onRenameTrajectory: (value: string) => void;
};

const TrajectoryPanel = ({
	trajectoryId,
	trajectoryName,
	trajectoryOptions,
	onSelectTrajectory,
	onSaveTrajectory,
	onExportTrajectoryFile,
	onDeleteTrajectory,
	onRenameTrajectory,
}: TrajectoryPanelProps) => (
	<section className="dock-card">
		<div className="dock-card-head">
			<h2>航线</h2>
			<span className="chip muted">规划</span>
		</div>
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
		<div className="button-row">
			<button className="primary with-icon" onClick={onSaveTrajectory}>
				<span className="material-symbols-outlined" aria-hidden="true">
					save
				</span>
				保存
			</button>
			<button className="ghost with-icon" onClick={onExportTrajectoryFile}>
				<span className="material-symbols-outlined" aria-hidden="true">
					download
				</span>
				导出
			</button>
			<button className="ghost danger with-icon" onClick={onDeleteTrajectory}>
				<span className="material-symbols-outlined" aria-hidden="true">
					delete
				</span>
				删除
			</button>
		</div>
	</section>
);

export default TrajectoryPanel;
