import type { LasHeaderInfo } from "../../../types/mission";
import { readLasHeader } from "../../lasHeader";
import {
	COLOR_OFFSETS,
	estimateMaxPoints,
	getColorsFromBatch,
	getPositionsFromBatch,
	normalizeColor,
	yieldToMainThread,
} from "./pointCloudHelpers";
import type { LasLoadOptions, LasLoadResult } from "./pointCloudTypes";
import { DEFAULT_BYTES_PER_POINT } from "./pointCloudTypes";

const streamLasPositions = async (
	file: File,
	header: LasHeaderInfo,
	options: LasLoadOptions,
	maxPoints: number,
	sampleEvery: number,
) => {
	const bytesPerPoint =
		header.recordLength > 0 ? header.recordLength : DEFAULT_BYTES_PER_POINT;
	const totalPoints = Math.max(1, header.pointCount);
	const targetPoints = Math.min(maxPoints, totalPoints);
	const output = new Float32Array(targetPoints * 3);
	const colorOffset = COLOR_OFFSETS[header.pointFormat] ?? null;
	const outputColors =
		colorOffset === null ? null : new Float32Array(targetPoints * 3);
	let colorScale: number | null = null;

	const scale = header.scale;
	const offset = header.offset;
	const chunkBytes = 32 * 1024 * 1024;
	const pointsPerChunk = Math.max(1, Math.floor(chunkBytes / bytesPerPoint));
	let accepted = 0;
	let seen = 0;
	let frameStart = performance.now();

	for (
		let pointIndex = 0;
		pointIndex < totalPoints && accepted < targetPoints;
		pointIndex += pointsPerChunk
	) {
		if (options.signal?.aborted) break;

		const count = Math.min(pointsPerChunk, totalPoints - pointIndex);
		const byteOffset = header.offsetToPointData + pointIndex * bytesPerPoint;
		const byteLength = count * bytesPerPoint;
		const buffer = await file
			.slice(byteOffset, byteOffset + byteLength)
			.arrayBuffer();
		const view = new DataView(buffer);
		if (outputColors && colorOffset !== null && colorScale === null) {
			let maxColor = 0;
			for (let i = 0; i < count; i += 1) {
				const base = i * bytesPerPoint + colorOffset;
				const r = view.getUint16(base, true);
				const g = view.getUint16(base + 2, true);
				const b = view.getUint16(base + 4, true);
				maxColor = Math.max(maxColor, r, g, b);
				if (maxColor > 255) break;
			}
			colorScale = maxColor > 255 ? 65535 : 255;
		}

		for (let i = 0; i < count; i += 1) {
			if (options.signal?.aborted) break;

			const currentIndex = seen;
			seen += 1;
			if (currentIndex % sampleEvery !== 0) continue;

			const base = i * bytesPerPoint;
			const ix = view.getInt32(base, true);
			const iy = view.getInt32(base + 4, true);
			const iz = view.getInt32(base + 8, true);
			const outIndex = accepted * 3;
			output[outIndex] = ix * scale[0] + offset[0];
			output[outIndex + 1] = iy * scale[1] + offset[1];
			output[outIndex + 2] = iz * scale[2] + offset[2];
			if (outputColors && colorOffset !== null) {
				const colorBase = base + colorOffset;
				const r = view.getUint16(colorBase, true);
				const g = view.getUint16(colorBase + 2, true);
				const b = view.getUint16(colorBase + 4, true);
				const colorScaleValue = colorScale ?? 65535;
				outputColors[outIndex] = normalizeColor(r, colorScaleValue);
				outputColors[outIndex + 1] = normalizeColor(g, colorScaleValue);
				outputColors[outIndex + 2] = normalizeColor(b, colorScaleValue);
			}
			accepted += 1;

			if (accepted >= targetPoints) break;
			if (i % 4096 === 0 && performance.now() - frameStart > 12) {
				await yieldToMainThread();
				frameStart = performance.now();
			}
		}

		if (options.signal?.aborted) {
			return {
				points: new Float32Array(),
				colors: null,
				acceptedPoints: 0,
			};
		}

		options.onProgress?.({
			totalPoints: header.pointCount,
			processedPoints: seen,
			acceptedPoints: accepted,
			sampleEvery,
		});
	}

	return {
		points: output.subarray(0, accepted * 3),
		colors: outputColors ? outputColors.subarray(0, accepted * 3) : null,
		acceptedPoints: accepted,
	};
};

export const loadLasPointCloud = async (
	file: File,
	options: LasLoadOptions,
): Promise<LasLoadResult> => {
	const header = await readLasHeader(file);
	if (header.pointCount === 0) {
		return {
			points: new Float32Array(),
			colors: null,
			header,
			sampleEvery: 1,
			acceptedPoints: 0,
		};
	}
	const bytesPerPoint =
		header.recordLength > 0
			? header.recordLength
			: (options.bytesPerPoint ?? DEFAULT_BYTES_PER_POINT);
	const maxPoints = estimateMaxPoints(options.maxMegabytes, bytesPerPoint);
	const safeTotal = Math.max(1, header.pointCount);
	const sampleEvery = Math.max(1, Math.ceil(safeTotal / maxPoints));
	const targetPoints = Math.min(maxPoints, safeTotal);

	const needCustomParse =
		header.versionMajor > 1 ||
		(header.versionMajor === 1 && header.versionMinor >= 4);

	if (needCustomParse) {
		const result = await streamLasPositions(
			file,
			header,
			options,
			maxPoints,
			sampleEvery,
		);
		return {
			points: result.points,
			colors: result.colors,
			header,
			sampleEvery,
			acceptedPoints: result.acceptedPoints,
		};
	}

	const { loadInBatches } = await import("@loaders.gl/core");
	const { LASLoader } = await import("@loaders.gl/las");

	const output = new Float32Array(targetPoints * 3);
	let outputColors: Float32Array | null = null;
	let colorScale: number | null = null;
	let accepted = 0;
	let seen = 0;

	const batches = await loadInBatches(file, LASLoader, {
		las: { decompressed: true },
		worker: true,
	});

	for await (const batch of batches) {
		if (options.signal?.aborted) break;

		const positions = getPositionsFromBatch(batch);
		if (!positions) continue;
		const colors = getColorsFromBatch(batch);
		if (colors && !outputColors) {
			outputColors = new Float32Array(targetPoints * 3);
			if (colors instanceof Uint8Array) {
				colorScale = 255;
			} else {
				let maxColor = 0;
				const sampleCount = Math.min(colors.length, 3000);
				for (let i = 0; i < sampleCount; i += 1) {
					maxColor = Math.max(maxColor, colors[i]);
					if (maxColor > 255) break;
				}
				if (maxColor <= 1) {
					colorScale = 1;
				} else if (maxColor <= 255) {
					colorScale = 255;
				} else {
					colorScale = 65535;
				}
			}
		}

		const batchCount = Math.floor(positions.length / 3);
		for (let i = 0; i < batchCount; i += 1) {
			if (options.signal?.aborted) break;

			const currentIndex = seen;
			seen += 1;

			if (currentIndex % sampleEvery === 0) {
				const base = i * 3;
				const outIndex = accepted * 3;
				output[outIndex] = positions[base];
				output[outIndex + 1] = positions[base + 1];
				output[outIndex + 2] = positions[base + 2];
				if (outputColors && colors) {
					const scale = colorScale ?? (colors instanceof Uint8Array ? 255 : 1);
					outputColors[outIndex] = colors[base] / scale;
					outputColors[outIndex + 1] = colors[base + 1] / scale;
					outputColors[outIndex + 2] = colors[base + 2] / scale;
				}
				accepted += 1;

				if (accepted >= targetPoints) break;
			}
		}

		options.onProgress?.({
			totalPoints: header.pointCount,
			processedPoints: seen,
			acceptedPoints: accepted,
			sampleEvery,
		});

		if (accepted >= targetPoints) break;
	}

	return {
		points: output.subarray(0, accepted * 3),
		colors: outputColors ? outputColors.subarray(0, accepted * 3) : null,
		header,
		sampleEvery,
		acceptedPoints: accepted,
	};
};
