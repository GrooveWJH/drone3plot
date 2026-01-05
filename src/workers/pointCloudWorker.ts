import { loadPointCloud } from '../lib/pointCloudLoader'

type WorkerScope = typeof self & {
  postMessage: (message: unknown, transfer?: Transferable[]) => void
}

type WorkerMessage = {
  file: File
  options: {
    maxMegabytes: number
    chunkSize?: number
  }
  existingHash?: string | null
}

let lastProgressAt = 0

const postProgress = (progress: {
  totalPoints: number
  processedPoints: number
  acceptedPoints: number
  sampleEvery: number
}) => {
  const now = performance.now()
  if (now - lastProgressAt < 80) return
  lastProgressAt = now
  ;(self as WorkerScope).postMessage({ type: 'progress', payload: progress })
}

const bufferToHex = (buffer: ArrayBuffer) =>
  Array.from(new Uint8Array(buffer))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('')

const computeHash = async (file: File) => {
  const buffer = await file.arrayBuffer()
  const digest = await crypto.subtle.digest('SHA-256', buffer)
  return bufferToHex(digest)
}

(self as WorkerScope).onmessage = async (event: MessageEvent<WorkerMessage>) => {
  const { file, options, existingHash } = event.data
  lastProgressAt = 0
  try {
    const hash = await computeHash(file)
    ;(self as WorkerScope).postMessage({ type: 'hash', payload: { hash } })
    if (existingHash && existingHash === hash) {
      ;(self as WorkerScope).postMessage({ type: 'skip', payload: { hash } })
      return
    }
    const result = await loadPointCloud(file, {
      maxMegabytes: options.maxMegabytes,
      onProgress: postProgress,
    })
    const totalPoints = Math.floor(result.points.length / 3)
    const size = options.chunkSize && options.chunkSize > 0 ? options.chunkSize : totalPoints
    for (let i = 0; i < totalPoints; i += size) {
      const start = i * 3
      const end = Math.min(totalPoints, i + size) * 3
      const pointsChunk = result.points.slice(start, end)
      const colorsChunk = result.colors ? result.colors.slice(start, end) : null
      const transfer: Transferable[] = [pointsChunk.buffer]
      if (colorsChunk) transfer.push(colorsChunk.buffer)
      ;(self as WorkerScope).postMessage(
        {
          type: 'chunk',
          payload: {
            points: pointsChunk,
            colors: colorsChunk,
          },
        },
        transfer
      )
    }
    ;(self as WorkerScope).postMessage({
      type: 'done',
      payload: {
        totalPoints: result.totalPoints,
        acceptedPoints: result.acceptedPoints,
        sampleEvery: result.sampleEvery,
        hash,
      },
    })
  } catch (err) {
    ;(self as WorkerScope).postMessage({
      type: 'error',
      error: err instanceof Error ? err.message : 'Failed to load LAS file.',
    })
  }
}
