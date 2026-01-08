import fs from 'node:fs/promises'
import path from 'node:path'

const HEADER_MIN_BYTES = 375
const DEFAULT_SAMPLE_TARGET = 200000

const bytesToMB = (bytes) => bytes / (1024 * 1024)
const formatNumber = (value) => new Intl.NumberFormat('en-US').format(value)

const COLOR_OFFSETS = {
  2: 20,
  3: 28,
  5: 34,
  7: 30,
  8: 30,
  10: 30,
}

const readLasHeader = async (filePath) => {
  const handle = await fs.open(filePath, 'r')
  const buffer = Buffer.alloc(HEADER_MIN_BYTES)
  await handle.read(buffer, 0, HEADER_MIN_BYTES, 0)
  await handle.close()

  const signature = buffer.toString('ascii', 0, 4)
  if (signature !== 'LASF') {
    throw new Error('Invalid LAS header signature')
  }

  const versionMajor = buffer.readUInt8(24)
  const versionMinor = buffer.readUInt8(25)
  const headerSize = buffer.readUInt16LE(94)
  const offsetToPointData = buffer.readUInt32LE(96)
  const pointFormat = buffer.readUInt8(104)
  const recordLength = buffer.readUInt16LE(105)
  const legacyPointCount = buffer.readUInt32LE(107)

  let pointCount = legacyPointCount
  if (headerSize >= HEADER_MIN_BYTES && buffer.length >= 255) {
    const extendedCount = buffer.readBigUInt64LE(247)
    if (extendedCount > 0n) {
      const maxSafe = BigInt(Number.MAX_SAFE_INTEGER)
      pointCount = Number(extendedCount > maxSafe ? maxSafe : extendedCount)
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
  }
}

const walkFiles = async (dir) => {
  const entries = await fs.readdir(dir, { withFileTypes: true })
  const results = []
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      results.push(...(await walkFiles(fullPath)))
      continue
    }
    results.push(fullPath)
  }
  return results
}

const analyzeLasColors = async (filePath, sampleTarget = DEFAULT_SAMPLE_TARGET) => {
  const header = await readLasHeader(filePath)
  const colorOffset = COLOR_OFFSETS[header.pointFormat] ?? null

  if (colorOffset === null) {
    return {
      header,
      hasColor: false,
      reason: '点格式不包含 RGB 字段',
    }
  }

  if (header.recordLength < colorOffset + 6) {
    return {
      header,
      hasColor: false,
      reason: '记录长度不足以包含 RGB',
    }
  }

  const totalPoints = Math.max(1, header.pointCount)
  const target = Math.min(sampleTarget, totalPoints)
  const sampleEvery = Math.max(1, Math.floor(totalPoints / target))
  const chunkBytes = 8 * 1024 * 1024
  const pointsPerChunk = Math.max(1, Math.floor(chunkBytes / header.recordLength))

  const stats = {
    min: [Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY],
    max: [0, 0, 0],
    sum: [0, 0, 0],
    zeros: 0,
    samples: 0,
    firstColors: [],
  }

  const handle = await fs.open(filePath, 'r')
  try {
    for (let pointIndex = 0; pointIndex < totalPoints; pointIndex += pointsPerChunk) {
      const count = Math.min(pointsPerChunk, totalPoints - pointIndex)
      const byteOffset = header.offsetToPointData + pointIndex * header.recordLength
      const byteLength = count * header.recordLength
      const buffer = Buffer.alloc(byteLength)
      await handle.read(buffer, 0, byteLength, byteOffset)

      for (let i = 0; i < count; i += 1) {
        const globalIndex = pointIndex + i
        if (globalIndex % sampleEvery !== 0) continue

        const base = i * header.recordLength + colorOffset
        const r = buffer.readUInt16LE(base)
        const g = buffer.readUInt16LE(base + 2)
        const b = buffer.readUInt16LE(base + 4)

        stats.min[0] = Math.min(stats.min[0], r)
        stats.min[1] = Math.min(stats.min[1], g)
        stats.min[2] = Math.min(stats.min[2], b)
        stats.max[0] = Math.max(stats.max[0], r)
        stats.max[1] = Math.max(stats.max[1], g)
        stats.max[2] = Math.max(stats.max[2], b)
        stats.sum[0] += r
        stats.sum[1] += g
        stats.sum[2] += b
        if (r === 0 && g === 0 && b === 0) stats.zeros += 1
        stats.samples += 1
        if (stats.firstColors.length < 10) {
          stats.firstColors.push([r, g, b])
        }

        if (stats.samples >= target) break
      }

      if (stats.samples >= target) break
    }
  } finally {
    await handle.close()
  }

  const maxValue = Math.max(stats.max[0], stats.max[1], stats.max[2])
  const suggestedScale = maxValue <= 255 ? 255 : 65535
  const zeroRatio = stats.samples > 0 ? stats.zeros / stats.samples : 0

  return {
    header,
    hasColor: true,
    sampleEvery,
    samples: stats.samples,
    min: stats.min,
    max: stats.max,
    mean: stats.samples > 0 ? stats.sum.map((v) => v / stats.samples) : [0, 0, 0],
    zeroRatio,
    maxValue,
    suggestedScale,
    firstColors: stats.firstColors,
  }
}

const printReport = async (filePath) => {
  const fileStats = await fs.stat(filePath)
  console.log(`\nLAS: ${filePath}`)
  console.log(`  文件大小: ${bytesToMB(fileStats.size).toFixed(2)} MB`)

  let result
  try {
    result = await analyzeLasColors(filePath)
  } catch (error) {
    console.log(`  读取失败: ${error instanceof Error ? error.message : String(error)}`)
    return
  }

  console.log(`  LAS 版本: ${result.header.version}`)
  console.log(`  点格式: ${result.header.pointFormat}`)
  console.log(`  记录长度: ${result.header.recordLength} bytes`)
  console.log(`  点总数: ${formatNumber(result.header.pointCount)}`)

  if (!result.hasColor) {
    console.log(`  颜色字段: 无 (${result.reason})`)
    return
  }

  console.log('  颜色字段: 有（RGB）')
  console.log(`  采样步长: ${result.sampleEvery}`)
  console.log(`  采样点数: ${formatNumber(result.samples)}`)
  console.log(`  RGB 最小值: ${result.min.join(', ')}`)
  console.log(`  RGB 最大值: ${result.max.join(', ')}`)
  console.log(`  RGB 均值: ${result.mean.map((v) => v.toFixed(1)).join(', ')}`)
  console.log(`  全零比例: ${(result.zeroRatio * 100).toFixed(2)}%`)
  console.log(`  建议归一化: / ${result.suggestedScale}`)
  if (result.firstColors.length > 0) {
    console.log(`  前 10 个颜色: ${result.firstColors.map((item) => item.join(',')).join(' | ')}`)
  }
}

const main = async () => {
  const dataDir = path.join(process.cwd(), 'data')
  const files = await walkFiles(dataDir)
  const lasFiles = files.filter((file) => ['.las', '.laz'].includes(path.extname(file).toLowerCase()))

  if (lasFiles.length === 0) {
    console.log('data/ 目录下未发现 .las/.laz 文件。')
    return
  }

  console.log('LAS 颜色分析（采样 RGB 统计 + 建议归一化）')

  for (const filePath of lasFiles) {
    await printReport(filePath)
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
