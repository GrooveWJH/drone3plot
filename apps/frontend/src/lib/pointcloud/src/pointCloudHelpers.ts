import { DEFAULT_BYTES_PER_POINT } from "./pointCloudTypes";

export const getPositionsFromBatch = (batch: unknown): Float32Array | null => {
	if (!batch || typeof batch !== "object") return null;

	const typedBatch = batch as {
		attributes?: { POSITION?: { value?: Float32Array } };
		positions?: Float32Array;
	};

	if (typedBatch.attributes?.POSITION?.value instanceof Float32Array) {
		return typedBatch.attributes.POSITION.value;
	}

	if (typedBatch.positions instanceof Float32Array) {
		return typedBatch.positions;
	}

	return null;
};

export const getColorsFromBatch = (
	batch: unknown,
): Float32Array | Uint8Array | null => {
	if (!batch || typeof batch !== "object") return null;

	const typedBatch = batch as {
		attributes?: { COLOR_0?: { value?: Float32Array | Uint8Array } };
		colors?: Float32Array | Uint8Array;
	};

	if (typedBatch.attributes?.COLOR_0?.value instanceof Float32Array) {
		return typedBatch.attributes.COLOR_0.value;
	}

	if (typedBatch.attributes?.COLOR_0?.value instanceof Uint8Array) {
		return typedBatch.attributes.COLOR_0.value;
	}

	if (typedBatch.colors instanceof Float32Array) {
		return typedBatch.colors;
	}

	if (typedBatch.colors instanceof Uint8Array) {
		return typedBatch.colors;
	}

	return null;
};

export const COLOR_OFFSETS: Record<number, number | null> = {
	0: null,
	1: null,
	2: 20,
	3: 28,
	4: null,
	5: 30,
	6: null,
	7: 30,
	8: 30,
	9: 30,
	10: 30,
};

export const normalizeColor = (value: number, scale: number) =>
	Math.min(1, Math.max(0, value / scale));

export const estimateMaxPoints = (budgetMB: number, bytesPerPoint: number) => {
	const bytes = Math.max(1, budgetMB) * 1024 * 1024;
	return Math.max(1, Math.floor(bytes / bytesPerPoint));
};

export const yieldToMainThread = () =>
	new Promise<void>((resolve) => {
		if (typeof requestAnimationFrame === "function") {
			requestAnimationFrame(() => resolve());
			return;
		}
		setTimeout(() => resolve(), 0);
	});

export const resolveBytesPerPoint = (bytesPerPoint?: number) =>
	bytesPerPoint ?? DEFAULT_BYTES_PER_POINT;
