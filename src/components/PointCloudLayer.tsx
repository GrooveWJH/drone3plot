import { useEffect, useMemo } from 'react'
import * as THREE from 'three'

export type PointCloudLayerProps = {
  points: Float32Array | null
  colors?: Float32Array | null
  color?: string
  radius?: number
  rotation?: [number, number, number]
  sizeAttenuation?: boolean
}

const PointCloudLayer = ({
  points,
  colors = null,
  color = '#8fa3a8',
  radius = 0.12,
  rotation = [0, 0, 0],
  sizeAttenuation = true,
}: PointCloudLayerProps) => {
  const geometry = useMemo(() => {
    const geom = new THREE.BufferGeometry()
    if (points && points.length > 0) {
      geom.setAttribute('position', new THREE.BufferAttribute(points, 3))
      if (colors && colors.length === points.length) {
        geom.setAttribute('color', new THREE.BufferAttribute(colors, 3))
      }
      geom.computeBoundingSphere()
    }
    return geom
  }, [points, colors])

  useEffect(() => () => geometry.dispose(), [geometry])

  return (
    <group rotation={rotation}>
      <points geometry={geometry}>
        <pointsMaterial
          size={radius}
          color={color}
          vertexColors={!!colors}
          toneMapped={false}
          sizeAttenuation={sizeAttenuation}
        />
      </points>
    </group>
  )
}

export default PointCloudLayer
