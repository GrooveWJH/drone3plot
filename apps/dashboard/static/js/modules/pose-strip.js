import { getJSON } from '../utils/http.js';

export function initPoseStrip() {
  const xEl = document.querySelector('[data-pose-x]');
  const yEl = document.querySelector('[data-pose-y]');
  const zEl = document.querySelector('[data-pose-z]');
  const yawEl = document.querySelector('[data-pose-yaw]');
  const rhEl = document.querySelector('[data-relative-height]');
  const flightModeEl = document.querySelector('[data-flight-mode]');
  let pollTimer = null;
  let pollIntervalMs = 1000;

  if (!xEl || !yEl || !zEl || !yawEl || !rhEl || !flightModeEl) return;

  const reset = () => {
    xEl.textContent = '--';
    yEl.textContent = '--';
    zEl.textContent = '--';
    yawEl.textContent = '--';
    rhEl.textContent = '--';
    flightModeEl.textContent = '--';
  };

  const format = (value) => {
    if (typeof value !== 'number' || Number.isNaN(value)) return '--';
    return value.toFixed(3);
  };

  const setPollInterval = (hz) => {
    const safeHz = Number.isFinite(hz) && hz > 0 ? hz : 1;
    const nextInterval = Math.max(1, Math.round(1000 / safeHz));
    if (nextInterval === pollIntervalMs) return;
    pollIntervalMs = nextInterval;
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = setInterval(updateAll, pollIntervalMs);
    }
  };

  const updatePose = () => {
    getJSON('/api/pose')
      .then((payload) => {
        xEl.textContent = format(payload?.x);
        yEl.textContent = format(payload?.y);
        zEl.textContent = format(payload?.z);
        yawEl.textContent = format(payload?.yaw);
        const mqttHz = Number(payload?.frequency?.mqtt);
        if (Number.isFinite(mqttHz) && mqttHz > 0) {
          setPollInterval(mqttHz);
        } else {
          setPollInterval(1);
        }
      })
      .catch(() => {
        xEl.textContent = '--';
        yEl.textContent = '--';
        zEl.textContent = '--';
        yawEl.textContent = '--';
        setPollInterval(1);
      });
  };

  const updateRelativeHeight = () => {
    getJSON('/api/telemetry')
      .then((payload) => {
        rhEl.textContent = format(payload?.position?.relative_altitude);
        const modeLabel = payload?.flight?.mode_label ?? payload?.flight?.mode_code;
        flightModeEl.textContent =
          typeof modeLabel === 'number' ? `模式 ${modeLabel}` : modeLabel || '--';
      })
      .catch(() => {
        rhEl.textContent = '--';
        flightModeEl.textContent = '--';
      });
  };

  const updateAll = () => {
    updatePose();
    updateRelativeHeight();
  };

  const startPoll = () => {
    if (pollTimer) return;
    updateAll();
    pollTimer = setInterval(updateAll, pollIntervalMs);
  };

  const stopPoll = () => {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    pollIntervalMs = 1000;
    reset();
  };

  window.addEventListener('drc-state', (event) => {
    const state = event?.detail;
    if (state === 'drc_ready') {
      startPoll();
    } else {
      stopPoll();
    }
  });

  stopPoll();
}
