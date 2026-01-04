import { Html, TransformControls } from '@react-three/drei'
import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import type { TransformControls as TransformControlsImpl } from 'three-stdlib'
import type { TransformMode, WaypointData } from '../types/mission'
import { UI_CONFIG } from '../config/ui'

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
            obj.rotation.y = 0
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
        }}
        onClick={(event) => {
          event.stopPropagation()
          onSelect()
        }}
      >
        <mesh>
          <sphereGeometry args={[UI_CONFIG.waypoint.sphereRadius, 18, 18]} />
          <meshStandardMaterial
            color={waypoint.takePhoto ? '#ff2d55' : selected ? '#d66a3c' : '#2f343a'}
            emissive={waypoint.takePhoto ? '#ff2d55' : '#000000'}
            emissiveIntensity={waypoint.takePhoto ? 0.8 : 0}
          />
        </mesh>
        <mesh
          position={[UI_CONFIG.waypoint.coneOffsetX, 0, 0]}
          rotation={[0, 0, -Math.PI / 2]}
        >
          <coneGeometry args={[UI_CONFIG.waypoint.coneRadius, UI_CONFIG.waypoint.coneHeight, 10]} />
          <meshStandardMaterial color="#53b9ff" emissive="#1f6fff" emissiveIntensity={0.35} />
        </mesh>
        <Html position={[0, 0, UI_CONFIG.waypoint.labelOffsetZ]} center>
          <div className="waypoint-label">#{index + 1}</div>
        </Html>
      </group>
    </>
  )
}

export default WaypointMarker
