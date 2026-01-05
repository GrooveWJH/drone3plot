export const UI_CONFIG = {
  palette: {
    ink: '#1b1a17',
    inkMuted: '#5f5950',
    surface: '#0b1114',
    panel: '#ffffff',
    accent: '#d66a3c',
    accentWarm: '#e18d5c',
    accentGlow: '#f4b156',
  },
  pointCloud: {
    radius: 0.75,
    budgetMB: 100,
    fixedPixelSize: true,
    boundsRadius: 1000,
    chunkSize: 200000,
    chunkBatch: 2,
  },
  waypoint: {
    sphereRadius: 0.1,
    coneRadius: 0.05,
    coneHeight: 0.2,
    coneOffsetX: 0.25,
    labelOffsetZ: 0.5,
  },
  grid: {
    size: 200,
    coarseDivisions: 40,
    fineDivisions: 200,
    coarseColor: '#b7b0a4',
    fineColor: '#d5cec2',
  },
  axes: {
    length: 4,
    width: 2,
    colors: {
      x: '#ff0000',
      y: '#00ff00',
      z: '#0000ff',
    },
  },
  path: {
    color: '#d66a3c',
    opacity: 0.8,
    width: 2.5,
  },
  camera: {
    focusDuration: 0.5,
  },
}
