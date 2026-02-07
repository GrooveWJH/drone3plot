import { useCallback, useEffect, useMemo, useReducer } from "react";

export type MissionState =
	| "idle"
	| "loading"
	| "ready"
	| "locked"
	| "executing"
	| "error";

type MissionEvent =
	| { type: "POINTCLOUD_LOADING" }
	| { type: "POINTCLOUD_LOADED" }
	| { type: "POINTCLOUD_CLEARED" }
	| { type: "LOCK_TRAJECTORY" }
	| { type: "UNLOCK_TRAJECTORY" }
	| { type: "EXECUTE" }
	| { type: "EXECUTE_DONE" }
	| { type: "EXECUTE_FAILED" };

const missionReducer = (
	state: MissionState,
	event: MissionEvent,
): MissionState => {
	switch (event.type) {
		case "POINTCLOUD_LOADING":
			if (state === "locked" || state === "executing") return state;
			return "loading";
		case "POINTCLOUD_LOADED":
			if (state === "locked" || state === "executing") return state;
			return "ready";
		case "POINTCLOUD_CLEARED":
			if (state === "locked" || state === "executing") return state;
			return "idle";
		case "LOCK_TRAJECTORY":
			return state === "executing" ? state : "locked";
		case "UNLOCK_TRAJECTORY":
			return "ready";
		case "EXECUTE":
			return state === "locked" ? "executing" : state;
		case "EXECUTE_DONE":
			return state === "executing" ? "locked" : state;
		case "EXECUTE_FAILED":
			return "error";
		default:
			return state;
	}
};

type MissionStateParams = {
	hasPointCloud: boolean;
	isLoading: boolean;
};

export const useMissionStateMachine = ({
	hasPointCloud,
	isLoading,
}: MissionStateParams) => {
	const [state, dispatch] = useReducer(missionReducer, "idle");

	useEffect(() => {
		if (hasPointCloud) {
			dispatch({ type: "POINTCLOUD_LOADED" });
		} else if (isLoading) {
			dispatch({ type: "POINTCLOUD_LOADING" });
		} else {
			dispatch({ type: "POINTCLOUD_CLEARED" });
		}
	}, [hasPointCloud, isLoading]);

	const lockTrajectory = useCallback(() => {
		dispatch({ type: "LOCK_TRAJECTORY" });
	}, []);

	const unlockTrajectory = useCallback(() => {
		dispatch({ type: "UNLOCK_TRAJECTORY" });
	}, []);

	const toggleTrajectoryLock = useCallback(() => {
		if (state === "locked") {
			dispatch({ type: "UNLOCK_TRAJECTORY" });
		} else {
			dispatch({ type: "LOCK_TRAJECTORY" });
		}
	}, [state]);

	const isTrajectoryLocked = state === "locked" || state === "executing";
	const canEditWaypoints = !isTrajectoryLocked;

	const derived = useMemo(
		() => ({
			state,
			isTrajectoryLocked,
			canEditWaypoints,
			lockTrajectory,
			unlockTrajectory,
			toggleTrajectoryLock,
		}),
		[
			state,
			isTrajectoryLocked,
			canEditWaypoints,
			lockTrajectory,
			unlockTrajectory,
			toggleTrajectoryLock,
		],
	);

	return derived;
};
