import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { loadPointCloud } from './pointCloudLoader'
import type { PointCloudStats } from '../../../types/mission'
import { UI_CONFIG } from '../../../config/ui'

type UsePointCloudLoaderParams = {
  onPrepareFile: (fileName: string) => void
  onResetCloudTransform: () => void
  isInteracting: boolean
}

let lastLogAt = 0

const logTiming = (fileName: string, phase: string, duration?: number) => {
  const now = performance.now()
  const timestamp = new Date().toISOString()
  const delta = lastLogAt ? now - lastLogAt : 0
  lastLogAt = now
  const durationText = typeof duration === 'number' ? ` ${duration.toFixed(7)}ms` : ''
  console.log(
    `[pointcloud] ${timestamp} ${fileName} ${phase}:${durationText} (+${delta.toFixed(7)}ms)`
  )
}

export const usePointCloudLoader = ({
  onPrepareFile,
  onResetCloudTransform,
  isInteracting,
}: UsePointCloudLoaderParams) => {
  const [pointCloud, setPointCloud] = useState<Float32Array | null>(null)
  const [pointColors, setPointColors] = useState<Float32Array | null>(null)
  const [pointCloudChunks, setPointCloudChunks] = useState<
    Array<{ points: Float32Array; colors: Float32Array | null }>
  >([])
  const [pointCloudChunkVersion, setPointCloudChunkVersion] = useState(0)
  const [stats, setStats] = useState<PointCloudStats | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fileName, setFileName] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const workerRef = useRef<Worker | null>(null)
  const lastFingerprintRef = useRef<string | null>(null)
  const lastHashRef = useRef<string | null>(null)
  const pendingHashRef = useRef<string | null>(null)
  const chunkBufferRef = useRef<Array<{ points: Float32Array; colors: Float32Array | null }>>([])
  const flushRef = useRef<number | null>(null)
  const isPausedRef = useRef(false)
  const hasRenderedChunksRef = useRef(false)
  const pausedFlushRef = useRef<number | null>(null)
  const budgetMB = UI_CONFIG.pointCloud.budgetMB
  const chunkSize = UI_CONFIG.pointCloud.chunkSize

  const flushChunks = useCallback(() => {
    if (flushRef.current !== null || isPausedRef.current) return
    flushRef.current = requestAnimationFrame(() => {
      flushRef.current = null
      if (isPausedRef.current || chunkBufferRef.current.length === 0) return
      const nextChunks = chunkBufferRef.current
      chunkBufferRef.current = []
      hasRenderedChunksRef.current = true
      setPointCloudChunks((prev) => [...prev, ...nextChunks])
      if (chunkBufferRef.current.length > 0) {
        flushChunks()
      }
    })
  }, [])

  useEffect(() => {
    isPausedRef.current = isInteracting
    if (!isInteracting && chunkBufferRef.current.length > 0) {
      flushChunks()
    }
    if (isInteracting && flushRef.current) {
      cancelAnimationFrame(flushRef.current)
      flushRef.current = null
    }
    if (!isInteracting && pausedFlushRef.current) {
      window.clearTimeout(pausedFlushRef.current)
      pausedFlushRef.current = null
    }
  }, [isInteracting, flushChunks])

  const computeHash = useCallback(async (file: File) => {
    const buffer = await file.arrayBuffer()
    const digest = await crypto.subtle.digest('SHA-256', buffer)
    return Array.from(new Uint8Array(digest))
      .map((byte) => byte.toString(16).padStart(2, '0'))
      .join('')
  }, [])

  const handleFileSelect = useCallback(
    async (file: File) => {
      workerRef.current?.terminate()
      workerRef.current = null
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      lastLogAt = 0
      const totalStart = performance.now()
      logTiming(file.name, 'start')
      logTiming(file.name, `budgetMB=${budgetMB.toFixed(2)}`)
      setFileName(file.name)
      onPrepareFile(file.name)
      let hasCleared = false
      const clearExisting = () => {
        if (hasCleared) return
        hasCleared = true
        setPointCloud(null)
        setPointColors(null)
        setPointCloudChunks([])
        setPointCloudChunkVersion((prev) => prev + 1)
        chunkBufferRef.current = []
        hasRenderedChunksRef.current = false
        if (flushRef.current) {
          cancelAnimationFrame(flushRef.current)
          flushRef.current = null
        }
        setStats(null)
      }

      const fingerprint = `${file.name}:${file.size}:${file.lastModified}`
      if (fingerprint === lastFingerprintRef.current && pointCloud) {
        logTiming(file.name, 'skip (same file)')
        return
      }
      lastFingerprintRef.current = fingerprint
      setIsLoading(true)
      setError(null)
      let handledByWorker = false
      pendingHashRef.current = null
      const enqueueChunk = (chunk: { points: Float32Array; colors: Float32Array | null }) => {
        chunkBufferRef.current.push(chunk)
        if (!hasRenderedChunksRef.current) {
          const nextChunks = chunkBufferRef.current
          chunkBufferRef.current = []
          hasRenderedChunksRef.current = true
          setPointCloudChunks((prev) => [...prev, ...nextChunks])
          return
        }
        if (!isPausedRef.current) {
          flushChunks()
          return
        }
        if (pausedFlushRef.current) return
        pausedFlushRef.current = window.setTimeout(() => {
          pausedFlushRef.current = null
          if (chunkBufferRef.current.length === 0) return
          const nextChunks = chunkBufferRef.current
          chunkBufferRef.current = []
          setPointCloudChunks((prev) => [...prev, ...nextChunks])
        }, 200)
      }

      try {
        if (typeof Worker !== 'undefined') {
          const worker = new Worker(new URL('./pointCloudWorker.ts', import.meta.url), {
            type: 'module',
          })
          workerRef.current = worker
          const decodeStart = performance.now()
          handledByWorker = true

          const cleanup = () => {
            worker.terminate()
            if (workerRef.current === worker) {
              workerRef.current = null
            }
          }

          worker.onmessage = (event: MessageEvent) => {
            const { type, payload, error: workerError } = event.data as {
              type: 'progress' | 'chunk' | 'done' | 'error' | 'hash' | 'skip'
              payload?: {
                totalPoints: number
                processedPoints: number
                acceptedPoints: number
                sampleEvery: number
                points?: Float32Array
                colors?: Float32Array | null
                hash?: string
              }
              error?: string
            }

            if (type === 'hash' && payload?.hash) {
              pendingHashRef.current = payload.hash
              if (payload.hash !== lastHashRef.current) {
                clearExisting()
              }
              return
            }

            if (type === 'skip' && payload?.hash) {
              logTiming(file.name, 'skip (same hash)')
              setIsLoading(false)
              cleanup()
              return
            }

            if (type === 'progress' && payload) {
              clearExisting()
              setStats({
                totalPoints: payload.totalPoints,
                loadedPoints: payload.acceptedPoints,
                sampleEvery: payload.sampleEvery,
                budgetMB,
              })
              return
            }

            if (type === 'chunk' && payload?.points) {
              clearExisting()
              enqueueChunk({
                points: payload.points,
                colors: payload.colors ?? null,
              })
              return
            }

            if (type === 'done' && payload) {
              clearExisting()
              logTiming(file.name, 'decode', performance.now() - decodeStart)
              const setStateStart = performance.now()
              setStats({
                totalPoints: payload.totalPoints,
                loadedPoints: payload.acceptedPoints,
                sampleEvery: payload.sampleEvery,
                budgetMB,
              })
              if (payload.hash) {
                lastHashRef.current = payload.hash
              } else if (pendingHashRef.current) {
                lastHashRef.current = pendingHashRef.current
              }
              pendingHashRef.current = null
              logTiming(file.name, 'setState', performance.now() - setStateStart)
              setIsLoading(false)
              logTiming(file.name, 'total', performance.now() - totalStart)
              cleanup()
            }

            if (type === 'error') {
              setError(workerError ?? 'Failed to load LAS file.')
              setIsLoading(false)
              pendingHashRef.current = null
              logTiming(file.name, 'total', performance.now() - totalStart)
              cleanup()
            }
          }

          worker.onerror = () => {
            setError('Failed to load LAS file.')
            setIsLoading(false)
            pendingHashRef.current = null
            logTiming(file.name, 'total', performance.now() - totalStart)
            cleanup()
          }

          worker.postMessage({
            file,
            options: { maxMegabytes: budgetMB, chunkSize },
            existingHash: lastHashRef.current,
          })
          return
        }

        const hash = await computeHash(file)
        if (hash === lastHashRef.current && (pointCloud || pointCloudChunks.length > 0)) {
          logTiming(file.name, 'skip (same hash)')
          setIsLoading(false)
          return
        }
        pendingHashRef.current = hash
        clearExisting()
        const decodeStart = performance.now()
        const result = await loadPointCloud(file, {
          maxMegabytes: budgetMB,
          onProgress: (progress) => {
            setStats({
              totalPoints: progress.totalPoints,
              loadedPoints: progress.acceptedPoints,
              sampleEvery: progress.sampleEvery,
              budgetMB,
            })
          },
          signal: controller.signal,
        })
        logTiming(file.name, 'decode', performance.now() - decodeStart)

        const setStateStart = performance.now()
        setPointCloud(result.points)
        setPointColors(result.colors)
        setPointCloudChunks([{ points: result.points, colors: result.colors }])
        setStats({
          totalPoints: result.totalPoints,
          loadedPoints: result.acceptedPoints,
          sampleEvery: result.sampleEvery,
          budgetMB,
        })
        lastHashRef.current = pendingHashRef.current
        pendingHashRef.current = null
        logTiming(file.name, 'setState', performance.now() - setStateStart)
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : 'Failed to load LAS file.')
        }
      } finally {
        if (!controller.signal.aborted && !handledByWorker) {
          setIsLoading(false)
        }
        if (!handledByWorker) {
          logTiming(file.name, 'total', performance.now() - totalStart)
        }
      }
    },
    [
      budgetMB,
      onPrepareFile,
      pointCloud,
      pointCloudChunks.length,
      chunkSize,
      computeHash,
      onResetCloudTransform,
      flushChunks,
    ]
  )

  const clearPointCloud = useCallback(() => {
    workerRef.current?.terminate()
    workerRef.current = null
    abortRef.current?.abort()
    abortRef.current = null
    lastFingerprintRef.current = null
    lastHashRef.current = null
    pendingHashRef.current = null
    chunkBufferRef.current = []
    if (flushRef.current) {
      cancelAnimationFrame(flushRef.current)
      flushRef.current = null
    }
    setPointCloud(null)
    setPointColors(null)
    setPointCloudChunks([])
    setPointCloudChunkVersion((prev) => prev + 1)
    setStats(null)
    setError(null)
    setIsLoading(false)
    setFileName(null)
    onResetCloudTransform()
  }, [onResetCloudTransform])

  const pointsColor = useMemo(() => {
    const hasChunkColors = pointCloudChunks.some((chunk) => chunk.colors && chunk.colors.length > 0)
    if (pointColors || hasChunkColors) return '#ffffff'
    if (pointCloud || pointCloudChunks.length > 0) return '#5a666e'
    return '#7f8b92'
  }, [pointCloud, pointColors, pointCloudChunks])

  return {
    pointCloud,
    pointColors,
    pointCloudChunks,
    pointCloudChunkVersion,
    hasPointCloud: pointCloudChunks.length > 0 || Boolean(pointCloud),
    fileName,
    stats,
    isLoading,
    error,
    pointsColor,
    pointRadius: UI_CONFIG.pointCloud.radius,
    pointSizeAttenuation: !UI_CONFIG.pointCloud.fixedPixelSize,
    handleFileSelect,
    clearPointCloud,
  }
}
