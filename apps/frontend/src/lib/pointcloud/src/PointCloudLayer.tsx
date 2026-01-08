import { useEffect, useMemo, useState } from 'react'
import * as THREE from 'three'
import { UI_CONFIG } from '../../../config/ui'

let lastGeometryLogAt = 0

export type PointCloudLayerProps = {
  points: Float32Array | null
  colors?: Float32Array | null
  chunks?: Array<{ points: Float32Array; colors: Float32Array | null }>
  chunkVersion?: number
  color?: string
  radius?: number
  rotation?: [number, number, number]
  position?: [number, number, number]
  sizeAttenuation?: boolean
  chunkSize?: number
  chunkBatch?: number
}

const PointCloudLayer = ({
  points,
  colors = null,
  chunks: chunksProp,
  chunkVersion = 0,
  color = '#8fa3a8',
  radius = 0.12,
  rotation = [0, 0, 0],
  position = [0, 0, 0],
  sizeAttenuation = true,
  chunkSize = 0,
  chunkBatch = 6,
}: PointCloudLayerProps) => {
  const chunks = useMemo(() => {
    if (chunksProp && chunksProp.length > 0) return chunksProp
    if (!points || points.length === 0) return []
    const totalPoints = Math.floor(points.length / 3)
    const size = chunkSize > 0 ? chunkSize : totalPoints
    const result: Array<{ points: Float32Array; colors: Float32Array | null }> = []
    for (let i = 0; i < totalPoints; i += size) {
      const start = i * 3
      const end = Math.min(totalPoints, i + size) * 3
      result.push({
        points: points.subarray(start, end),
        colors: colors ? colors.subarray(start, end) : null,
      })
    }
    return result
  }, [chunksProp, points, colors, chunkSize])

  const [visibleChunks, setVisibleChunks] = useState(0)
  const [geometries, setGeometries] = useState<THREE.BufferGeometry[]>([])

  useEffect(() => {
    setVisibleChunks(0)
  }, [chunkVersion])

  useEffect(() => {
    if (chunks.length === 0) {
      setVisibleChunks(0)
      return
    }
    let raf = 0
    const step = () => {
      setVisibleChunks((prev) => {
        const next = Math.min(chunks.length, prev + chunkBatch)
        if (next < chunks.length) {
          raf = requestAnimationFrame(step)
        }
        return next
      })
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [chunks.length, chunkBatch, chunkVersion])

  useEffect(() => {
    setGeometries((prev) => {
      prev.forEach((geom) => geom.dispose())
      return []
    })
  }, [chunkVersion])

  useEffect(() => {
    if (chunks.length === 0 || visibleChunks === 0) return
    const radius = UI_CONFIG.pointCloud.boundsRadius ?? 1000
    setGeometries((prev) => {
      if (prev.length >= visibleChunks) return prev
      const next = [...prev]
      const timingLabel = `[pointcloud]`
      const start = performance.now()
      for (let i = prev.length; i < visibleChunks; i += 1) {
        const chunk = chunks[i]
        if (!chunk) continue
        const geom = new THREE.BufferGeometry()
        geom.setAttribute('position', new THREE.BufferAttribute(chunk.points, 3))
        if (chunk.colors && chunk.colors.length === chunk.points.length) {
          geom.setAttribute('color', new THREE.BufferAttribute(chunk.colors, 3))
        }
        geom.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 0, 0), radius)
        next.push(geom)
      }
      const now = performance.now()
      const duration = now - start
      const delta = lastGeometryLogAt ? now - lastGeometryLogAt : 0
      lastGeometryLogAt = now
      const timestamp = new Date().toISOString()
      console.log(
        `${timingLabel} ${timestamp} geometry: ${duration.toFixed(7)}ms (+${delta.toFixed(7)}ms)`
      )
      return next
    })
  }, [chunks, visibleChunks])

  useEffect(
    () => () => {
      geometries.forEach((geom) => geom.dispose())
    },
    [geometries]
  )

  const hasVertexColors = useMemo(() => {
    if (chunksProp && chunksProp.length > 0) {
      return chunksProp.some((chunk) => chunk.colors && chunk.colors.length > 0)
    }
    return Boolean(colors)
  }, [chunksProp, colors])

  return (
    <group rotation={rotation} position={position}>
      {geometries.map((geometry, index) => (
        <points key={index} geometry={geometry}>
          <pointsMaterial
            size={radius}
            color={color}
            vertexColors={hasVertexColors}
            toneMapped={false}
            sizeAttenuation={sizeAttenuation}
          />
        </points>
      ))}
    </group>
  )
}

export default PointCloudLayer
