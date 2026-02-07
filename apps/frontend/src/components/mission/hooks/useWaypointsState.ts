import type { RefObject } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { UI_CONFIG } from "../../../config/ui";
import type { TransformMode, WaypointData } from "../../../types/mission";
import { createWaypoint, offsetWaypoint, originWaypoint } from "../utils";

export const useWaypointsState = (
	orbitRef: RefObject<OrbitControlsImpl | null>,
) => {
	const [waypoints, setWaypoints] = useState<WaypointData[]>([
		createWaypoint([0, 0, 0]),
		createWaypoint([4, 0, 2]),
	]);
	const [selectedId, setSelectedId] = useState<string | null>(null);
	const [focusTargetId, setFocusTargetId] = useState<string | null>(null);
	const [mode] = useState<TransformMode>("translate");
	const waypointsRef = useRef<WaypointData[]>([]);
	const focusAnimationRef = useRef<number | null>(null);
	const isFocusingRef = useRef(false);

	const handleAddWaypoint = useCallback(() => {
		setWaypoints((prev) => {
			const last = prev[prev.length - 1];
			const nextPosition = last
				? offsetWaypoint(last.position)
				: originWaypoint;
			return [...prev, createWaypoint(nextPosition)];
		});
	}, []);

	const handleUpdateWaypoint = useCallback(
		(
			id: string,
			position: [number, number, number],
			rotation: [number, number, number],
			takePhoto?: boolean,
		) => {
			setWaypoints((prev) =>
				prev.map((waypoint) =>
					waypoint.id === id
						? {
								...waypoint,
								position,
								rotation,
								takePhoto: takePhoto ?? waypoint.takePhoto,
							}
						: waypoint,
				),
			);
		},
		[],
	);

	const handleTogglePhoto = useCallback((id: string, value: boolean) => {
		setWaypoints((prev) =>
			prev.map((waypoint) =>
				waypoint.id === id ? { ...waypoint, takePhoto: value } : waypoint,
			),
		);
	}, []);

	const handleDeleteWaypoint = useCallback((id: string) => {
		setWaypoints((prev) => prev.filter((waypoint) => waypoint.id !== id));
		setSelectedId((prev) => (prev === id ? null : prev));
	}, []);

	const handleReorderWaypoint = useCallback(
		(id: string, direction: "up" | "down") => {
			setWaypoints((prev) => {
				const index = prev.findIndex((waypoint) => waypoint.id === id);
				if (index < 0) return prev;
				const targetIndex = direction === "up" ? index - 1 : index + 1;
				if (targetIndex < 0 || targetIndex >= prev.length) return prev;
				const next = [...prev];
				const [moved] = next.splice(index, 1);
				next.splice(targetIndex, 0, moved);
				return next;
			});
		},
		[],
	);

	useEffect(() => {
		waypointsRef.current = waypoints;
	}, [waypoints]);

	const focusOnWaypoint = useCallback(
		(waypointId: string) => {
			const targetWaypoint = waypointsRef.current.find(
				(waypoint) => waypoint.id === waypointId,
			);
			if (!targetWaypoint || !orbitRef.current) return;
			if (focusAnimationRef.current !== null) {
				cancelAnimationFrame(focusAnimationRef.current);
				focusAnimationRef.current = null;
			}
			const startTarget = orbitRef.current.target.clone();
			const endTarget = {
				x: targetWaypoint.position[0],
				y: targetWaypoint.position[1],
				z: targetWaypoint.position[2],
			};
			const duration = Math.max(0, UI_CONFIG.camera.focusDuration) * 1000;
			if (duration === 0) {
				orbitRef.current.target.set(endTarget.x, endTarget.y, endTarget.z);
				orbitRef.current.update();
				isFocusingRef.current = false;
				return;
			}
			isFocusingRef.current = true;
			const startTime = performance.now();
			const animate = (time: number) => {
				const elapsed = time - startTime;
				const t = Math.min(1, elapsed / duration);
				const ease = t * (2 - t);
				orbitRef.current?.target.set(
					startTarget.x + (endTarget.x - startTarget.x) * ease,
					startTarget.y + (endTarget.y - startTarget.y) * ease,
					startTarget.z + (endTarget.z - startTarget.z) * ease,
				);
				orbitRef.current?.update();
				if (t < 1) {
					focusAnimationRef.current = requestAnimationFrame(animate);
				} else {
					focusAnimationRef.current = null;
					isFocusingRef.current = false;
				}
			};
			focusAnimationRef.current = requestAnimationFrame(animate);
		},
		[orbitRef],
	);

	useEffect(() => {
		if (!focusTargetId) return;
		focusOnWaypoint(focusTargetId);
		return () => {
			if (focusAnimationRef.current !== null) {
				cancelAnimationFrame(focusAnimationRef.current);
				focusAnimationRef.current = null;
			}
		};
	}, [focusOnWaypoint, focusTargetId]);

	const handleSelectWaypointFromSidebar = useCallback((id: string) => {
		setSelectedId(id);
		setFocusTargetId(id);
	}, []);

	const handleSelectWaypointFromScene = useCallback((id: string) => {
		setSelectedId(id);
	}, []);

	const pathPoints = useMemo(() => {
		if (waypoints.length <= 1) return null;
		return waypoints.map(
			(waypoint) => [...waypoint.position] as [number, number, number],
		);
	}, [waypoints]);

	return {
		waypoints,
		selectedId,
		mode,
		pathPoints,
		isFocusingRef,
		setSelectedId,
		setWaypoints,
		handleAddWaypoint,
		handleUpdateWaypoint,
		handleDeleteWaypoint,
		handleReorderWaypoint,
		handleTogglePhoto,
		handleSelectWaypointFromSidebar,
		handleSelectWaypointFromScene,
	};
};
