import type { PointCloudStats } from "../../types/mission";
import { formatNumber } from "./utils";

export type MissionTopbarProps = {
	trajectoryName: string;
	stats: PointCloudStats | null;
};

const MissionTopbar = ({ trajectoryName, stats }: MissionTopbarProps) => (
	<header className="app-topbar">
		<div className="brand">
			<img className="brand-logo" src="/logo_yundrone.svg" alt="标识" />
		</div>
		<div className="topbar-meta">
			<div className="meta-card">
				<span>航线</span>
				<strong>{trajectoryName}</strong>
			</div>
			<div className="meta-card">
				<span>点云</span>
				<strong>
					{stats ? `${formatNumber(stats.loadedPoints)} 点` : "未加载"}
				</strong>
			</div>
		</div>
	</header>
);

export default MissionTopbar;
