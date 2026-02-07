import type { WaypointData } from "../../types/mission";

export const createId = () =>
	globalThis.crypto?.randomUUID?.() ??
	`wp-${Math.random().toString(36).slice(2, 10)}`;

export const createWaypoint = (
	position: [number, number, number],
): WaypointData => ({
	id: createId(),
	position,
	rotation: [0, 0, 0],
	takePhoto: false,
});

export const offsetWaypoint = (position: [number, number, number]) =>
	[position[0] + 2, position[1], position[2]] as [number, number, number];

export const originWaypoint: [number, number, number] = [0, 0, 0];

export const formatNumber = (value: number) =>
	new Intl.NumberFormat("en-US").format(value);
export const clampRotation = (value: number) =>
	Math.max(-180, Math.min(180, value));
export const degToRad = (degrees: number) => (degrees * Math.PI) / 180;
export const radToDeg = (radians: number) => (radians * 180) / Math.PI;
export const normalizeDegrees = (value: number) => {
	const wrapped = ((value % 360) + 360) % 360;
	return wrapped > 180 ? wrapped - 360 : wrapped;
};

export const TRAJECTORY_ID_STORAGE_KEY = "trajectory:selected";
