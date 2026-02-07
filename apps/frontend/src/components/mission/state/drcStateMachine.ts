import { useCallback, useMemo, useReducer } from "react";

export type DrcState =
	| "idle"
	| "disconnected"
	| "waiting_for_user"
	| "drc_ready"
	| "error"
	| "unavailable";

type DrcEvent =
	| { type: "STATUS"; state: DrcState; lastError?: string | null }
	| { type: "UNAVAILABLE" };

type DrcSnapshot = {
	state: DrcState;
	lastError: string | null;
};

const drcReducer = (state: DrcSnapshot, event: DrcEvent): DrcSnapshot => {
	switch (event.type) {
		case "STATUS":
			return {
				state: event.state,
				lastError: event.lastError ?? null,
			};
		case "UNAVAILABLE":
			return { state: "unavailable", lastError: null };
		default:
			return state;
	}
};

export const useDrcStateMachine = () => {
	const [snapshot, dispatch] = useReducer(drcReducer, {
		state: "disconnected",
		lastError: null,
	});

	const updateStatus = useCallback(
		(state: DrcState, lastError?: string | null) => {
			dispatch({ type: "STATUS", state, lastError });
		},
		[],
	);

	const markUnavailable = useCallback(() => {
		dispatch({ type: "UNAVAILABLE" });
	}, []);

	const derived = useMemo(
		() => ({
			drcState: snapshot.state,
			lastError: snapshot.lastError,
			updateStatus,
			markUnavailable,
		}),
		[snapshot, updateStatus, markUnavailable],
	);

	return derived;
};
