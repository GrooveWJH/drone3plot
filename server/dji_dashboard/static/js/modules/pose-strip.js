import { getJSON } from '../utils/http.js';

export function initPoseStrip() {
  const xEl = document.querySelector('[data-pose-x]');
  const yEl = document.querySelector('[data-pose-y]');
  const zEl = document.querySelector('[data-pose-z]');
  const yawEl = document.querySelector('[data-pose-yaw]');
  const rhEl = document.querySelector('[data-relative-height]');
  let pollTimer = null;

  if (!xEl || !yEl || !zEl || !yawEl || !rhEl) return;

  const reset = () => {
    xEl.textContent = '--';
    yEl.textContent = '--';
    zEl.textContent = '--';
    yawEl.textContent = '--';
    rhEl.textContent = '--';
  };

  const format = (value) => {
    if (typeof value !== 'number' || Number.isNaN(value)) return '--';
    return value.toFixed(3);
  };

  const updatePose = () => {
    getJSON('/api/pose')
      .then((payload) => {
        xEl.textContent = format(payload?.x);
        yEl.textContent = format(payload?.y);
        zEl.textContent = format(payload?.z);
        yawEl.textContent = format(payload?.yaw);
      })
      .catch(() => {
        xEl.textContent = '--';
        yEl.textContent = '--';
        zEl.textContent = '--';
        yawEl.textContent = '--';
      });
  };

  const updateRelativeHeight = () => {
    getJSON('/api/telemetry')
      .then((payload) => {
        rhEl.textContent = format(payload?.position?.relative_altitude);
      })
      .catch(() => {
        rhEl.textContent = '--';
      });
  };

  const updateAll = () => {
    updatePose();
    updateRelativeHeight();
  };

  const startPoll = () => {
    if (pollTimer) return;
    updateAll();
    pollTimer = setInterval(updateAll, 1000);
  };

  const stopPoll = () => {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
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
