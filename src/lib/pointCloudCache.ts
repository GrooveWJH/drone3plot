type CachedPointCloud = {
  blob: Blob
  name: string
  type: string
  lastModified: number
}

const DB_NAME = 'drone3plot-cache'
const STORE_NAME = 'pointcloud'
const CACHE_KEY = 'last'

const openDb = (): Promise<IDBDatabase> =>
  new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME)
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })

const runTransaction = async <T>(
  mode: IDBTransactionMode,
  handler: (store: IDBObjectStore) => IDBRequest<T>
): Promise<T> => {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, mode)
    const store = tx.objectStore(STORE_NAME)
    const request = handler(store)
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
    tx.oncomplete = () => db.close()
    tx.onerror = () => reject(tx.error)
  })
}

export const cachePointCloudFile = async (file: File) => {
  try {
    const payload: CachedPointCloud = {
      blob: file,
      name: file.name,
      type: file.type,
      lastModified: file.lastModified,
    }
    await runTransaction('readwrite', (store) => store.put(payload, CACHE_KEY))
  } catch {
    // ignore cache failures
  }
}

export const getCachedPointCloudFile = async (): Promise<File | null> => {
  try {
    const result = await runTransaction<CachedPointCloud | undefined>('readonly', (store) =>
      store.get(CACHE_KEY)
    )
    if (!result) return null
    return new File([result.blob], result.name, {
      type: result.type,
      lastModified: result.lastModified,
    })
  } catch {
    return null
  }
}

export const clearCachedPointCloudFile = async () => {
  try {
    await runTransaction('readwrite', (store) => store.delete(CACHE_KEY))
  } catch {
    // ignore cache failures
  }
}
