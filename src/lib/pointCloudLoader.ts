import { readLasHeader } from './lasHeader'
import type { LasHeaderInfo } from '../types/mission'

const DEFAULT_BYTES_PER_POINT = 20

export type LasLoadProgress = {
  totalPoints: number
  processedPoints: number
  acceptedPoints: number
  sampleEvery: number
}

export type LasLoadResult = {
  points: Float32Array
  colors: Float32Array | null
  header: LasHeaderInfo
  sampleEvery: number
  acceptedPoints: number
}

export type LasLoadOptions = {
  maxMegabytes: number
  bytesPerPoint?: number
  onProgress?: (progress: LasLoadProgress) => void
  signal?: AbortSignal
}

const getPositionsFromBatch = (batch: unknown): Float32Array | null => {
  if (!batch || typeof batch !== 'object') return null

  const typedBatch = batch as {
    attributes?: { POSITION?: { value?: Float32Array } }
    positions?: Float32Array
  }

  if (typedBatch.attributes?.POSITION?.value instanceof Float32Array) {
    return typedBatch.attributes.POSITION.value
  }

  if (typedBatch.positions instanceof Float32Array) {
    return typedBatch.positions
  }

  return null
}

const getColorsFromBatch = (batch: unknown): Float32Array | Uint8Array | null => {
  if (!batch || typeof batch !== 'object') return null

  const typedBatch = batch as {
    attributes?: { COLOR_0?: { value?: Float32Array | Uint8Array } }
    colors?: Float32Array | Uint8Array
  }

  if (typedBatch.attributes?.COLOR_0?.value instanceof Float32Array) {
    return typedBatch.attributes.COLOR_0.value
  }

  if (typedBatch.attributes?.COLOR_0?.value instanceof Uint8Array) {
    return typedBatch.attributes.COLOR_0.value
  }

  if (typedBatch.colors instanceof Float32Array) {
    return typedBatch.colors
  }

  if (typedBatch.colors instanceof Uint8Array) {
    return typedBatch.colors
  }

  return null
}

const COLOR_OFFSETS: Record<number, number | null> = {
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
}

const normalizeColor = (value: number, scale: number) =>
  Math.min(1, Math.max(0, value / scale))

const estimateMaxPoints = (budgetMB: number, bytesPerPoint: number) => {
  const bytes = Math.max(1, budgetMB) * 1024 * 1024
  return Math.max(1, Math.floor(bytes / bytesPerPoint))
}

const streamLasPositions = async (
  file: File,
  header: LasHeaderInfo,
  options: LasLoadOptions,
  maxPoints: number,
  sampleEvery: number
) => {
  const bytesPerPoint = header.recordLength > 0 ? header.recordLength : DEFAULT_BYTES_PER_POINT
  const totalPoints = Math.max(1, header.pointCount)
  const targetPoints = Math.min(maxPoints, totalPoints)
  const output = new Float32Array(targetPoints * 3)
  const colorOffset = COLOR_OFFSETS[header.pointFormat] ?? null
  const outputColors = colorOffset === null ? null : new Float32Array(targetPoints * 3)
  let colorScale: number | null = null

  const scale = header.scale
  const offset = header.offset
  const chunkBytes = 32 * 1024 * 1024
  const pointsPerChunk = Math.max(1, Math.floor(chunkBytes / bytesPerPoint))
  let accepted = 0
  let seen = 0

  for (
    let pointIndex = 0;
    pointIndex < totalPoints && accepted < targetPoints;
    pointIndex += pointsPerChunk
  ) {
    if (options.signal?.aborted) break

    const count = Math.min(pointsPerChunk, totalPoints - pointIndex)
    const byteOffset = header.offsetToPointData + pointIndex * bytesPerPoint
    const byteLength = count * bytesPerPoint
    const buffer = await file.slice(byteOffset, byteOffset + byteLength).arrayBuffer()
    const view = new DataView(buffer)
    if (outputColors && colorOffset !== null && colorScale === null) {
      let maxColor = 0
      for (let i = 0; i < count; i += 1) {
        const base = i * bytesPerPoint + colorOffset
        const r = view.getUint16(base, true)
        const g = view.getUint16(base + 2, true)
        const b = view.getUint16(base + 4, true)
        maxColor = Math.max(maxColor, r, g, b)
        if (maxColor > 255) break
      }
      colorScale = maxColor > 255 ? 65535 : 255
    }

    for (let i = 0; i < count; i += 1) {
      if (options.signal?.aborted) break

      const currentIndex = seen
      seen += 1
      if (currentIndex % sampleEvery !== 0) continue

      const base = i * bytesPerPoint
      const ix = view.getInt32(base, true)
      const iy = view.getInt32(base + 4, true)
      const iz = view.getInt32(base + 8, true)
      const outIndex = accepted * 3
      output[outIndex] = ix * scale[0] + offset[0]
      output[outIndex + 1] = iy * scale[1] + offset[1]
      output[outIndex + 2] = iz * scale[2] + offset[2]
      if (outputColors && colorOffset !== null) {
        const colorBase = base + colorOffset
        const r = view.getUint16(colorBase, true)
        const g = view.getUint16(colorBase + 2, true)
        const b = view.getUint16(colorBase + 4, true)
        const scale = colorScale ?? 65535
        outputColors[outIndex] = normalizeColor(r, scale)
        outputColors[outIndex + 1] = normalizeColor(g, scale)
        outputColors[outIndex + 2] = normalizeColor(b, scale)
      }
      accepted += 1

      if (accepted >= targetPoints) break
    }

    options.onProgress?.({
      totalPoints: header.pointCount,
      processedPoints: seen,
      acceptedPoints: accepted,
      sampleEvery,
    })
  }

  return {
    points: output.subarray(0, accepted * 3),
    colors: outputColors ? outputColors.subarray(0, accepted * 3) : null,
    acceptedPoints: accepted,
  }
}

export const loadLasPointCloud = async (
  file: File,
  options: LasLoadOptions
): Promise<LasLoadResult> => {
  const header = await readLasHeader(file)
  if (header.pointCount === 0) {
    return {
      points: new Float32Array(),
      colors: null,
      header,
      sampleEvery: 1,
      acceptedPoints: 0,
    }
  }
  const bytesPerPoint =
    header.recordLength > 0 ? header.recordLength : options.bytesPerPoint ?? DEFAULT_BYTES_PER_POINT
  const maxPoints = estimateMaxPoints(options.maxMegabytes, bytesPerPoint)
  const safeTotal = Math.max(1, header.pointCount)
  const sampleEvery = Math.max(1, Math.ceil(safeTotal / maxPoints))
  const targetPoints = Math.min(maxPoints, safeTotal)

  const needCustomParse =
    header.versionMajor > 1 || (header.versionMajor === 1 && header.versionMinor >= 4)

  if (needCustomParse) {
    const result = await streamLasPositions(file, header, options, maxPoints, sampleEvery)
    return {
      points: result.points,
      colors: result.colors,
      header,
      sampleEvery,
      acceptedPoints: result.acceptedPoints,
    }
  }

  const { loadInBatches } = await import('@loaders.gl/core')
  const { LASLoader } = await import('@loaders.gl/las')

  const output = new Float32Array(targetPoints * 3)
  let outputColors: Float32Array | null = null
  let colorScale: number | null = null
  let accepted = 0
  let seen = 0

  const batches = await loadInBatches(file, LASLoader, {
    las: { decompressed: true },
    worker: false,
  })

  for await (const batch of batches) {
    if (options.signal?.aborted) break

    const positions = getPositionsFromBatch(batch)
    if (!positions) continue
    const colors = getColorsFromBatch(batch)
    if (colors && !outputColors) {
      outputColors = new Float32Array(targetPoints * 3)
      if (colors instanceof Uint8Array) {
        colorScale = 255
      } else {
        let maxColor = 0
        const sampleCount = Math.min(colors.length, 3000)
        for (let i = 0; i < sampleCount; i += 1) {
          maxColor = Math.max(maxColor, colors[i])
          if (maxColor > 255) break
        }
        if (maxColor <= 1) {
          colorScale = 1
        } else if (maxColor <= 255) {
          colorScale = 255
        } else {
          colorScale = 65535
        }
      }
    }

    const batchCount = Math.floor(positions.length / 3)
    for (let i = 0; i < batchCount; i += 1) {
      if (options.signal?.aborted) break

      const currentIndex = seen
      seen += 1

      if (currentIndex % sampleEvery === 0) {
        const base = i * 3
        const outIndex = accepted * 3
        output[outIndex] = positions[base]
        output[outIndex + 1] = positions[base + 1]
        output[outIndex + 2] = positions[base + 2]
        if (outputColors && colors) {
          const scale = colorScale ?? (colors instanceof Uint8Array ? 255 : 1)
          if (colors instanceof Uint8Array) {
            outputColors[outIndex] = colors[base] / scale
            outputColors[outIndex + 1] = colors[base + 1] / scale
            outputColors[outIndex + 2] = colors[base + 2] / scale
          } else {
            outputColors[outIndex] = colors[base] / scale
            outputColors[outIndex + 1] = colors[base + 1] / scale
            outputColors[outIndex + 2] = colors[base + 2] / scale
          }
        }
        accepted += 1

        if (accepted >= targetPoints) break
      }
    }

    options.onProgress?.({
      totalPoints: header.pointCount,
      processedPoints: seen,
      acceptedPoints: accepted,
      sampleEvery,
    })

    if (accepted >= targetPoints) break
  }

  return {
    points: output.subarray(0, accepted * 3),
    colors: outputColors ? outputColors.subarray(0, accepted * 3) : null,
    header,
    sampleEvery,
    acceptedPoints: accepted,
  }
}
