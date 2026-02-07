import fs from "node:fs/promises";
import path from "node:path";

const DEFAULT_BUDGET_MB = 100;
const DEFAULT_BYTES_PER_POINT = 20;
const HEADER_MIN_BYTES = 375;
const SAMPLE_COUNT = 5;

const bytesToMB = (bytes) => bytes / (1024 * 1024);

const formatNumber = (value) => new Intl.NumberFormat("en-US").format(value);

const getBudget = () => {
	const arg = process.argv.find((item) => item.startsWith("--budget="));
	if (!arg) return DEFAULT_BUDGET_MB;
	const value = Number(arg.split("=")[1]);
	return Number.isFinite(value) && value > 0 ? value : DEFAULT_BUDGET_MB;
};

const ansiColor = (text, r, g, b) => `\x1b[38;2;${r};${g};${b}m${text}\x1b[0m`;

const randomIndices = (total, count) => {
	const result = new Set();
	const safeTotal = Math.max(0, total);
	while (result.size < Math.min(count, safeTotal)) {
		result.add(Math.floor(Math.random() * safeTotal));
	}
	return [...result].sort((a, b) => a - b);
};

const readLasHeader = async (filePath) => {
	const handle = await fs.open(filePath, "r");
	const buffer = Buffer.alloc(HEADER_MIN_BYTES);
	await handle.read(buffer, 0, HEADER_MIN_BYTES, 0);
	await handle.close();

	const signature = buffer.toString("ascii", 0, 4);
	if (signature !== "LASF") {
		throw new Error("Invalid LAS header signature");
	}

	const versionMajor = buffer.readUInt8(24);
	const versionMinor = buffer.readUInt8(25);
	const headerSize = buffer.readUInt16LE(94);
	const offsetToPointData = buffer.readUInt32LE(96);
	const pointFormat = buffer.readUInt8(104);
	const recordLength = buffer.readUInt16LE(105);
	const legacyPointCount = buffer.readUInt32LE(107);
	const scaleX = buffer.readDoubleLE(131);
	const scaleY = buffer.readDoubleLE(139);
	const scaleZ = buffer.readDoubleLE(147);
	const offsetX = buffer.readDoubleLE(155);
	const offsetY = buffer.readDoubleLE(163);
	const offsetZ = buffer.readDoubleLE(171);

	let pointCount = legacyPointCount;
	if (headerSize >= HEADER_MIN_BYTES && buffer.length >= 255) {
		const extendedCount = buffer.readBigUInt64LE(247);
		if (extendedCount > 0n) {
			const maxSafe = BigInt(Number.MAX_SAFE_INTEGER);
			pointCount = Number(extendedCount > maxSafe ? maxSafe : extendedCount);
		}
	}

	return {
		version: `${versionMajor}.${versionMinor}`,
		headerSize,
		offsetToPointData,
		pointCount,
		pointFormat,
		recordLength,
		scale: [scaleX, scaleY, scaleZ],
		offset: [offsetX, offsetY, offsetZ],
	};
};

const readPcdHeader = async (filePath) => {
	const handle = await fs.open(filePath, "r");
	const buffer = Buffer.alloc(65536);
	await handle.read(buffer, 0, 65536, 0);
	await handle.close();

	const text = buffer.toString("ascii");
	const dataIndex = text.indexOf("\nDATA");
	if (dataIndex === -1) return null;
	const lineEnd = text.indexOf("\n", dataIndex + 1);
	if (lineEnd === -1) return null;

	const headerText = text.slice(0, lineEnd);
	const headerLines = headerText.split(/\r?\n/);
	const getValue = (key) => {
		const line = headerLines.find((entry) => entry.startsWith(`${key} `));
		return line ? line.slice(key.length + 1).trim() : null;
	};

	const pointsRaw = getValue("POINTS");
	const widthRaw = getValue("WIDTH");
	const heightRaw = getValue("HEIGHT");
	const fieldsRaw = getValue("FIELDS");
	const sizeRaw = getValue("SIZE");
	const countRaw = getValue("COUNT");
	const typeRaw = getValue("TYPE");
	const dataRaw = getValue("DATA");
	const points = pointsRaw ? Number(pointsRaw) : null;
	const width = widthRaw ? Number(widthRaw) : null;
	const height = heightRaw ? Number(heightRaw) : null;
	const fields = fieldsRaw ? fieldsRaw.split(/\s+/) : [];
	const sizes = sizeRaw ? sizeRaw.split(/\s+/).map(Number) : [];
	const counts = countRaw ? countRaw.split(/\s+/).map(Number) : [];
	const types = typeRaw ? typeRaw.split(/\s+/) : [];

	return {
		pointCount: points ?? (width && height ? width * height : null),
		width,
		height,
		data: dataRaw ?? "unknown",
		fields,
		sizes,
		counts,
		types,
		headerLength: lineEnd + 1,
	};
};

const walkFiles = async (dir) => {
	const entries = await fs.readdir(dir, { withFileTypes: true });
	const results = [];
	for (const entry of entries) {
		const fullPath = path.join(dir, entry.name);
		if (entry.isDirectory()) {
			results.push(...(await walkFiles(fullPath)));
			continue;
		}
		results.push(fullPath);
	}
	return results;
};

const COLOR_OFFSETS = {
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

const to8Bit = (value) => Math.round(value / 257);

const analyzeLas = async (filePath, budgetMB, bytesPerPoint) => {
	const stats = await fs.stat(filePath);
	const header = await readLasHeader(filePath);
	const effectiveBytes =
		header.recordLength > 0 ? header.recordLength : bytesPerPoint;
	const budgetBytes = budgetMB * 1024 * 1024;
	const maxPoints = Math.max(1, Math.floor(budgetBytes / effectiveBytes));
	const totalPoints = Math.max(1, header.pointCount);
	const sampleEvery = Math.max(1, Math.ceil(totalPoints / maxPoints));
	const loadedPoints = Math.min(totalPoints, maxPoints);
	const estimatedMemory = loadedPoints * effectiveBytes;
	const colorFormats = new Set([2, 3, 5, 7, 8, 10]);

	return {
		path: filePath,
		sizeMB: bytesToMB(stats.size),
		header,
		totalPoints: header.pointCount,
		sampleEvery,
		loadedPoints,
		estimatedMemoryMB: bytesToMB(estimatedMemory),
		bytesPerPoint: effectiveBytes,
		fallbackBytesPerPoint: bytesPerPoint,
		hasColor: colorFormats.has(header.pointFormat),
	};
};

const analyzePcd = async (filePath, budgetMB, bytesPerPoint) => {
	const stats = await fs.stat(filePath);
	const header = await readPcdHeader(filePath);
	const totalPoints = Math.max(1, header?.pointCount ?? 0);
	const sizes = header?.sizes ?? [];
	const counts = header?.counts ?? [];
	const hasFieldInfo =
		sizes.length > 0 && (counts.length === 0 || counts.length === sizes.length);
	const computedBytes = hasFieldInfo
		? sizes.reduce((sum, size, index) => sum + size * (counts[index] ?? 1), 0)
		: null;
	const effectiveBytes =
		computedBytes && computedBytes > 0 ? computedBytes : bytesPerPoint;
	const budgetBytes = budgetMB * 1024 * 1024;
	const maxPoints = Math.max(1, Math.floor(budgetBytes / effectiveBytes));
	const sampleEvery = Math.max(1, Math.ceil(totalPoints / maxPoints));
	const loadedPoints = Math.min(totalPoints, maxPoints);
	const estimatedMemory = loadedPoints * effectiveBytes;
	const fields = header?.fields ?? [];
	const hasColor = fields.some(
		(field) => field.toLowerCase() === "rgb" || field.toLowerCase() === "rgba",
	);
	const rgbIndex = fields.findIndex(
		(field) => field.toLowerCase() === "rgb" || field.toLowerCase() === "rgba",
	);
	const rgbBits = rgbIndex >= 0 ? (sizes[rgbIndex] ?? 0) * 8 : 0;

	return {
		path: filePath,
		sizeMB: bytesToMB(stats.size),
		pointCount: header?.pointCount ?? null,
		width: header?.width ?? null,
		height: header?.height ?? null,
		data: header?.data ?? "unknown",
		bytesPerPoint: effectiveBytes,
		fallbackBytesPerPoint: bytesPerPoint,
		sampleEvery,
		loadedPoints,
		estimatedMemoryMB: bytesToMB(estimatedMemory),
		hasColor,
		fields,
		rgbBits,
		header,
	};
};

const printLas = (result) => {
	console.log(`\nLAS: ${result.path}`);
	console.log(`  文件大小: ${result.sizeMB.toFixed(2)} MB`);
	console.log(`  LAS 版本: ${result.header.version}`);
	console.log(`  点格式: ${result.header.pointFormat}`);
	console.log(`  记录长度: ${result.header.recordLength} bytes`);
	console.log(`  点总数: ${formatNumber(result.totalPoints)}`);
	console.log(`  预算 bytes/point: ${result.bytesPerPoint}`);
	if (result.bytesPerPoint !== result.fallbackBytesPerPoint) {
		console.log(`  （按记录长度 ${result.bytesPerPoint} bytes/point 计算）`);
	}
	console.log(`  颜色字段: ${result.hasColor ? "有（RGB）" : "无"}`);
	console.log(`  采样步长: ${result.sampleEvery}`);
	console.log(`  预计加载点数: ${formatNumber(result.loadedPoints)}`);
	console.log(`  估算内存: ${result.estimatedMemoryMB.toFixed(2)} MB`);
};

const printPcd = (result) => {
	console.log(`\nPCD: ${result.path}`);
	console.log(`  文件大小: ${result.sizeMB.toFixed(2)} MB`);
	if (result.pointCount) {
		console.log(`  点数量: ${formatNumber(result.pointCount)}`);
	} else {
		console.log("  点数量: 未知（未解析 header）");
	}
	if (result.width && result.height) {
		console.log(`  组织结构: ${result.width} x ${result.height}`);
	}
	console.log(`  数据类型: ${result.data}`);
	console.log(`  预算 bytes/point: ${result.bytesPerPoint}`);
	if (result.bytesPerPoint !== result.fallbackBytesPerPoint) {
		console.log(`  （按字段 SIZE/COUNT 计算）`);
	}
	console.log(`  颜色字段: ${result.hasColor ? "有（RGB）" : "无"}`);
	if (result.rgbBits) {
		console.log(`  RGB 位数: ${result.rgbBits}-bit`);
	}
	console.log(`  采样步长: ${result.sampleEvery}`);
	console.log(`  预计加载点数: ${formatNumber(result.loadedPoints)}`);
	console.log(`  估算内存: ${result.estimatedMemoryMB.toFixed(2)} MB`);
	if (result.fields.length > 0) {
		console.log(`  字段: ${result.fields.join(" ")}`);
	}
};

const readBinaryValue = (view, offset, type, size) => {
	const isLittle = true;
	if (type === "F") {
		if (size === 4) return view.getFloat32(offset, isLittle);
		if (size === 8) return view.getFloat64(offset, isLittle);
	}
	if (type === "I") {
		if (size === 1) return view.getInt8(offset);
		if (size === 2) return view.getInt16(offset, isLittle);
		if (size === 4) return view.getInt32(offset, isLittle);
	}
	if (type === "U") {
		if (size === 1) return view.getUint8(offset);
		if (size === 2) return view.getUint16(offset, isLittle);
		if (size === 4) return view.getUint32(offset, isLittle);
	}
	return null;
};

const parsePcdSamples = async (filePath, header) => {
	if (!header) return [];
	const dataType = (header.data ?? "").toLowerCase();
	if (!dataType.startsWith("binary")) return [];

	const buffer = await fs.readFile(filePath);
	let dataOffset = header.headerLength;
	let dataBuffer;

	if (dataType === "binary_compressed") {
		const compressedSize = buffer.readUInt32LE(dataOffset);
		const uncompressedSize = buffer.readUInt32LE(dataOffset + 4);
		const compressed = buffer.subarray(
			dataOffset + 8,
			dataOffset + 8 + compressedSize,
		);
		dataBuffer = lzfDecompress(compressed, uncompressedSize);
		dataOffset = 0;
	} else {
		dataBuffer = buffer.subarray(dataOffset);
		dataOffset = 0;
	}

	const view = new DataView(
		dataBuffer.buffer,
		dataBuffer.byteOffset,
		dataBuffer.byteLength,
	);
	const fields = header.fields;
	const sizes = header.sizes;
	const counts = header.counts.length ? header.counts : fields.map(() => 1);
	const types = header.types;
	const offsets = [];
	let stride = 0;
	for (let i = 0; i < fields.length; i += 1) {
		offsets.push(stride);
		stride += (sizes[i] ?? 0) * (counts[i] ?? 1);
	}

	const idxX = fields.findIndex((field) => field.toLowerCase() === "x");
	const idxY = fields.findIndex((field) => field.toLowerCase() === "y");
	const idxZ = fields.findIndex((field) => field.toLowerCase() === "z");
	const idxRGB = fields.findIndex(
		(field) => field.toLowerCase() === "rgb" || field.toLowerCase() === "rgba",
	);
	const idxR = fields.findIndex((field) => field.toLowerCase() === "r");
	const idxG = fields.findIndex((field) => field.toLowerCase() === "g");
	const idxB = fields.findIndex((field) => field.toLowerCase() === "b");

	const indices = randomIndices(header.pointCount ?? 0, SAMPLE_COUNT);
	const samples = [];

	for (const index of indices) {
		const base = index * stride;
		const x =
			idxX >= 0
				? readBinaryValue(view, base + offsets[idxX], types[idxX], sizes[idxX])
				: null;
		const y =
			idxY >= 0
				? readBinaryValue(view, base + offsets[idxY], types[idxY], sizes[idxY])
				: null;
		const z =
			idxZ >= 0
				? readBinaryValue(view, base + offsets[idxZ], types[idxZ], sizes[idxZ])
				: null;

		let r = null;
		let g = null;
		let b = null;

		if (idxRGB >= 0) {
			const offset = base + offsets[idxRGB];
			const packed = view.getUint32(offset, true);
			r = (packed >> 16) & 255;
			g = (packed >> 8) & 255;
			b = packed & 255;
		} else if (idxR >= 0 && idxG >= 0 && idxB >= 0) {
			r = readBinaryValue(view, base + offsets[idxR], types[idxR], sizes[idxR]);
			g = readBinaryValue(view, base + offsets[idxG], types[idxG], sizes[idxG]);
			b = readBinaryValue(view, base + offsets[idxB], types[idxB], sizes[idxB]);
		}

		samples.push({ index, x, y, z, r, g, b });
	}

	return samples;
};

const parseLasSamples = async (filePath, header) => {
	const indices = randomIndices(header.pointCount, SAMPLE_COUNT);
	const handle = await fs.open(filePath, "r");
	const samples = [];
	const colorOffset = COLOR_OFFSETS[header.pointFormat] ?? null;

	try {
		for (const index of indices) {
			const buffer = Buffer.alloc(header.recordLength);
			const offset = header.offsetToPointData + index * header.recordLength;
			await handle.read(buffer, 0, header.recordLength, offset);
			const x = buffer.readInt32LE(0) * header.scale[0] + header.offset[0];
			const y = buffer.readInt32LE(4) * header.scale[1] + header.offset[1];
			const z = buffer.readInt32LE(8) * header.scale[2] + header.offset[2];
			let r = null;
			let g = null;
			let b = null;
			if (colorOffset !== null) {
				r = buffer.readUInt16LE(colorOffset);
				g = buffer.readUInt16LE(colorOffset + 2);
				b = buffer.readUInt16LE(colorOffset + 4);
			}
			samples.push({ index, x, y, z, r, g, b });
		}
	} finally {
		await handle.close();
	}

	return samples;
};

const lzfDecompress = (input, outputLength) => {
	const output = Buffer.alloc(outputLength);
	let inPos = 0;
	let outPos = 0;

	while (inPos < input.length) {
		const ctrl = input[inPos++];
		if (ctrl < 32) {
			const length = ctrl + 1;
			if (outPos + length > outputLength)
				throw new Error("LZF buffer overflow");
			input.copy(output, outPos, inPos, inPos + length);
			inPos += length;
			outPos += length;
		} else {
			let length = ctrl >> 5;
			let ref = outPos - ((ctrl & 0x1f) << 8) - 1;
			if (length === 7) length += input[inPos++];
			ref -= input[inPos++];
			length += 2;
			if (ref < 0) throw new Error("LZF invalid back-reference");
			for (let i = 0; i < length; i += 1) {
				output[outPos++] = output[ref++];
			}
		}
	}

	return output;
};

const printSamples = (label, samples) => {
	if (!samples.length) {
		console.log(`  ${label}: 无法抽样（格式不支持或未包含数据）`);
		return;
	}
	console.log(`  ${label}:`);
	samples.forEach((sample, idx) => {
		const coords = `x=${sample.x?.toFixed?.(3) ?? sample.x}, y=${sample.y?.toFixed?.(3) ?? sample.y}, z=${
			sample.z?.toFixed?.(3) ?? sample.z
		}`;
		if (sample.r !== null && sample.g !== null && sample.b !== null) {
			const r = sample.r > 255 ? to8Bit(sample.r) : Math.round(sample.r);
			const g = sample.g > 255 ? to8Bit(sample.g) : Math.round(sample.g);
			const b = sample.b > 255 ? to8Bit(sample.b) : Math.round(sample.b);
			const rgb = `rgb=${r},${g},${b}`;
			console.log(
				`    #${idx + 1} idx=${sample.index} ${ansiColor(coords, r, g, b)} ${ansiColor(rgb, r, g, b)}`,
			);
		} else {
			console.log(`    #${idx + 1} idx=${sample.index} ${coords}`);
		}
	});
};

const main = async () => {
	const dataDir = path.join(process.cwd(), "data");
	const budgetMB = getBudget();
	const bytesPerPoint = DEFAULT_BYTES_PER_POINT;

	const files = await walkFiles(dataDir);
	const lasFiles = files.filter((file) =>
		[".las", ".laz"].includes(path.extname(file).toLowerCase()),
	);
	const pcdFiles = files.filter(
		(file) => path.extname(file).toLowerCase() === ".pcd",
	);

	if (lasFiles.length === 0 && pcdFiles.length === 0) {
		console.log("data/ 目录下未发现 .las/.laz/.pcd 文件。");
		return;
	}

	console.log(`点云分析（预算 ${budgetMB}MB，${bytesPerPoint} bytes/point）。`);

	for (const filePath of lasFiles) {
		try {
			const result = await analyzeLas(filePath, budgetMB, bytesPerPoint);
			printLas(result);
			const samples = await parseLasSamples(filePath, result.header);
			printSamples("随机点样本", samples);
		} catch (error) {
			console.log(`\nLAS: ${filePath}`);
			console.log(
				`  读取 header 失败: ${error instanceof Error ? error.message : String(error)}`,
			);
		}
	}

	for (const filePath of pcdFiles) {
		const result = await analyzePcd(filePath, budgetMB, bytesPerPoint);
		printPcd(result);
		const samples = await parsePcdSamples(filePath, result.header);
		printSamples("随机点样本", samples);
	}
};

main().catch((error) => {
	console.error(error);
	process.exit(1);
});
