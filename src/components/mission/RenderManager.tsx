import { useEffect } from 'react'
import { useFrame, useThree } from '@react-three/fiber'

export type RenderManagerProps = {
  deps: unknown[]
  active: boolean
  onInvalidate: (fn: () => void) => void
}

const RenderManager = ({ deps, active, onInvalidate }: RenderManagerProps) => {
  const { invalidate } = useThree()
  useEffect(() => {
    onInvalidate(invalidate)
  }, [invalidate, onInvalidate])

  useEffect(() => {
    invalidate()
  }, deps)

  useFrame(() => {
    if (active) invalidate()
  })

  return null
}

export default RenderManager
