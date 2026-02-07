import type { LasHeaderInfo } from "../types/mission";

const HEADER_MIN_BYTES = 375;

const readAscii = (view: DataView, start: number, length: number) => {
	const bytes = new Uint8Array(view.buffer, start, length);
	return new TextDecoder("ascii").decode(bytes).replace(/\0/g, "").trim();
};

export const readLasHeader = async (file: File): Promise<LasHeaderInfo> => {
	const slice = file.slice(0, HEADER_MIN_BYTES);
	const buffer = await slice.arrayBuffer();
	const view = new DataView(buffer);

	const signature = readAscii(view, 0, 4);
	if (signature !== "LASF") {
		throw new Error("Invalid LAS header signature");
	}

	const versionMajor = view.getUint8(24);
	const versionMinor = view.getUint8(25);
	const headerSize = view.getUint16(94, true);
	const offsetToPointData = view.getUint32(96, true);
	const pointFormat = view.getUint8(104);
	const recordLength = view.getUint16(105, true);
	const legacyPointCount = view.getUint32(107, true);
	const scaleX = view.getFloat64(131, true);
	const scaleY = view.getFloat64(139, true);
	const scaleZ = view.getFloat64(147, true);
	const offsetX = view.getFloat64(155, true);
	const offsetY = view.getFloat64(163, true);
	const offsetZ = view.getFloat64(171, true);

	let pointCount = legacyPointCount;
	if (headerSize >= HEADER_MIN_BYTES) {
		const extendedCount = view.getBigUint64(247, true);
		if (extendedCount > 0n) {
			const maxSafe = BigInt(Number.MAX_SAFE_INTEGER);
			pointCount = Number(extendedCount > maxSafe ? maxSafe : extendedCount);
		}
	}

	return {
		version: `${versionMajor}.${versionMinor}`,
		versionMajor,
		versionMinor,
		headerSize,
		offsetToPointData,
		pointCount,
		pointFormat,
		recordLength,
		scale: [scaleX, scaleY, scaleZ],
		offset: [offsetX, offsetY, offsetZ],
	};
};
