import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useRef } from "react";

type GpuUploadTimerProps = {
	enabled: boolean;
};

type TimerQueryExt = {
	TIME_ELAPSED_EXT: number;
	GPU_DISJOINT_EXT: number;
};

let lastGpuLogAt = 0;

const logGpu = (label: string, durationMs: number) => {
	const now = performance.now();
	const delta = lastGpuLogAt ? now - lastGpuLogAt : 0;
	lastGpuLogAt = now;
	const timestamp = new Date().toISOString();
	console.log(
		`[gpu] ${timestamp} ${label}: ${durationMs.toFixed(7)}ms (+${delta.toFixed(7)}ms)`,
	);
};

const GpuUploadTimer = ({ enabled }: GpuUploadTimerProps) => {
	const { gl } = useThree();
	const extRef = useRef<TimerQueryExt | null>(null);
	const queryRef = useRef<WebGLQuery | null>(null);
	const stateRef = useRef<"idle" | "armed" | "started" | "ended" | "done">(
		"idle",
	);

	useEffect(() => {
		if (!enabled) return undefined;
		const ctx = gl.getContext();
		if (
			!ctx ||
			typeof (ctx as WebGL2RenderingContext).getExtension !== "function"
		) {
			console.log("[gpu] WebGL context unavailable");
			return undefined;
		}
		const ext = (ctx as WebGL2RenderingContext).getExtension(
			"EXT_disjoint_timer_query_webgl2",
		) as TimerQueryExt | null;
		extRef.current = ext;
		if (!ext) {
			console.log("[gpu] EXT_disjoint_timer_query_webgl2 unavailable");
			return undefined;
		}
		stateRef.current = "armed";
		return () => {
			extRef.current = null;
		};
	}, [enabled, gl]);

	useEffect(() => {
		if (!enabled) {
			stateRef.current = "idle";
			return undefined;
		}
		if (!extRef.current) return undefined;
		stateRef.current = "armed";
		return undefined;
	}, [enabled]);

	useFrame(() => {
		if (
			!enabled ||
			!extRef.current ||
			stateRef.current !== "ended" ||
			!queryRef.current
		)
			return;
		const ext = extRef.current;
		const ctx = gl.getContext() as WebGL2RenderingContext;
		const available = ctx.getQueryParameter(
			queryRef.current,
			ctx.QUERY_RESULT_AVAILABLE,
		);
		const disjoint = ctx.getParameter(ext.GPU_DISJOINT_EXT);
		if (available && !disjoint) {
			const timeNs = ctx.getQueryParameter(
				queryRef.current,
				ctx.QUERY_RESULT,
			) as number;
			logGpu("first-frame-upload", timeNs / 1e6);
			ctx.deleteQuery(queryRef.current);
			queryRef.current = null;
			stateRef.current = "done";
		}
	});

	useFrame(() => {
		if (!enabled || !extRef.current) return;
		if (stateRef.current !== "armed") return;
		const ctx = gl.getContext() as WebGL2RenderingContext;
		const query = ctx.createQuery();
		if (!query) return;
		queryRef.current = query;
		ctx.beginQuery(extRef.current.TIME_ELAPSED_EXT, query);
		stateRef.current = "started";
	}, 1);

	useFrame(() => {
		if (!enabled || !extRef.current) return;
		if (stateRef.current !== "started") return;
		const ctx = gl.getContext() as WebGL2RenderingContext;
		ctx.endQuery(extRef.current.TIME_ELAPSED_EXT);
		stateRef.current = "ended";
	}, -1);

	return null;
};

export default GpuUploadTimer;
