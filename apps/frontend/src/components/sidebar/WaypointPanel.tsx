import { useEffect, useRef, useState } from "react";
import type { WaypointData } from "../../types/mission";

type DraftField = "x" | "y" | "z" | "yaw";

type DraftMap = Record<string, Partial<Record<DraftField, string>>>;

export type WaypointPanelProps = {
	waypoints: WaypointData[];
	selectedId: string | null;
	onSelectWaypoint: (id: string) => void;
	onDeleteWaypoint: (id: string) => void;
	onReorderWaypoint: (id: string, direction: "up" | "down") => void;
	onUpdateWaypoint: (
		id: string,
		position: [number, number, number],
		rotation: [number, number, number],
		takePhoto?: boolean,
	) => void;
	onTogglePhoto: (id: string, value: boolean) => void;
	onAddWaypoint: () => void;
	isLocked: boolean;
};

const radToDeg = (radians: number) => (radians * 180) / Math.PI;
const degToRad = (degrees: number) => (degrees * Math.PI) / 180;
const normalizeDegrees = (value: number) => {
	const wrapped = ((value % 360) + 360) % 360;
	return wrapped > 180 ? wrapped - 360 : wrapped;
};

const commitNumber = (value: string, onCommit: (num: number) => void) => {
	const trimmed = value.trim();
	if (trimmed === "") return false;
	const parsed = Number(trimmed);
	if (!Number.isFinite(parsed)) return false;
	onCommit(parsed);
	return true;
};

const WaypointPanel = ({
	waypoints,
	selectedId,
	onSelectWaypoint,
	onDeleteWaypoint,
	onReorderWaypoint,
	onUpdateWaypoint,
	onTogglePhoto,
	onAddWaypoint,
	isLocked,
}: WaypointPanelProps) => {
	const [drafts, setDrafts] = useState<DraftMap>({});
	const itemRefs = useRef<Map<string, HTMLDivElement | null>>(new Map());

	const setDraft = (id: string, field: DraftField, value: string) => {
		setDrafts((prev) => ({
			...prev,
			[id]: { ...prev[id], [field]: value },
		}));
	};

	const clearDraft = (id: string, field: DraftField) => {
		setDrafts((prev) => {
			const entry = { ...(prev[id] ?? {}) };
			delete entry[field];
			if (Object.keys(entry).length === 0) {
				const next = { ...prev };
				delete next[id];
				return next;
			}
			return { ...prev, [id]: entry };
		});
	};

	const handleBlur = (
		id: string,
		field: DraftField,
		value: string,
		onCommit: (num: number) => void,
	) => {
		const committed = commitNumber(value, onCommit);
		if (!committed) {
			clearDraft(id, field);
			return;
		}
		clearDraft(id, field);
	};

	useEffect(() => {
		if (!selectedId) return;
		const node = itemRefs.current.get(selectedId);
		node?.scrollIntoView({ behavior: "smooth", block: "nearest" });
	}, [selectedId]);

	return (
		<section className="dock-card">
			<div className="dock-card-head">
				<h2>航点</h2>
				<button
					className="primary with-icon"
					onClick={onAddWaypoint}
					disabled={isLocked}
				>
					<span className="material-symbols-outlined" aria-hidden="true">
						add
					</span>
					添加航点
				</button>
			</div>
			<div className="waypoint-list">
				{waypoints.length === 0 && <p className="empty">暂无航点</p>}
				{waypoints.map((waypoint, index) => (
					<div
						key={waypoint.id}
						className={`waypoint-card ${selectedId === waypoint.id ? "selected" : ""}`}
						ref={(node) => itemRefs.current.set(waypoint.id, node)}
						onPointerDown={(event) => {
							if (isLocked) return;
							const target = event.target as HTMLElement;
							if (target.closest("input, button, select, textarea")) return;
							onSelectWaypoint(waypoint.id);
						}}
					>
						<div className="waypoint-head">
							<button
								className="ghost waypoint-index"
								onClick={() => onSelectWaypoint(waypoint.id)}
								disabled={isLocked}
							>
								#{index + 1}
							</button>
							<div className="waypoint-actions">
								<button
									className="icon with-icon"
									onClick={() => onReorderWaypoint(waypoint.id, "up")}
									disabled={index === 0 || isLocked}
									aria-label="上移"
								>
									<span
										className="material-symbols-outlined"
										aria-hidden="true"
									>
										arrow_upward
									</span>
								</button>
								<button
									className="icon with-icon"
									onClick={() => onReorderWaypoint(waypoint.id, "down")}
									disabled={index === waypoints.length - 1 || isLocked}
									aria-label="下移"
								>
									<span
										className="material-symbols-outlined"
										aria-hidden="true"
									>
										arrow_downward
									</span>
								</button>
							</div>
						</div>
						<div className="waypoint-fields">
							<div className="waypoint-grid">
								<label className="field-stack">
									<span>x</span>
									<input
										type="text"
										inputMode="decimal"
										disabled={isLocked}
										value={
											drafts[waypoint.id]?.x ?? waypoint.position[0].toFixed(2)
										}
										onChange={(event) => {
											if (isLocked) return;
											const value = event.target.value;
											setDraft(waypoint.id, "x", value);
											commitNumber(value, (parsed) =>
												onUpdateWaypoint(
													waypoint.id,
													[parsed, waypoint.position[1], waypoint.position[2]],
													waypoint.rotation,
													waypoint.takePhoto,
												),
											);
										}}
										onBlur={(event) => {
											if (isLocked) return;
											handleBlur(
												waypoint.id,
												"x",
												event.target.value,
												(parsed) =>
													onUpdateWaypoint(
														waypoint.id,
														[
															parsed,
															waypoint.position[1],
															waypoint.position[2],
														],
														waypoint.rotation,
														waypoint.takePhoto,
													),
											);
										}}
									/>
								</label>
								<label className="field-stack">
									<span>y</span>
									<input
										type="text"
										inputMode="decimal"
										disabled={isLocked}
										value={
											drafts[waypoint.id]?.y ?? waypoint.position[1].toFixed(2)
										}
										onChange={(event) => {
											if (isLocked) return;
											const value = event.target.value;
											setDraft(waypoint.id, "y", value);
											commitNumber(value, (parsed) =>
												onUpdateWaypoint(
													waypoint.id,
													[waypoint.position[0], parsed, waypoint.position[2]],
													waypoint.rotation,
													waypoint.takePhoto,
												),
											);
										}}
										onBlur={(event) => {
											if (isLocked) return;
											handleBlur(
												waypoint.id,
												"y",
												event.target.value,
												(parsed) =>
													onUpdateWaypoint(
														waypoint.id,
														[
															waypoint.position[0],
															parsed,
															waypoint.position[2],
														],
														waypoint.rotation,
														waypoint.takePhoto,
													),
											);
										}}
									/>
								</label>
								<label className="field-stack">
									<span>z</span>
									<input
										type="text"
										inputMode="decimal"
										disabled={isLocked}
										value={
											drafts[waypoint.id]?.z ?? waypoint.position[2].toFixed(2)
										}
										onChange={(event) => {
											if (isLocked) return;
											const value = event.target.value;
											setDraft(waypoint.id, "z", value);
											commitNumber(value, (parsed) =>
												onUpdateWaypoint(
													waypoint.id,
													[waypoint.position[0], waypoint.position[1], parsed],
													waypoint.rotation,
													waypoint.takePhoto,
												),
											);
										}}
										onBlur={(event) => {
											if (isLocked) return;
											handleBlur(
												waypoint.id,
												"z",
												event.target.value,
												(parsed) =>
													onUpdateWaypoint(
														waypoint.id,
														[
															waypoint.position[0],
															waypoint.position[1],
															parsed,
														],
														waypoint.rotation,
														waypoint.takePhoto,
													),
											);
										}}
									/>
								</label>
								<label className="field-stack">
									<span>航向</span>
									<input
										type="text"
										inputMode="decimal"
										disabled={isLocked}
										value={
											drafts[waypoint.id]?.yaw ??
											normalizeDegrees(radToDeg(waypoint.rotation[2])).toFixed(
												1,
											)
										}
										onChange={(event) => {
											if (isLocked) return;
											const value = event.target.value;
											setDraft(waypoint.id, "yaw", value);
											commitNumber(value, (parsed) => {
												const normalized = normalizeDegrees(parsed);
												onUpdateWaypoint(
													waypoint.id,
													waypoint.position,
													[0, 0, degToRad(normalized)],
													waypoint.takePhoto,
												);
											});
										}}
										onBlur={(event) => {
											if (isLocked) return;
											const raw = event.target.value;
											const committed = commitNumber(raw, (parsed) => {
												const normalized = normalizeDegrees(parsed);
												onUpdateWaypoint(
													waypoint.id,
													waypoint.position,
													[0, 0, degToRad(normalized)],
													waypoint.takePhoto,
												);
											});
											if (!committed) {
												clearDraft(waypoint.id, "yaw");
												return;
											}
											clearDraft(waypoint.id, "yaw");
										}}
									/>
								</label>
							</div>
							<div className="waypoint-footer">
								<label className="toggle-inline photo-toggle">
									<input
										type="checkbox"
										checked={Boolean(waypoint.takePhoto)}
										disabled={isLocked}
										onChange={(event) =>
											onTogglePhoto(waypoint.id, event.target.checked)
										}
									/>
									<span className="toggle-box" aria-hidden="true" />
									<span
										className="material-symbols-outlined"
										aria-hidden="true"
									>
										photo_camera
									</span>
									拍照
								</label>
								<button
									className="icon danger with-icon"
									onClick={() => onDeleteWaypoint(waypoint.id)}
									disabled={isLocked}
									aria-label="删除"
								>
									<span
										className="material-symbols-outlined"
										aria-hidden="true"
									>
										delete
									</span>
									删除
								</button>
							</div>
						</div>
					</div>
				))}
			</div>
		</section>
	);
};

export default WaypointPanel;
