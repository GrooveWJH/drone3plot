import { initConfigForm } from './modules/config-form.js';
import { initControlAuth } from './modules/control-auth.js';
import { initLiveStream } from './modules/live-stream.js';
import { initPoseStrip } from './modules/pose-strip.js';
import { initPhotoButton } from './modules/photo.js';

const blockRefreshKeys = (event) => {
  const key = event.key?.toLowerCase();
  const isReloadKey = event.key === 'F5' || (key === 'r' && (event.ctrlKey || event.metaKey));
  if (!isReloadKey) return;
  event.preventDefault();
  event.stopPropagation();
};

window.addEventListener('keydown', blockRefreshKeys, { capture: true });

document.addEventListener('DOMContentLoaded', () => {
  initControlAuth();
  initLiveStream();
  initConfigForm();
  initPoseStrip();
  initPhotoButton();
});
