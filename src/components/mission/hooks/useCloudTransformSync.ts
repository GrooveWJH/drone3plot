import { useEffect } from 'react'
import type { RefObject } from 'react'
import type { Group } from 'three'
import { degToRad } from '../utils'

type UseCloudTransformSyncParams = {
  cloudGroupRef: RefObject<Group | null>
  cloudRotation: [number, number, number]
  cloudOffset: [number, number, number]
  hasPointCloud: boolean
}

export const useCloudTransformSync = ({
  cloudGroupRef,
  cloudRotation,
  cloudOffset,
  hasPointCloud,
}: UseCloudTransformSyncParams) => {
  useEffect(() => {
    const group = cloudGroupRef.current
    if (!group) return
    group.position.set(cloudOffset[0], cloudOffset[1], cloudOffset[2])
    group.rotation.set(
      degToRad(cloudRotation[0]),
      degToRad(cloudRotation[1]),
      degToRad(cloudRotation[2])
    )
  }, [cloudOffset, cloudRotation, cloudGroupRef, hasPointCloud])
}
