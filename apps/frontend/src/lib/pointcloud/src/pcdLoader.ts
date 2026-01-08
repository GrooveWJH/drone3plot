import type { LasLoadOptions, PointCloudResult } from './pointCloudTypes'
import { DEFAULT_BYTES_PER_POINT } from './pointCloudTypes'
import { estimateMaxPoints, yieldToMainThread } from './pointCloudHelpers'

type PcdHeader = {
  pointCount: number
  data: string
  fields: string[]
  sizes: number[]
  counts: number[]
  types: string[]
  headerLength: number
}

const readPcdHeader = async (file: File): Promise<PcdHeader> => {
  const slice = file.slice(0, 65536)
  const buffer = await slice.arrayBuffer()
  const text = new TextDecoder('ascii').decode(buffer)
  const dataLineIndex = text.indexOf('\nDATA')
  if (dataLineIndex === -1) {
    throw new Error('Invalid PCD header (DATA not found)')
  }
  const endLineIndex = text.indexOf('\n', dataLineIndex + 1)
  const headerText = text.slice(0, endLineIndex)
  const lines = headerText.split(/\r?\n/)
  const getValue = (key: string) => {
    const line = lines.find((entry) => entry.startsWith(`${key} `))
    return line ? line.slice(key.length + 1).trim() : null
  }

  const pointsRaw = getValue('POINTS')
  const widthRaw = getValue('WIDTH')
  const heightRaw = getValue('HEIGHT')
  const fieldsRaw = getValue('FIELDS')
  const sizeRaw = getValue('SIZE')
  const countRaw = getValue('COUNT')
  const typeRaw = getValue('TYPE')
  const dataRaw = getValue('DATA')

  const points = pointsRaw ? Number(pointsRaw) : null
  const width = widthRaw ? Number(widthRaw) : null
  const height = heightRaw ? Number(heightRaw) : null
  const pointCount = points ?? (width && height ? width * height : 0)

  return {
    pointCount,
    data: dataRaw ?? 'unknown',
    fields: fieldsRaw ? fieldsRaw.split(/\s+/) : [],
    sizes: sizeRaw ? sizeRaw.split(/\s+/).map(Number) : [],
    counts: countRaw ? countRaw.split(/\s+/).map(Number) : [],
    types: typeRaw ? typeRaw.split(/\s+/) : [],
    headerLength: endLineIndex + 1,
  }
}

const readBinaryValue = (view: DataView, offset: number, type: string, size: number) => {
  const little = true
  if (type === 'F') {
    if (size === 4) return view.getFloat32(offset, little)
    if (size === 8) return view.getFloat64(offset, little)
  }
  if (type === 'I') {
    if (size === 1) return view.getInt8(offset)
    if (size === 2) return view.getInt16(offset, little)
    if (size === 4) return view.getInt32(offset, little)
  }
  if (type === 'U') {
    if (size === 1) return view.getUint8(offset)
    if (size === 2) return view.getUint16(offset, little)
    if (size === 4) return view.getUint32(offset, little)
  }
  return null
}

const lzfDecompress = (input: Uint8Array, outputLength: number) => {
  const output = new Uint8Array(outputLength)
  let inPos = 0
  let outPos = 0

  while (inPos < input.length) {
    const ctrl = input[inPos++]
    if (ctrl < 32) {
      let length = ctrl + 1
      output.set(input.subarray(inPos, inPos + length), outPos)
      inPos += length
      outPos += length
    } else {
      let length = ctrl >> 5
      let ref = outPos - ((ctrl & 0x1f) << 8) - 1
      if (length === 7) length += input[inPos++]
      ref -= input[inPos++]
      length += 2
      for (let i = 0; i < length; i += 1) {
        output[outPos++] = output[ref++]
      }
    }
  }

  return output
}

export const loadPcdPointCloud = async (
  file: File,
  options: LasLoadOptions
): Promise<PointCloudResult> => {
  const header = await readPcdHeader(file)
  const totalPoints = Math.max(1, header.pointCount)
  const counts = header.counts.length ? header.counts : header.fields.map(() => 1)
  const bytesPerPoint = header.sizes.reduce(
    (sum, size, index) => sum + size * (counts[index] ?? 1),
    0
  )
  const effectiveBytes =
    bytesPerPoint > 0 ? bytesPerPoint : options.bytesPerPoint ?? DEFAULT_BYTES_PER_POINT
  const maxPoints = estimateMaxPoints(options.maxMegabytes, effectiveBytes)
  const sampleEvery = Math.max(1, Math.ceil(totalPoints / maxPoints))
  const targetPoints = Math.min(maxPoints, totalPoints)

  const indexX = header.fields.findIndex((field) => field.toLowerCase() === 'x')
  const indexY = header.fields.findIndex((field) => field.toLowerCase() === 'y')
  const indexZ = header.fields.findIndex((field) => field.toLowerCase() === 'z')
  const indexRGB = header.fields.findIndex(
    (field) => field.toLowerCase() === 'rgb' || field.toLowerCase() === 'rgba'
  )
  const indexR = header.fields.findIndex((field) => field.toLowerCase() === 'r')
  const indexG = header.fields.findIndex((field) => field.toLowerCase() === 'g')
  const indexB = header.fields.findIndex((field) => field.toLowerCase() === 'b')

  if (indexX < 0 || indexY < 0 || indexZ < 0) {
    throw new Error('PCD missing x/y/z fields')
  }

  const offsets: number[] = []
  let stride = 0
  header.fields.forEach((_, index) => {
    offsets[index] = stride
    stride += (header.sizes[index] ?? 0) * (counts[index] ?? 1)
  })

  const buffer = await file.arrayBuffer()
  const dataStart = header.headerLength
  let data = new Uint8Array(buffer, dataStart)
  let dataIsFieldMajor = false
  if (header.data === 'binary_compressed') {
    const view = new DataView(buffer, dataStart)
    const compressedSize = view.getUint32(0, true)
    const uncompressedSize = view.getUint32(4, true)
    const compressed = new Uint8Array(buffer, dataStart + 8, compressedSize)
    data = lzfDecompress(compressed, uncompressedSize)
    dataIsFieldMajor = true
  } else if (header.data !== 'binary') {
    throw new Error(`Unsupported PCD DATA format: ${header.data}`)
  }

  const view = new DataView(data.buffer, data.byteOffset, data.byteLength)
  const output = new Float32Array(targetPoints * 3)
  const outputColors = new Float32Array(targetPoints * 3)
  let colorScale = 255
  let accepted = 0
  let frameStart = performance.now()
  let lastProgressAt = frameStart

  const readFieldMajor = (fieldIndex: number, pointIndex: number) => {
    let fieldOffset = 0
    for (let i = 0; i < fieldIndex; i += 1) {
      fieldOffset += (header.sizes[i] ?? 0) * (counts[i] ?? 1) * totalPoints
    }
    const fieldStride = (header.sizes[fieldIndex] ?? 0) * (counts[fieldIndex] ?? 1)
    return fieldOffset + pointIndex * fieldStride
  }

  const unpackRgbFloat = (value: number) => {
    const buffer = new ArrayBuffer(4)
    new DataView(buffer).setFloat32(0, value, true)
    const packed = new DataView(buffer).getUint32(0, true)
    return {
      r: (packed >> 16) & 255,
      g: (packed >> 8) & 255,
      b: packed & 255,
    }
  }

  const pickLayout = () => {
    if (!dataIsFieldMajor) return false
    const maxSamples = 5000
    const step = Math.max(1, Math.floor(totalPoints / maxSamples))

    const evaluate = (useFieldMajor: boolean) => {
      let count = 0
      const min = [Infinity, Infinity, Infinity]
      const max = [-Infinity, -Infinity, -Infinity]
      for (let i = 0; i < totalPoints && count < maxSamples; i += step) {
        const base = useFieldMajor ? 0 : i * stride
        const xOffset = useFieldMajor ? readFieldMajor(indexX, i) : base + offsets[indexX]
        const yOffset = useFieldMajor ? readFieldMajor(indexY, i) : base + offsets[indexY]
        const zOffset = useFieldMajor ? readFieldMajor(indexZ, i) : base + offsets[indexZ]
        const x = readBinaryValue(view, xOffset, header.types[indexX], header.sizes[indexX])
        const y = readBinaryValue(view, yOffset, header.types[indexY], header.sizes[indexY])
        const z = readBinaryValue(view, zOffset, header.types[indexZ], header.sizes[indexZ])
        if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) continue
        if (x < min[0]) min[0] = x
        if (y < min[1]) min[1] = y
        if (z < min[2]) min[2] = z
        if (x > max[0]) max[0] = x
        if (y > max[1]) max[1] = y
        if (z > max[2]) max[2] = z
        count += 1
      }
      const rangeSum =
        Number.isFinite(min[0]) && Number.isFinite(max[0])
          ? (max[0] - min[0]) + (max[1] - min[1]) + (max[2] - min[2])
          : 0
      return { count, rangeSum }
    }

    const fieldStats = evaluate(true)
    const interStats = evaluate(false)
    if (fieldStats.count === 0) return false
    if (interStats.count === 0) return true
    if (interStats.rangeSum > fieldStats.rangeSum * 1.1) return false
    return true
  }

  dataIsFieldMajor = pickLayout()

  for (let i = 0; i < totalPoints && accepted < targetPoints; i += sampleEvery) {
    if (options.signal?.aborted) {
      return {
        points: new Float32Array(),
        colors: null,
        totalPoints,
        sampleEvery,
        acceptedPoints: 0,
      }
    }
    const base = dataIsFieldMajor ? 0 : i * stride
    const xOffset = dataIsFieldMajor ? readFieldMajor(indexX, i) : base + offsets[indexX]
    const yOffset = dataIsFieldMajor ? readFieldMajor(indexY, i) : base + offsets[indexY]
    const zOffset = dataIsFieldMajor ? readFieldMajor(indexZ, i) : base + offsets[indexZ]
    const x = readBinaryValue(view, xOffset, header.types[indexX], header.sizes[indexX])
    const y = readBinaryValue(view, yOffset, header.types[indexY], header.sizes[indexY])
    const z = readBinaryValue(view, zOffset, header.types[indexZ], header.sizes[indexZ])
    const outIndex = accepted * 3
    output[outIndex] = Number(x ?? 0)
    output[outIndex + 1] = Number(y ?? 0)
    output[outIndex + 2] = Number(z ?? 0)

    let r: number | null = null
    let g: number | null = null
    let b: number | null = null
    if (indexRGB >= 0) {
      const rgbOffset = dataIsFieldMajor ? readFieldMajor(indexRGB, i) : base + offsets[indexRGB]
      if (header.types[indexRGB] === 'F' && header.sizes[indexRGB] === 4) {
        const packedFloat = view.getFloat32(rgbOffset, true)
        const unpacked = unpackRgbFloat(packedFloat)
        r = unpacked.r
        g = unpacked.g
        b = unpacked.b
      } else {
        const packed = view.getUint32(rgbOffset, true)
        r = (packed >> 16) & 255
        g = (packed >> 8) & 255
        b = packed & 255
      }
    } else if (indexR >= 0 && indexG >= 0 && indexB >= 0) {
      const rOffset = dataIsFieldMajor ? readFieldMajor(indexR, i) : base + offsets[indexR]
      const gOffset = dataIsFieldMajor ? readFieldMajor(indexG, i) : base + offsets[indexG]
      const bOffset = dataIsFieldMajor ? readFieldMajor(indexB, i) : base + offsets[indexB]
      r = Number(readBinaryValue(view, rOffset, header.types[indexR], header.sizes[indexR]))
      g = Number(readBinaryValue(view, gOffset, header.types[indexG], header.sizes[indexG]))
      b = Number(readBinaryValue(view, bOffset, header.types[indexB], header.sizes[indexB]))
      const max = Math.max(r, g, b)
      colorScale = max <= 1 ? 1 : max <= 255 ? 255 : 65535
    }

    if (r !== null && g !== null && b !== null) {
      outputColors[outIndex] = r / colorScale
      outputColors[outIndex + 1] = g / colorScale
      outputColors[outIndex + 2] = b / colorScale
    }

    accepted += 1
    const now = performance.now()
    if (now - lastProgressAt > 80) {
      options.onProgress?.({
        totalPoints,
        processedPoints: i,
        acceptedPoints: accepted,
        sampleEvery,
      })
      lastProgressAt = now
    }

    if (now - frameStart > 12) {
      await yieldToMainThread()
      frameStart = performance.now()
    }
  }

  return {
    points: output.subarray(0, accepted * 3),
    colors: accepted > 0 ? outputColors.subarray(0, accepted * 3) : null,
    totalPoints,
    sampleEvery,
    acceptedPoints: accepted,
  }
}
