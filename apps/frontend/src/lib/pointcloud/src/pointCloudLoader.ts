import { loadLasPointCloud } from "./lasLoader";
import { loadPcdPointCloud } from "./pcdLoader";
import type { LasLoadOptions, PointCloudResult } from "./pointCloudTypes";

export { loadLasPointCloud } from "./lasLoader";
export type {
	LasLoadOptions,
	LasLoadProgress,
	LasLoadResult,
	PointCloudResult,
} from "./pointCloudTypes";

export const loadPointCloud = async (
	file: File,
	options: LasLoadOptions,
): Promise<PointCloudResult> => {
	const name = file.name.toLowerCase();
	if (name.endsWith(".pcd")) {
		return loadPcdPointCloud(file, options);
	}
	const lasResult = await loadLasPointCloud(file, options);
	return {
		points: lasResult.points,
		colors: lasResult.colors,
		totalPoints: lasResult.header.pointCount,
		sampleEvery: lasResult.sampleEvery,
		acceptedPoints: lasResult.acceptedPoints,
	};
};
