import { Html, TransformControls } from '@react-three/drei'
import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import type { TransformControls as TransformControlsImpl } from 'three-stdlib'
import type { TransformMode, WaypointData } from '../types/mission'
import { UI_CONFIG } from '../config/ui'
import WaypointShape from './WaypointShape'

export type WaypointMarkerProps = {
  waypoint: WaypointData
  index: number
  mode: TransformMode
  selected: boolean
  isLocked: boolean
  onSelect: () => void
  onUpdate: (id: string, position: [number, number, number], rotation: [number, number, number]) => void
  onTransforming: (value: boolean) => void
}

const WaypointMarker = ({
  waypoint,
  index,
  mode,
  selected,
  isLocked,
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
        enabled={selected && !isLocked}
        showX={selected && !isLocked}
        showY={selected && !isLocked}
        showZ={selected && !isLocked}
        onPointerDown={() => {
          if (!isLocked) onTransforming(true)
        }}
        onPointerUp={() => {
          if (!isLocked) onTransforming(false)
        }}
        onObjectChange={() => {
          if (isLocked) return
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
          if (!isLocked) {
            event.stopPropagation()
          }
        }}
        onClick={(event) => {
          if (isLocked) return
          event.stopPropagation()
          onSelect()
        }}
      >
        <WaypointShape
          sphereColor={waypoint.takePhoto ? '#ff2d55' : selected ? '#d66a3c' : '#335591'}
          coneColor={waypoint.takePhoto ? '#53b9ff' : '#335591'}
          sphereEmissive={waypoint.takePhoto ? '#ff2d55' : '#000000'}
          coneEmissive={waypoint.takePhoto ? '#1f6fff' : '#0f1c33'}
          sphereEmissiveIntensity={waypoint.takePhoto ? 0.8 : 0}
          coneEmissiveIntensity={waypoint.takePhoto ? 0.35 : 0.2}
        />
        <Html position={[0, 0, UI_CONFIG.waypoint.labelOffsetZ]} center>
          <div
            className="waypoint-label"
            onClick={(event) => {
              if (isLocked) return
              event.stopPropagation()
              onSelect()
            }}
          >
            #{index + 1}
          </div>
        </Html>
      </group>
    </>
  )
}

export default WaypointMarker
