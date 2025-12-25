# drone3plot

Mission planning UI for drones with a point cloud reference scene.

## Features
- Waypoint editing (position + yaw) with ordered list
- LAS point cloud streaming with budgeted sampling
- Per-point color rendering and quick rotation (±90° on X/Y/Z)
- Scripts to analyze LAS size/point counts and color ranges

## Getting Started
```bash
pnpm install
pnpm dev
```

## Scripts
```bash
pnpm analyze:pointcloud
pnpm analyze:las-color
```

## Notes
- Large datasets live in `data/` and are ignored by git.
- LAS color is normalized based on sampled RGB ranges.
