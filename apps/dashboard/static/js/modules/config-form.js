import { postJSON } from "../utils/http.js";

export function initConfigForm() {
	const form = document.querySelector("[data-config-form]");
	if (!form) return;
	const applyButton = document.querySelector("[data-config-apply]");
	const feedback = document.querySelector("[data-config-feedback]");
	const cacheKey = "dashboard_config_cache_v1";
	let isLocked = false;
	const requiredKeys = ["DJI_MQTT_HOST", "DJI_MQTT_PORT"];

	const applyCachedConfig = () => {
		try {
			const cached = JSON.parse(localStorage.getItem(cacheKey) || "null");
			if (!cached || typeof cached !== "object") return;
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
	form.classList.add("is-open");

	const setLocked = (locked) => {
		isLocked = locked;
		form.querySelectorAll("input, select, textarea").forEach((field) => {
			field.disabled = locked;
		});
		if (applyButton) applyButton.disabled = locked;
	};

	const buildPayload = () => Object.fromEntries(new FormData(form).entries());
	const hasRequiredFields = (payload) => {
		const basicFilled = requiredKeys.every(
			(key) => String(payload?.[key] ?? "").trim().length > 0,
		);
		if (!basicFilled) return false;
		const port = Number(payload?.DJI_MQTT_PORT);
		return Number.isInteger(port) && port > 0;
	};

	const persistDraft = () => {
		const payload = buildPayload();
		localStorage.setItem(cacheKey, JSON.stringify(payload));
	};

	const applyPayload = () => {
		if (isLocked) return;
		const payload = buildPayload();
		persistDraft();
		if (!hasRequiredFields(payload)) {
			if (feedback)
				feedback.textContent = "请先填写网关、MQTT Host 与 MQTT Port。";
			return;
		}
		postJSON("/api/drone/config", payload)
			.then(() => {
				if (feedback) feedback.textContent = "配置已应用。";
			})
			.catch((err) => {
				if (feedback) feedback.textContent = err?.error ?? "配置应用失败";
			});
	};

	form.addEventListener("input", persistDraft);
	form.addEventListener("change", persistDraft);

	window.addEventListener("drc-state", (event) => {
		const state = event?.detail;
		setLocked(state === "waiting_for_user" || state === "drc_ready");
	});

	form.addEventListener("submit", (event) => {
		event.preventDefault();
		if (isLocked) return;
		applyPayload();
	});

	if (applyButton) {
		applyButton.addEventListener("click", (event) => {
			event.preventDefault();
			applyPayload();
		});
	}

	persistDraft();
}
