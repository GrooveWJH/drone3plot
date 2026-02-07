import { postJSON } from "../utils/http.js";
import { createLivePlayer } from "./live-player.js";

export function initLiveStream() {
	const startButton = document.querySelector("[data-live-start]");
	const stopButton = document.querySelector("[data-live-stop]");
	const rtmpInput = document.querySelector("[data-live-rtmp]");
	const playbackInput = document.querySelector("[data-live-playback]");
	const feedback = document.querySelector("[data-live-feedback]");
	const stage = document.querySelector("[data-live-stage]");
	const video = document.querySelector("[data-live-video]");
	const resolution = document.querySelector("[data-live-resolution]");
	const statusPill = document.querySelector("[data-live-pill]");
	const statusPillText = statusPill;
	const liveCard = document.querySelector("[data-live-card]");
	const qualityRadios = Array.from(
		document.querySelectorAll('input[name="live_quality"]'),
	);
	if (!startButton || !stopButton || !playbackInput || !stage || !video) return;
	const urlCacheKey = "dashboard_live_urls_v1";
	let isLive = false;
	let selectedQuality = 0;
	let isAvailable = false;
	const defaultStartLabel = startButton.textContent;
	const setPill = (state, text) => {
		if (!statusPill || !statusPillText) return;
		statusPill.classList.remove("state-ok", "state-warn", "state-error");
		if (state === "live") {
			statusPill.classList.add("state-ok");
		} else if (state === "starting") {
			statusPill.classList.add("state-warn");
		} else if (state === "error") {
			statusPill.classList.add("state-error");
		}
		statusPillText.textContent = text || statusPillText.textContent;
	};
	const setButtons = (state) => {
		if (!isAvailable && !isLive) {
			startButton.disabled = true;
			stopButton.disabled = true;
			startButton.textContent = "等待连接";
			return;
		}
		if (state === "live") {
			startButton.disabled = true;
			stopButton.disabled = false;
			startButton.textContent = "直播中";
		} else if (state === "starting") {
			startButton.disabled = true;
			stopButton.disabled = true;
			startButton.textContent = "启动中...";
		} else {
			startButton.disabled = false;
			stopButton.disabled = true;
			startButton.textContent = defaultStartLabel;
		}
	};
	const setStageActive = (active) => {
		stage.classList.toggle("is-active", active);
	};
	const player = createLivePlayer({
		video,
		resolution,
		feedback,
		onError: () => setPill("error", "播放异常"),
	});
	let lastPlaybackUrl = "";
	let retryTimer = null;
	let retrying = false;
	const retryConfig = { intervalMs: 2000, maxAttempts: 8 };
	const streamCheck = {
		intervalMs: 1500,
		timeoutMs: 15000,
		requestTimeoutMs: 2000,
	};

	const fetchWithTimeout = (url, timeoutMs) => {
		const controller = new AbortController();
		const timer = setTimeout(() => controller.abort(), timeoutMs);
		return fetch(url, { signal: controller.signal }).finally(() =>
			clearTimeout(timer),
		);
	};

	const waitForStream = async (url) => {
		const deadline = Date.now() + streamCheck.timeoutMs;
		while (Date.now() < deadline) {
			try {
				const resp = await fetchWithTimeout(url, streamCheck.requestTimeoutMs);
				if (resp.ok) return true;
			} catch (_) {
				// ignore and retry
			}
			await new Promise((resolve) =>
				setTimeout(resolve, streamCheck.intervalMs),
			);
		}
		return false;
	};

	const scheduleRetry = async () => {
		if (!lastPlaybackUrl || retrying) return;
		retrying = true;
		let attempt = 0;
		const retry = async () => {
			attempt += 1;
			if (attempt > retryConfig.maxAttempts) {
				retrying = false;
				return;
			}
			if (feedback) feedback.textContent = "播放异常，自动重试中...";
			const ready = await waitForStream(lastPlaybackUrl);
			if (ready) {
				player.play(lastPlaybackUrl);
				retrying = false;
				return;
			}
			retryTimer = setTimeout(retry, retryConfig.intervalMs);
		};
		retry();
	};
	startButton.addEventListener("click", () => {
		if (feedback) feedback.textContent = "正在开启直播...";
		setButtons("starting");
		setPill("starting", "启动中");
		const rtmpUrl = rtmpInput?.value?.trim();
		const playbackUrl = playbackInput.value.trim();
		if (!playbackUrl) {
			if (feedback) feedback.textContent = "请填写播放 URL。";
			setButtons("idle");
			setPill("error", "配置错误");
			return;
		}
		postJSON("/api/stream/start", {
			rtmp_url: rtmpUrl || playbackUrl,
			video_quality: selectedQuality,
		})
			.then(() => {
				setStageActive(true);
				setPill("live", "直播中");
				setButtons("live");
				isLive = true;
				lastPlaybackUrl = playbackUrl;
				if (feedback) feedback.textContent = "检测流可用性...";
				waitForStream(playbackUrl).then((ready) => {
					if (!ready) {
						if (feedback) feedback.textContent = "直播流尚不可用，继续重试...";
						scheduleRetry();
						return;
					}
					player.play(playbackUrl);
					if (feedback) feedback.textContent = "直播已开启。";
				});
			})
			.catch((err) => {
				if (feedback) feedback.textContent = err?.error ?? "开启直播失败";
				setPill("error", "开启失败");
				setButtons("idle");
				setStageActive(false);
				player.reset();
				isLive = false;
				lastPlaybackUrl = "";
			});
	});
	stopButton.addEventListener("click", () => {
		if (feedback) feedback.textContent = "正在关闭直播...";
		postJSON("/api/stream/stop", {})
			.then(() => {
				setPill("idle", "未开启");
				setButtons("idle");
				setStageActive(false);
				player.reset();
				if (feedback) feedback.textContent = "直播已关闭。";
				isLive = false;
				lastPlaybackUrl = "";
				retrying = false;
				if (retryTimer) {
					clearTimeout(retryTimer);
					retryTimer = null;
				}
			})
			.catch((err) => {
				if (feedback) feedback.textContent = err?.error ?? "关闭直播失败";
			});
	});
	setPill("idle", "未开启");
	setButtons("idle");
	qualityRadios.forEach((radio) => {
		if (radio.checked) {
			selectedQuality = parseInt(radio.value, 10);
		}
		radio.addEventListener("change", () => {
			selectedQuality = parseInt(radio.value, 10);
			if (!isLive) {
				return;
			}
			postJSON("/api/stream/quality", { video_quality: selectedQuality })
				.then(() => {
					if (feedback) feedback.textContent = "画质已更新。";
				})
				.catch((err) => {
					if (feedback) feedback.textContent = err?.error ?? "画质更新失败";
				});
		});
	});

	const resetLiveUi = () => {
		setPill("idle", "未开启");
		setButtons("idle");
		setStageActive(false);
		player.reset();
		isLive = false;
		lastPlaybackUrl = "";
		retrying = false;
		if (retryTimer) {
			clearTimeout(retryTimer);
			retryTimer = null;
		}
		if (feedback) feedback.textContent = "";
	};

	const setAvailability = (available) => {
		isAvailable = available;
		if (liveCard) {
			liveCard.classList.toggle("is-locked", !available);
		}
		if (!available) {
			resetLiveUi();
		} else {
			setButtons(isLive ? "live" : "idle");
		}
	};

	window.addEventListener("drc-state", (event) => {
		const state = event?.detail;
		setAvailability(state === "drc_ready");
	});

	setAvailability(false);

	const applyCachedUrls = () => {
		try {
			const cached = JSON.parse(localStorage.getItem(urlCacheKey) || "null");
			if (!cached || typeof cached !== "object") return;
			if (rtmpInput && cached.rtmp) {
				rtmpInput.value = cached.rtmp;
			}
			if (cached.playback) {
				playbackInput.value = cached.playback;
			}
		} catch (_) {
			// ignore cache errors
		}
	};

	const persistUrls = () => {
		if (!playbackInput) return;
		const payload = {
			rtmp: rtmpInput?.value?.trim() ?? "",
			playback: playbackInput.value.trim(),
		};
		localStorage.setItem(urlCacheKey, JSON.stringify(payload));
	};

	applyCachedUrls();

	if (rtmpInput) {
		rtmpInput.addEventListener("change", persistUrls);
		rtmpInput.addEventListener("blur", persistUrls);
	}
	playbackInput.addEventListener("change", persistUrls);
	playbackInput.addEventListener("blur", persistUrls);
}
