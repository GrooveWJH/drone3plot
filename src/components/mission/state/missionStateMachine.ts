import { useCallback, useEffect, useMemo, useReducer } from 'react'

export type MissionState =
  | 'idle'
  | 'loading'
  | 'ready'
  | 'locked'
  | 'executing'
  | 'error'

type MissionEvent =
  | { type: 'POINTCLOUD_LOADING' }
  | { type: 'POINTCLOUD_LOADED' }
  | { type: 'POINTCLOUD_CLEARED' }
  | { type: 'LOCK_TRAJECTORY' }
  | { type: 'UNLOCK_TRAJECTORY' }
  | { type: 'EXECUTE' }
  | { type: 'EXECUTE_DONE' }
  | { type: 'EXECUTE_FAILED' }

const missionReducer = (state: MissionState, event: MissionEvent): MissionState => {
  switch (event.type) {
    case 'POINTCLOUD_LOADING':
      return 'loading'
    case 'POINTCLOUD_LOADED':
      if (state === 'locked' || state === 'executing') return state
      return 'ready'
    case 'POINTCLOUD_CLEARED':
      return 'idle'
    case 'LOCK_TRAJECTORY':
      return state === 'ready' ? 'locked' : state
    case 'UNLOCK_TRAJECTORY':
      return state === 'locked' ? 'ready' : state
    case 'EXECUTE':
      return state === 'locked' ? 'executing' : state
    case 'EXECUTE_DONE':
      return state === 'executing' ? 'locked' : state
    case 'EXECUTE_FAILED':
      return 'error'
    default:
      return state
  }
}

type MissionStateParams = {
  hasPointCloud: boolean
  isLoading: boolean
}

export const useMissionStateMachine = ({ hasPointCloud, isLoading }: MissionStateParams) => {
  const [state, dispatch] = useReducer(missionReducer, 'idle')

  useEffect(() => {
    if (isLoading) {
      dispatch({ type: 'POINTCLOUD_LOADING' })
    } else if (hasPointCloud) {
      dispatch({ type: 'POINTCLOUD_LOADED' })
    } else {
      dispatch({ type: 'POINTCLOUD_CLEARED' })
    }
  }, [hasPointCloud, isLoading])

  const lockTrajectory = useCallback(() => {
    dispatch({ type: 'LOCK_TRAJECTORY' })
  }, [])

  const unlockTrajectory = useCallback(() => {
    dispatch({ type: 'UNLOCK_TRAJECTORY' })
  }, [])

  const toggleTrajectoryLock = useCallback(() => {
    if (state === 'locked') {
      dispatch({ type: 'UNLOCK_TRAJECTORY' })
    } else {
      dispatch({ type: 'LOCK_TRAJECTORY' })
    }
  }, [state])

  const isTrajectoryLocked = state === 'locked' || state === 'executing'
  const canEditWaypoints = state === 'ready'

  const derived = useMemo(
    () => ({
      state,
      isTrajectoryLocked,
      canEditWaypoints,
      lockTrajectory,
      unlockTrajectory,
      toggleTrajectoryLock,
    }),
    [state, isTrajectoryLocked, canEditWaypoints, lockTrajectory, unlockTrajectory, toggleTrajectoryLock]
  )

  return derived
}
