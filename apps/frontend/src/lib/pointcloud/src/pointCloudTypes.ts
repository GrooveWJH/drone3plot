import type { LasHeaderInfo } from "../../../types/mission";

export const DEFAULT_BYTES_PER_POINT = 20;

export type LasLoadProgress = {
	totalPoints: number;
	processedPoints: number;
	acceptedPoints: number;
	sampleEvery: number;
};

export type LasLoadResult = {
	points: Float32Array;
	colors: Float32Array | null;
	header: LasHeaderInfo;
	sampleEvery: number;
	acceptedPoints: number;
};

export type PointCloudResult = {
	points: Float32Array;
	colors: Float32Array | null;
	totalPoints: number;
	sampleEvery: number;
	acceptedPoints: number;
};

export type LasLoadOptions = {
	maxMegabytes: number;
	bytesPerPoint?: number;
	onProgress?: (progress: LasLoadProgress) => void;
	signal?: AbortSignal;
};
