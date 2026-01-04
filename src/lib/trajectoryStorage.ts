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

export const getTrajectoryOptions = (builtIns: BuiltInTrajectory[]): TrajectoryMeta[] => {
  const localList = readLocalList()
  const builtIds = new Set(builtIns.map((item) => item.id))
  const cleanedLocal = localList.filter((item) => !builtIds.has(item.id))
  const builtMeta: TrajectoryMeta[] = builtIns.map((item) => ({
    id: item.id,
    label: item.label,
    source: 'built-in',
    url: item.url,
  }))
  return [...builtMeta, ...cleanedLocal]
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

const uniqueLabel = (preferred: string, existingLabels: string[]) => {
  const normalized = new Set(existingLabels.map(normalizeLabel))
  if (!normalized.has(normalizeLabel(preferred))) return preferred
  const base = preferred.replace(/\s+/g, '') || 'Trajectory'
  let index = 1
  while (normalized.has(normalizeLabel(`${base}${index}`))) {
    index += 1
  }
  return `${base}${index}`
}

export const createNewTrajectoryName = (
  base: string,
  builtIns: BuiltInTrajectory[]
): string => {
  const existingLabels = [
    ...builtIns.map((item) => item.label),
    ...readLocalList().map((item) => item.label),
  ]
  return uniqueLabel(base, existingLabels)
}

export const saveLocalTrajectory = (
  id: string,
  trajectory: TrajectoryFile,
  preferredLabel: string,
  builtIns: BuiltInTrajectory[]
) => {
  const localList = readLocalList()
  const existingLabels = [
    ...builtIns.map((item) => item.label),
    ...localList.filter((item) => item.id !== id).map((item) => item.label),
  ]
  const finalLabel = uniqueLabel(preferredLabel, existingLabels)
  const payload: TrajectoryFile = { ...trajectory, name: finalLabel }
  localStorage.setItem(itemKey(id), JSON.stringify(payload))
  const nextList = [...localList.filter((item) => item.id !== id), { id, label: finalLabel, source: 'local' as const }]
  writeLocalList(nextList)
  return { label: finalLabel }
}

export const deleteLocalTrajectory = (id: string) => {
  const localList = readLocalList()
  const nextList = localList.filter((item) => item.id !== id)
  writeLocalList(nextList)
  localStorage.removeItem(itemKey(id))
}

export const findFallbackTrajectoryId = (
  builtIns: BuiltInTrajectory[],
  localOptions: TrajectoryMeta[]
) => builtIns[0]?.id ?? localOptions.find((item) => item.source === 'local')?.id ?? 'default'
