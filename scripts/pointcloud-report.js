import fs from 'node:fs/promises'
import path from 'node:path'

const DEFAULT_BUDGET_MB = 100
const DEFAULT_BYTES_PER_POINT = 20
const HEADER_MIN_BYTES = 375

const bytesToMB = (bytes) => bytes / (1024 * 1024)

const formatNumber = (value) => new Intl.NumberFormat('en-US').format(value)

const getBudget = () => {
  const arg = process.argv.find((item) => item.startsWith('--budget='))
  if (!arg) return DEFAULT_BUDGET_MB
  const value = Number(arg.split('=')[1])
  return Number.isFinite(value) && value > 0 ? value : DEFAULT_BUDGET_MB
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
    headerSize,
    offsetToPointData,
    pointCount,
    pointFormat,
    recordLength,
  }
}

const readPlyHeader = async (filePath) => {
  const handle = await fs.open(filePath, 'r')
  const buffer = Buffer.alloc(4096)
  await handle.read(buffer, 0, 4096, 0)
  await handle.close()

  const text = buffer.toString('ascii')
  const match = text.match(/element\s+vertex\s+(\d+)/)
  if (!match) return null
  return { pointCount: Number(match[1]) }
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

const analyzeLas = async (filePath, budgetMB, bytesPerPoint) => {
  const stats = await fs.stat(filePath)
  const header = await readLasHeader(filePath)
  const effectiveBytes = header.recordLength > 0 ? header.recordLength : bytesPerPoint
  const budgetBytes = budgetMB * 1024 * 1024
  const maxPoints = Math.max(1, Math.floor(budgetBytes / effectiveBytes))
  const totalPoints = Math.max(1, header.pointCount)
  const sampleEvery = Math.max(1, Math.ceil(totalPoints / maxPoints))
  const loadedPoints = Math.min(totalPoints, maxPoints)
  const estimatedMemory = loadedPoints * effectiveBytes
  const colorFormats = new Set([2, 3, 5, 7, 8, 10])

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
  }
}

const analyzePly = async (filePath) => {
  const stats = await fs.stat(filePath)
  const header = await readPlyHeader(filePath)
  return {
    path: filePath,
    sizeMB: bytesToMB(stats.size),
    pointCount: header?.pointCount ?? null,
  }
}

const printLas = (result) => {
  console.log(`\nLAS: ${result.path}`)
  console.log(`  文件大小: ${result.sizeMB.toFixed(2)} MB`)
  console.log(`  LAS 版本: ${result.header.version}`)
  console.log(`  点格式: ${result.header.pointFormat}`)
  console.log(`  记录长度: ${result.header.recordLength} bytes`)
  console.log(`  点总数: ${formatNumber(result.totalPoints)}`)
  console.log(`  预算 bytes/point: ${result.bytesPerPoint}`)
  if (result.bytesPerPoint !== result.fallbackBytesPerPoint) {
    console.log(`  （按记录长度 ${result.bytesPerPoint} bytes/point 计算）`)
  }
  console.log(`  颜色字段: ${result.hasColor ? '有（RGB）' : '无'}`)
  console.log(`  采样步长: ${result.sampleEvery}`)
  console.log(`  预计加载点数: ${formatNumber(result.loadedPoints)}`)
  console.log(`  估算内存: ${result.estimatedMemoryMB.toFixed(2)} MB`)
}

const printPly = (result) => {
  console.log(`\nPLY: ${result.path}`)
  console.log(`  文件大小: ${result.sizeMB.toFixed(2)} MB`)
  if (result.pointCount) {
    console.log(`  点数量: ${formatNumber(result.pointCount)}`)
  } else {
    console.log('  点数量: 未知（未解析 header）')
  }
}

const main = async () => {
  const dataDir = path.join(process.cwd(), 'data')
  const budgetMB = getBudget()
  const bytesPerPoint = DEFAULT_BYTES_PER_POINT

  const files = await walkFiles(dataDir)
  const lasFiles = files.filter((file) => ['.las', '.laz'].includes(path.extname(file).toLowerCase()))
  const plyFiles = files.filter((file) => path.extname(file).toLowerCase() === '.ply')

  if (lasFiles.length === 0 && plyFiles.length === 0) {
    console.log('data/ 目录下未发现 .las/.laz/.ply 文件。')
    return
  }

  console.log(`点云分析（预算 ${budgetMB}MB，${bytesPerPoint} bytes/point）。`)

  for (const filePath of lasFiles) {
    try {
      const result = await analyzeLas(filePath, budgetMB, bytesPerPoint)
      printLas(result)
    } catch (error) {
      console.log(`\nLAS: ${filePath}`)
      console.log(`  读取 header 失败: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  for (const filePath of plyFiles) {
    const result = await analyzePly(filePath)
    printPly(result)
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
