import { postJSON } from '../utils/http.js';

export function initTrajectoryControl() {
  const startButton = document.querySelector('[data-trajectory-start]');
  const statusEl = document.querySelector('[data-trajectory-status]');
  const lockEl = document.querySelector('[data-trajectory-lock-state]');
  if (!startButton) return;

  let confirmPending = false;
  let confirmTimer = null;
  const defaultLabel = startButton.textContent;

  const setStatus = (text, state) => {
    if (statusEl) statusEl.textContent = text;
    startButton.classList.remove('success', 'error');
    if (state) startButton.classList.add(state);
  };

  const resetConfirm = () => {
    confirmPending = false;
    startButton.textContent = defaultLabel;
    startButton.classList.remove('error');
    if (confirmTimer) {
      clearTimeout(confirmTimer);
      confirmTimer = null;
    }
  };

  const requestExecute = () => {
    setStatus('任务执行中...', null);
    postJSON('/api/trajectory/execute', {})
      .then((payload) => {
        setStatus(`任务执行完成 (${payload?.points ?? 0} 点)`, 'success');
      })
      .catch((error) => {
        setStatus(error?.message || '执行失败', 'error');
      })
      .finally(() => {
        resetConfirm();
      });
  };

  startButton.addEventListener('click', () => {
    if (lockEl?.dataset.locked !== 'true') {
      resetConfirm();
      setStatus('请先锁定轨迹', 'error');
      return;
    }
    if (!confirmPending) {
      confirmPending = true;
      startButton.textContent = '确认开始';
      startButton.classList.add('error');
      setStatus('请确认开始任务', null);
      confirmTimer = setTimeout(resetConfirm, 3000);
      return;
    }
    requestExecute();
  });
}
