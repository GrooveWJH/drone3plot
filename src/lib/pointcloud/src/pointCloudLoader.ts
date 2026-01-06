import type { LasLoadOptions, PointCloudResult } from './pointCloudTypes'
import { loadLasPointCloud } from './lasLoader'
import { loadPcdPointCloud } from './pcdLoader'

export type { LasLoadProgress, LasLoadResult, PointCloudResult, LasLoadOptions } from './pointCloudTypes'
export { loadLasPointCloud } from './lasLoader'

export const loadPointCloud = async (
  file: File,
  options: LasLoadOptions
): Promise<PointCloudResult> => {
  const name = file.name.toLowerCase()
  if (name.endsWith('.pcd')) {
    return loadPcdPointCloud(file, options)
  }
  const lasResult = await loadLasPointCloud(file, options)
  return {
    points: lasResult.points,
    colors: lasResult.colors,
    totalPoints: lasResult.header.pointCount,
    sampleEvery: lasResult.sampleEvery,
    acceptedPoints: lasResult.acceptedPoints,
  }
}
