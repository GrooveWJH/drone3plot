import { useEffect, useMemo, useRef, useState } from "react";
import { io } from "socket.io-client";

export type SlamSnapshot = {
	x: number | null;
	y: number | null;
	z: number | null;
	yaw: number | null;
	status: string | null;
};

export type DronePose = {
	x: number;
	y: number;
	z: number;
	yaw: number;
};

const isFiniteNumber = (value: unknown): value is number =>
	typeof value === "number" && Number.isFinite(value);

const POSE_STALE_MS = 3000;

export const useSlamPose = () => {
	const [slamSnapshot, setSlamSnapshot] = useState<SlamSnapshot | null>(null);
	const [isStale, setIsStale] = useState(false);
	const staleTimerRef = useRef<number | null>(null);

	useEffect(() => {
		const socket = io("/pose");
		socket.on("pose", (payload) => {
			if (!payload) return;
			const { x, y, z, yaw, status } = payload as {
				x?: number | null;
				y?: number | null;
				z?: number | null;
				yaw?: number | null;
				status?: string | null;
			};
			setSlamSnapshot({
				x: x ?? null,
				y: y ?? null,
				z: z ?? null,
				yaw: yaw ?? null,
				status: status ?? null,
			});
			setIsStale(false);
			if (staleTimerRef.current) {
				window.clearTimeout(staleTimerRef.current);
			}
			staleTimerRef.current = window.setTimeout(() => {
				setIsStale(true);
			}, POSE_STALE_MS);
		});
		return () => {
			socket.disconnect();
			if (staleTimerRef.current) {
				window.clearTimeout(staleTimerRef.current);
			}
		};
	}, []);

	const dronePose = useMemo<DronePose | null>(() => {
		if (!slamSnapshot || isStale) return null;
		if (
			!isFiniteNumber(slamSnapshot.x) ||
			!isFiniteNumber(slamSnapshot.y) ||
			!isFiniteNumber(slamSnapshot.z)
		) {
			return null;
		}
		return {
			x: slamSnapshot.x,
			y: slamSnapshot.y,
			z: slamSnapshot.z,
			yaw: isFiniteNumber(slamSnapshot.yaw) ? slamSnapshot.yaw : 0,
		};
	}, [slamSnapshot, isStale]);

	return { slamSnapshot, dronePose };
};
