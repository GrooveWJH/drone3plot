import { memo } from 'react'
import { UI_CONFIG } from '../config/ui'

type WaypointShapeProps = {
  sphereColor: string
  coneColor: string
  sphereEmissive?: string
  coneEmissive?: string
  sphereEmissiveIntensity?: number
  coneEmissiveIntensity?: number
}

const WaypointShape = ({
  sphereColor,
  coneColor,
  sphereEmissive = '#000000',
  coneEmissive = '#000000',
  sphereEmissiveIntensity = 0,
  coneEmissiveIntensity = 0,
}: WaypointShapeProps) => (
  <>
    <mesh>
      <sphereGeometry args={[UI_CONFIG.waypoint.sphereRadius, 18, 18]} />
      <meshStandardMaterial
        color={sphereColor}
        emissive={sphereEmissive}
        emissiveIntensity={sphereEmissiveIntensity}
      />
    </mesh>
    <mesh
      position={[UI_CONFIG.waypoint.coneOffsetX, 0, 0]}
      rotation={[0, 0, -Math.PI / 2]}
    >
      <coneGeometry args={[UI_CONFIG.waypoint.coneRadius, UI_CONFIG.waypoint.coneHeight, 10]} />
      <meshStandardMaterial
        color={coneColor}
        emissive={coneEmissive}
        emissiveIntensity={coneEmissiveIntensity}
      />
    </mesh>
  </>
)

export default memo(WaypointShape)
