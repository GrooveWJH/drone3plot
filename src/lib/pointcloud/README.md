# Point Cloud Loader + Renderer (Extracted)

This directory contains the high‑performance point cloud loading + streaming renderer that powers `drone3plot`.
It is the **shared module** used by the app (not a copy), so it can be extracted later as a standalone project.

## Contents

- `src/pointCloudLoader.ts`
  - LAS/PCD parsing, sampling, progress reporting, abort support.
- `src/pointCloudWorker.ts`
  - Web Worker wrapper: hash check + chunked postMessage.
- `src/usePointCloudLoader.ts`
  - React hook that orchestrates loading, chunk buffering, and pause‑while‑interacting.
- `src/PointCloudLayer.tsx`
  - Chunk‑aware renderer that builds geometries incrementally.
- `src/GpuUploadTimer.tsx`
  - Optional GPU upload timing probe.
- `src/usePerfObservers.ts`
  - Optional long task/perf logging.
- `docs/pointcloud_pipeline.md`
  - Full pipeline description + PlantUML diagrams.

## Key Features

- Worker decode with **hash‑based cache skip**
- **Chunked streaming**: points are rendered as chunks arrive
- **Interaction‑safe**: while user orbits/zooms, chunk flush is paused
- Progress reporting with timestamps and deltas
- Abortable load and immediate close

## Expected Dependencies

- `three`
- `@react-three/fiber`
- `@react-three/drei`
- React 18+ (hook usage)

## Minimal Integration Checklist

1) Move `src/lib/pointcloud` into your project (or import as a package).
2) Provide a config with these values (or hardcode):

```ts
export const POINTCLOUD_CONFIG = {
  budgetMB: 100,
  radius: 0.75,
  fixedPixelSize: true,
  boundsRadius: 1000,
  chunkSize: 200000,
  chunkBatch: 2,
}
```

1) Wire the hook in a parent component:

```tsx
const {
  pointCloud,
  pointCloudChunks,
  pointCloudChunkVersion,
  pointsColor,
  pointRadius,
  pointSizeAttenuation,
  handleFileSelect,
  clearPointCloud,
  isLoading,
  stats,
} = usePointCloudLoader({
  onPrepareFile: (name) => {},
  onResetCloudTransform: () => {},
  isInteracting: isOrbiting || isDragging,
})
```

1) Render the layer:

```tsx
<PointCloudLayer
  points={pointCloud}
  chunks={pointCloudChunks}
  chunkVersion={pointCloudChunkVersion}
  color={pointsColor}
  radius={pointRadius}
  sizeAttenuation={!POINTCLOUD_CONFIG.fixedPixelSize}
  chunkSize={POINTCLOUD_CONFIG.chunkSize}
  chunkBatch={POINTCLOUD_CONFIG.chunkBatch}
/>
```

1) Worker usage: `usePointCloudLoader` already uses `pointCloudWorker.ts` via `new Worker(new URL(...))`.
   If you reorganize paths, update that import.

## Notes

- This copy still references app‑level types and config names. When extracting
  into a standalone project, rename imports and adjust paths as needed.
- The loader supports **LAS** and **PCD** formats.
- Chunked rendering reduces the big GC/longtask spikes and enables smooth camera interaction.

## Roadmap Ideas

- Publish as a package with typed exports
- Move config + types into this folder
- Optional GPU instancing mode for extremely large datasets
