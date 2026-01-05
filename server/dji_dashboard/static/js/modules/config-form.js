import { postJSON } from '../utils/http.js';

export function initConfigForm() {
  const form = document.querySelector('[data-config-form]');
  if (!form) return;
  const cacheKey = 'dashboard_config_cache_v1';
  let applyTimer = null;
  let isLocked = false;
  let lastPayload = null;

  const applyCachedConfig = () => {
    try {
      const cached = JSON.parse(localStorage.getItem(cacheKey) || 'null');
      if (!cached || typeof cached !== 'object') return;
      Object.entries(cached).forEach(([key, value]) => {
        const field = form.querySelector(`[name="${key}"]`);
        if (!field) return;
        field.value = value;
      });
    } catch (_) {
      // Ignore malformed cache.
    }
  };

  applyCachedConfig();
  form.classList.add('is-open');

  const setLocked = (locked) => {
    isLocked = locked;
    form.querySelectorAll('input, select, textarea, button').forEach((field) => {
      field.disabled = locked;
    });
  };

  const buildPayload = () => Object.fromEntries(new FormData(form).entries());

  const applyPayload = () => {
    if (isLocked) return;
    const payload = buildPayload();
    const signature = JSON.stringify(payload);
    if (signature === lastPayload) return;
    lastPayload = signature;
    postJSON('/api/config', payload)
      .then(() => {
        localStorage.setItem(cacheKey, JSON.stringify(payload));
      })
      .catch(() => {});
  };

  const scheduleApply = (immediate = false) => {
    if (isLocked) return;
    if (applyTimer) clearTimeout(applyTimer);
    if (immediate) {
      applyPayload();
      return;
    }
    applyTimer = setTimeout(applyPayload, 300);
  };

  form.addEventListener('input', scheduleApply);
  form.addEventListener('change', scheduleApply);

  window.addEventListener('drc-state', (event) => {
    const state = event?.detail;
    setLocked(state === 'waiting_for_user' || state === 'drc_ready');
  });

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (isLocked) return;
    scheduleApply(true);
  });

  scheduleApply(true);
}
