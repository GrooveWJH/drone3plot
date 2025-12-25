import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'

export type PointCloudLayerProps = {
  points: Float32Array | null
  colors?: Float32Array | null
  color?: string
  radius?: number
  rotation?: [number, number, number]
}

const PointCloudLayer = ({
  points,
  colors = null,
  color = '#8fa3a8',
  radius = 0.12,
  rotation = [0, 0, 0],
}: PointCloudLayerProps) => {
  const meshRef = useRef<THREE.InstancedMesh>(null)
  const instanceCount = points ? Math.floor(points.length / 3) : 0

  const baseGeometry = useMemo(() => new THREE.SphereGeometry(radius, 8, 8), [radius])

  useEffect(() => () => baseGeometry.dispose(), [baseGeometry])

  useEffect(() => {
    const mesh = meshRef.current
    if (!mesh || !points || instanceCount === 0) return

    const temp = new THREE.Object3D()
    for (let i = 0; i < instanceCount; i += 1) {
      const base = i * 3
      temp.position.set(points[base], points[base + 1], points[base + 2])
      temp.updateMatrix()
      mesh.setMatrixAt(i, temp.matrix)
    }
    mesh.instanceMatrix.needsUpdate = true

    if (colors && colors.length === points.length) {
      mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(instanceCount * 3), 3)
      mesh.geometry.setAttribute('instanceColor', mesh.instanceColor)
      const color = new THREE.Color()
      for (let i = 0; i < instanceCount; i += 1) {
        const base = i * 3
        color.setRGB(colors[base], colors[base + 1], colors[base + 2])
        mesh.setColorAt(i, color)
      }
      mesh.instanceColor.needsUpdate = true
      const material = mesh.material
      if (Array.isArray(material)) {
        material.forEach((entry) => {
          entry.needsUpdate = true
        })
      } else {
        material.needsUpdate = true
      }
    } else {
      mesh.instanceColor = null
      if (mesh.geometry.getAttribute('instanceColor')) {
        mesh.geometry.deleteAttribute('instanceColor')
      }
    }
  }, [points, colors, instanceCount])

  return (
    <group rotation={rotation}>
      <instancedMesh ref={meshRef} args={[baseGeometry, undefined, instanceCount]} frustumCulled={false}>
        <meshBasicMaterial color={color} vertexColors={!!colors} toneMapped={false} />
      </instancedMesh>
    </group>
  )
}

export default PointCloudLayer
