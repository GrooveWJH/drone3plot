import type { TrajectoryFile, TrajectoryMeta } from '../types/mission'

export type BuiltInTrajectory = {
  id: string
  label: string
  url?: string
}

const LIST_KEY = 'trajectory:list'
const itemKey = (id: string) => `trajectory:${id}`

const normalizeLabel = (label: string) => label.replace(/\s+/g, '').toLowerCase()

const readLocalList = (): TrajectoryMeta[] => {
  const raw = localStorage.getItem(LIST_KEY)
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    const items = parsed
      .filter((item) => item && typeof item === 'object')
      .map((item) => ({
        id: String(item.id ?? ''),
        label: String(item.label ?? ''),
        source: 'local' as const,
      }))
      .filter((item) => item.id && item.label)

    const byId = new Map<string, TrajectoryMeta>()
    items.forEach((item) => byId.set(item.id, item))
    return Array.from(byId.values())
  } catch {
    return []
  }
}

const writeLocalList = (items: TrajectoryMeta[]) => {
  localStorage.setItem(LIST_KEY, JSON.stringify(items))
}

export const getTrajectoryOptions = (
  builtIns: ReadonlyArray<BuiltInTrajectory>
): TrajectoryMeta[] => {
  const localList = readLocalList()
  const builtIds = new Set(builtIns.map((item) => item.id))
  const localLabels = new Set(localList.map((item) => normalizeLabel(item.label)))
  const cleanedLocal = localList.filter((item) => !builtIds.has(item.id))
  const builtMeta: TrajectoryMeta[] = builtIns.map((item) => ({
    id: item.id,
    label: item.label,
    source: 'built-in',
    url: item.url,
  }))
  const filteredBuilt = builtMeta.filter(
    (item) => !localLabels.has(normalizeLabel(item.label))
  )
  return [...filteredBuilt, ...cleanedLocal]
}

export const getLocalTrajectory = (id: string): TrajectoryFile | null => {
  const raw = localStorage.getItem(itemKey(id))
  if (!raw) return null
  try {
    return JSON.parse(raw) as TrajectoryFile
  } catch {
    return null
  }
}

export const findLocalTrajectoryIdByLabel = (label: string): string | null => {
  const normalized = normalizeLabel(label)
  const localList = readLocalList()
  const match = localList.find((item) => normalizeLabel(item.label) === normalized)
  return match?.id ?? null
}

export const saveLocalTrajectory = (
  id: string,
  trajectory: TrajectoryFile,
  label: string
) => {
  const localList = readLocalList()
  const payload: TrajectoryFile = { ...trajectory, name: label }
  localStorage.setItem(itemKey(id), JSON.stringify(payload))
  const nextList = [
    ...localList.filter((item) => item.id !== id),
    { id, label, source: 'local' as const },
  ]
  writeLocalList(nextList)
  return { label }
}

export const deleteLocalTrajectory = (id: string) => {
  const localList = readLocalList()
  const nextList = localList.filter((item) => item.id !== id)
  writeLocalList(nextList)
  localStorage.removeItem(itemKey(id))
}

export const findFallbackTrajectoryId = (
  builtIns: ReadonlyArray<BuiltInTrajectory>,
  localOptions: TrajectoryMeta[]
) => builtIns[0]?.id ?? localOptions.find((item) => item.source === 'local')?.id ?? 'default'
