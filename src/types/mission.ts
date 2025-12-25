export type TransformMode = 'translate'

export type WaypointData = {
  id: string
  position: [number, number, number]
  rotation: [number, number, number]
}

export type PointCloudStats = {
  totalPoints: number
  loadedPoints: number
  sampleEvery: number
  budgetMB: number
}

export type LasHeaderInfo = {
  version: string
  versionMajor: number
  versionMinor: number
  headerSize: number
  offsetToPointData: number
  pointCount: number
  pointFormat: number
  recordLength: number
  scale: [number, number, number]
  offset: [number, number, number]
}
