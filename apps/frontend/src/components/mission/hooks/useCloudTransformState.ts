import { useCallback, useRef, useState } from "react";
import type { Group } from "three";
import type { TrajectoryFile } from "../../../types/mission";
import { clampRotation, degToRad } from "../utils";

type Axis = "x" | "y" | "z";

export const useCloudTransformState = () => {
	const [cloudRotation, setCloudRotation] = useState<[number, number, number]>([
		0, 0, 0,
	]);
	const [cloudOffset, setCloudOffset] = useState<[number, number, number]>([
		0, 0, 0,
	]);
	const [cloudFileName, setCloudFileName] = useState<string | null>(null);
	const [cloudTransformEnabled, setCloudTransformEnabled] = useState(false);
	const [cloudTransformMode, setCloudTransformMode] = useState<
		"translate" | "rotate"
	>("translate");
	const [pendingCloudTransform, setPendingCloudTransform] = useState<
		TrajectoryFile["cloudTransform"] | null
	>(null);
	const cloudGroupRef = useRef<Group | null>(null);

	const saveCloudTransform = useCallback(
		(
			fileName: string,
			rotation: [number, number, number],
			offset: [number, number, number],
		) => {
			localStorage.setItem(
				`cloudTransform:${fileName}`,
				JSON.stringify({ rotation, offset }),
			);
		},
		[],
	);

	const applyCloudTransform = useCallback(
		(transform: NonNullable<TrajectoryFile["cloudTransform"]>) => {
			setCloudRotation([
				clampRotation(transform.rotation[0]),
				clampRotation(transform.rotation[1]),
				clampRotation(transform.rotation[2]),
			]);
			setCloudOffset([
				transform.offset[0],
				transform.offset[1],
				transform.offset[2],
			]);
			setPendingCloudTransform(null);
			saveCloudTransform(
				transform.fileName,
				transform.rotation,
				transform.offset,
			);
		},
		[saveCloudTransform],
	);

	const registerTrajectoryCloudTransform = useCallback(
		(transform: TrajectoryFile["cloudTransform"] | null) => {
			if (!transform) {
				setPendingCloudTransform(null);
				return;
			}
			if (cloudFileName && transform.fileName === cloudFileName) {
				applyCloudTransform(transform);
			} else {
				setPendingCloudTransform(transform);
			}
		},
		[applyCloudTransform, cloudFileName],
	);

	const prepareCloudForFile = useCallback(
		(fileName: string) => {
			setCloudFileName(fileName);
			let nextRotation: [number, number, number] = [0, 0, 0];
			let nextOffset: [number, number, number] = [0, 0, 0];
			const savedTransform = localStorage.getItem(`cloudTransform:${fileName}`);
			if (savedTransform) {
				try {
					const parsed = JSON.parse(savedTransform) as {
						rotation?: [number, number, number];
						offset?: [number, number, number];
					};
					if (parsed.rotation && parsed.rotation.length === 3) {
						nextRotation = [
							clampRotation(parsed.rotation[0]),
							clampRotation(parsed.rotation[1]),
							clampRotation(parsed.rotation[2]),
						];
					}
					if (parsed.offset && parsed.offset.length === 3) {
						nextOffset = [parsed.offset[0], parsed.offset[1], parsed.offset[2]];
					}
				} catch {
					// ignore invalid cache
				}
			}

			if (
				pendingCloudTransform &&
				pendingCloudTransform.fileName === fileName
			) {
				nextRotation = [
					clampRotation(pendingCloudTransform.rotation[0]),
					clampRotation(pendingCloudTransform.rotation[1]),
					clampRotation(pendingCloudTransform.rotation[2]),
				];
				nextOffset = [
					pendingCloudTransform.offset[0],
					pendingCloudTransform.offset[1],
					pendingCloudTransform.offset[2],
				];
				setPendingCloudTransform(null);
			}

			setCloudRotation(nextRotation);
			setCloudOffset(nextOffset);
			saveCloudTransform(fileName, nextRotation, nextOffset);
		},
		[pendingCloudTransform, saveCloudTransform],
	);

	const onSetCloudRotation = useCallback(
		(axis: Axis, value: number) => {
			setCloudRotation((prev) => {
				const next = [...prev] as [number, number, number];
				const index = axis === "x" ? 0 : axis === "y" ? 1 : 2;
				next[index] = clampRotation(value);
				if (cloudFileName) {
					saveCloudTransform(cloudFileName, next, cloudOffset);
				}
				return next;
			});
		},
		[cloudFileName, cloudOffset, saveCloudTransform],
	);

	const onTranslateCloud = useCallback(
		(axis: Axis, value: number) => {
			setCloudOffset((prev) => {
				const next = [...prev] as [number, number, number];
				const index = axis === "x" ? 0 : axis === "y" ? 1 : 2;
				next[index] = value;
				if (cloudFileName) {
					saveCloudTransform(cloudFileName, cloudRotation, next);
				}
				return next;
			});
		},
		[cloudFileName, cloudRotation, saveCloudTransform],
	);

	const onCloudObjectChange = useCallback(() => {
		const group = cloudGroupRef.current;
		if (!group) return;
		const nextRotation: [number, number, number] = [
			clampRotation((group.rotation.x * 180) / Math.PI),
			clampRotation((group.rotation.y * 180) / Math.PI),
			clampRotation((group.rotation.z * 180) / Math.PI),
		];
		group.rotation.set(
			degToRad(nextRotation[0]),
			degToRad(nextRotation[1]),
			degToRad(nextRotation[2]),
		);
		setCloudRotation(nextRotation);
		const nextOffset: [number, number, number] = [
			group.position.x,
			group.position.y,
			group.position.z,
		];
		setCloudOffset(nextOffset);
		if (cloudFileName) {
			saveCloudTransform(cloudFileName, nextRotation, nextOffset);
		}
	}, [cloudFileName, saveCloudTransform]);

	const resetCloudTransform = useCallback(() => {
		setCloudFileName(null);
		setCloudRotation([0, 0, 0]);
		setCloudOffset([0, 0, 0]);
		setCloudTransformEnabled(false);
		setPendingCloudTransform(null);
	}, []);

	return {
		cloudRotation,
		cloudOffset,
		cloudFileName,
		cloudTransformEnabled,
		cloudTransformMode,
		cloudGroupRef,
		setCloudTransformEnabled,
		setCloudTransformMode,
		onSetCloudRotation,
		onTranslateCloud,
		onCloudObjectChange,
		prepareCloudForFile,
		resetCloudTransform,
		registerTrajectoryCloudTransform,
	};
};
