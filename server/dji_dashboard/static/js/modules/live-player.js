export function createLivePlayer({ video, resolution, feedback, onError, onErrorDetails }) {
  let hls = null;
  let fpsTimer = null;
  let lastFrames = null;
  let ratioTimer = null;
  let lastSize = { w: 0, h: 0 };

  const reset = () => {
    if (hls) {
      hls.destroy();
      hls = null;
    }
    video.pause();
    video.removeAttribute('src');
    video.load();
    if (resolution) resolution.textContent = '--';
    if (fpsTimer) {
      clearInterval(fpsTimer);
      fpsTimer = null;
    }
    if (ratioTimer) {
      clearInterval(ratioTimer);
      ratioTimer = null;
    }
    lastFrames = null;
    lastSize = { w: 0, h: 0 };
  };

  const syncAspectRatio = () => {
    if (video.videoWidth && video.videoHeight) {
      const wrapper = video.parentElement;
      if (!wrapper) return;
      const height = wrapper.getBoundingClientRect().height;
      const ratio = video.videoWidth / video.videoHeight;
      const targetWidth = height * ratio;
      wrapper.style.width = `${Math.floor(targetWidth)}px`;
      if (resolution) {
        resolution.textContent = `${video.videoWidth}x${video.videoHeight}`;
      }
    }
  };

  const startFpsMeter = () => {
    if (!resolution) return;
    if (fpsTimer) clearInterval(fpsTimer);
    fpsTimer = setInterval(() => {
      if (video.videoWidth && video.videoHeight) {
        let fpsText = 'FPS --';
        if (typeof video.getVideoPlaybackQuality === 'function') {
          const quality = video.getVideoPlaybackQuality();
          const currentFrames = quality.totalVideoFrames;
          if (lastFrames !== null) {
            const fps = Math.max(0, currentFrames - lastFrames);
            fpsText = `FPS ${fps}`;
          }
          lastFrames = currentFrames;
        }
        resolution.textContent = `${video.videoWidth}x${video.videoHeight} · ${fpsText}`;
      }
    }, 1000);
  };

  const startRatioWatcher = () => {
    if (ratioTimer) return;
    ratioTimer = setInterval(() => {
      if (!video.videoWidth || !video.videoHeight) return;
      if (video.videoWidth !== lastSize.w || video.videoHeight !== lastSize.h) {
        lastSize = { w: video.videoWidth, h: video.videoHeight };
        syncAspectRatio();
      }
    }, 400);
  };

  const play = (url) => {
    reset();
    if (!url) return;
    const normalizedUrl = url.includes('/index.m3u8') ? url : `${url.replace(/\/+$/, '')}/index.m3u8`;
    const isHls = normalizedUrl.includes('.m3u8');
    if (window.Hls && window.Hls.isSupported() && isHls) {
      hls = new window.Hls({ liveSyncDurationCount: 3, liveMaxLatencyDurationCount: 5 });
      hls.loadSource(normalizedUrl);
      hls.attachMedia(video);
      hls.on(window.Hls.Events.MANIFEST_PARSED, () => {
        video.play().catch(() => {});
        startRatioWatcher();
      });
      hls.on(window.Hls.Events.ERROR, (_event, data) => {
        if (onErrorDetails) {
          onErrorDetails('hls-error', data);
        }
        if (data?.fatal) {
          if (feedback) feedback.textContent = '直播播放异常，请检查播放地址。';
          if (onError) onError();
        }
      });
    } else {
      video.src = normalizedUrl;
      video.play().catch(() => {});
      startRatioWatcher();
    }
  };

  video.addEventListener('error', () => {
    const err = video.error;
    if (onErrorDetails) {
      onErrorDetails('video-error', err ? { code: err.code, message: err.message } : null);
    }
    if (feedback) feedback.textContent = '直播播放异常，请检查播放地址。';
    if (onError) onError();
  });

  video.addEventListener('loadedmetadata', () => {
    syncAspectRatio();
    startFpsMeter();
    startRatioWatcher();
  });

  video.addEventListener('resize', () => {
    syncAspectRatio();
  });

  window.addEventListener('resize', syncAspectRatio);

  return { play, reset };
}
