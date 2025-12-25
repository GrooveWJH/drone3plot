import { Html, TransformControls } from '@react-three/drei'
import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import type { TransformControls as TransformControlsImpl } from 'three-stdlib'
import type { TransformMode, WaypointData } from '../types/mission'

export type WaypointMarkerProps = {
  waypoint: WaypointData
  index: number
  mode: TransformMode
  selected: boolean
  onSelect: () => void
  onUpdate: (id: string, position: [number, number, number], rotation: [number, number, number]) => void
  onTransforming: (value: boolean) => void
}

const WaypointMarker = ({
  waypoint,
  index,
  mode,
  selected,
  onSelect,
  onUpdate,
  onTransforming,
}: WaypointMarkerProps) => {
  const groupRef = useRef<THREE.Group>(null)
  const controlsRef = useRef<TransformControlsImpl>(null)

  useEffect(() => {
    const controls = controlsRef.current
    const group = groupRef.current
    if (!controls || !group) return

    if (selected) {
      controls.attach(group)
    } else {
      controls.detach()
    }

    return () => {
      controls.detach()
    }
  }, [selected])

  return (
    <>
      <TransformControls
        ref={controlsRef}
        mode={mode}
        enabled={selected}
        showX={selected}
        showY={selected}
        showZ={selected}
        onDraggingChanged={(event) => onTransforming(event.value)}
        onObjectChange={() => {
          const obj = groupRef.current
          if (!obj) return
          if (mode === 'rotate') {
            obj.rotation.x = 0
            obj.rotation.z = 0
          }
          onUpdate(waypoint.id, [obj.position.x, obj.position.y, obj.position.z], [
            obj.rotation.x,
            obj.rotation.y,
            obj.rotation.z,
          ])
        }}
      />
      <group
        ref={groupRef}
        position={waypoint.position}
        rotation={waypoint.rotation}
        onPointerDown={(event) => {
          event.stopPropagation()
          onSelect()
        }}
      >
        <mesh>
          <sphereGeometry args={[0.5, 18, 18]} />
          <meshStandardMaterial color={selected ? '#f97316' : '#fbbf24'} />
        </mesh>
        <mesh position={[0, 0, 1.25]} rotation={[Math.PI / 2, 0, 0]}>
          <coneGeometry args={[0.25, 0.8, 10]} />
          <meshStandardMaterial color="#fde68a" />
        </mesh>
        <Html position={[0, 1.2, 0]} center>
          <div className="waypoint-label">#{index + 1}</div>
        </Html>
      </group>
    </>
  )
}

export default WaypointMarker
