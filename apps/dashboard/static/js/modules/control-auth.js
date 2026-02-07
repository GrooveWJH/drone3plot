import { getJSON, postJSON } from "../utils/http.js";

export function initControlAuth() {
	const requestButton = document.querySelector("[data-auth-request]");
	const feedback = document.querySelector("[data-auth-feedback]");
	const modal = document.querySelector("[data-auth-modal]");
	const modalStatus = document.querySelector("[data-auth-modal-status]");
	const confirmButton = document.querySelector("[data-auth-confirm]");
	const batteryStatus = document.querySelector("[data-battery-status]");
	const batteryFill = document.querySelector("[data-battery-fill]");
	const statusPill = document.querySelector("[data-auth-pill]");
	const statusPillText = statusPill;
	let batteryTimer = null;
	let statusTimer = null;
	if (!requestButton || !modal || !confirmButton) return;
	modal.inert = modal.getAttribute("aria-hidden") !== "false";
	const defaultRequestLabel = requestButton.textContent;
	const setPill = (state, text) => {
		if (!statusPill || !statusPillText) return;
		statusPill.classList.remove("state-ok", "state-warn", "state-error");
		if (state === "drc_ready") {
			statusPill.classList.add("state-ok");
		} else if (state === "waiting_for_user") {
			statusPill.classList.add("state-warn");
		} else if (state === "error" || state === "unavailable") {
			statusPill.classList.add("state-error");
		}
		statusPillText.textContent = text || statusPillText.textContent;
	};
	const setRequestState = (state) => {
		if (state === "waiting_for_user") {
			requestButton.disabled = true;
			requestButton.textContent = "等待遥控器允许...";
		} else if (state === "drc_ready") {
			requestButton.disabled = true;
			requestButton.textContent = "已连接";
		} else if (state === "error") {
			requestButton.disabled = false;
			requestButton.textContent = "重试连接";
		} else if (state === "unavailable") {
			requestButton.disabled = true;
			requestButton.textContent = "暂不可用";
		} else {
			requestButton.disabled = false;
			requestButton.textContent = defaultRequestLabel;
		}
	};
	const emitState = (state) => {
		window.dispatchEvent(new CustomEvent("drc-state", { detail: state }));
	};

	const setModalHidden = (hidden) => {
		if (hidden) {
			modal.classList.remove("is-open");
			modal.setAttribute("aria-hidden", "true");
			modal.inert = true;
			if (modal.contains(document.activeElement)) {
				document.activeElement.blur();
			}
		} else {
			modal.classList.add("is-open");
			modal.setAttribute("aria-hidden", "false");
			modal.inert = false;
		}
	};

	const openModal = () => {
		setModalHidden(false);
	};

	const closeModal = () => {
		setModalHidden(true);
	};
	const stopBatteryPoll = () => {
		if (batteryTimer) {
			clearInterval(batteryTimer);
			batteryTimer = null;
		}
	};
	const updateBattery = () => {
		getJSON("/api/telemetry")
			.then((payload) => {
				const percent = payload?.battery?.percent;
				if (batteryStatus) {
					batteryStatus.textContent =
						typeof percent === "number" ? `${percent}%` : "--";
				}
				if (batteryFill) {
					if (typeof percent === "number") {
						const clamped = Math.max(0, Math.min(100, percent));
						batteryFill.style.width = `${clamped}%`;
						batteryFill.classList.remove("level-low", "level-mid");
						if (clamped <= 20) {
							batteryFill.classList.add("level-low");
						} else if (clamped <= 50) {
							batteryFill.classList.add("level-mid");
						}
					} else {
						batteryFill.style.width = "0%";
						batteryFill.classList.remove("level-low", "level-mid");
					}
				}
			})
			.catch(() => {
				if (batteryStatus) batteryStatus.textContent = "--";
				if (batteryFill) {
					batteryFill.style.width = "0%";
					batteryFill.classList.remove("level-low", "level-mid");
				}
			});
	};
	const startBatteryPoll = () => {
		stopBatteryPoll();
		updateBattery();
		batteryTimer = setInterval(updateBattery, 2000);
	};
	const resetBattery = () => {
		if (batteryStatus) batteryStatus.textContent = "--";
		if (batteryFill) {
			batteryFill.style.width = "0%";
			batteryFill.classList.remove("level-low", "level-mid");
		}
	};
	const handleState = (state, errorText) => {
		if (state === "unavailable") {
			setPill("unavailable", "不可用");
			setRequestState("unavailable");
			emitState("unavailable");
			if (feedback) feedback.textContent = errorText || "服务不可用";
			stopBatteryPoll();
			resetBattery();
			return;
		}

		setPill(
			state,
			state === "drc_ready"
				? "已连接"
				: state === "waiting_for_user"
					? "等待确认"
					: "未连接",
		);
		setRequestState(state);
		emitState(state);
		if (state === "drc_ready") {
			startBatteryPoll();
		} else {
			stopBatteryPoll();
			resetBattery();
		}
	};

	getJSON("/api/drone/status")
		.then((payload) => {
			if (!payload || payload?.error) {
				handleState("unavailable", payload.error);
				return;
			}
			handleState(payload?.drone?.drc_state || "disconnected");
		})
		.catch(() => {
			handleState("unavailable");
		});

	const startStatusPoll = () => {
		if (statusTimer) return;
		statusTimer = setInterval(() => {
			getJSON("/api/drone/status")
				.then((payload) => {
					if (!payload || payload?.error) {
						handleState("unavailable", payload.error);
						return;
					}
					handleState(payload?.drone?.drc_state || "disconnected");
				})
				.catch(() => {
					handleState("unavailable");
				});
		}, 3000);
	};

	startStatusPoll();

	requestButton.addEventListener("click", () => {
		if (feedback) feedback.textContent = "正在请求控制权...";
		setRequestState("waiting_for_user");
		postJSON("/api/drone/connect", {})
			.then(() => postJSON("/api/drone/auth/request", {}))
			.then((payload) => {
				handleState(payload?.drone?.drc_state || "waiting_for_user");
				if (feedback) feedback.textContent = "已发送请求，请在遥控器允许。";
				if (modalStatus) modalStatus.textContent = "等待遥控器允许...";
				openModal();
				stopBatteryPoll();
			})
			.catch((err) => {
				handleState("error", err?.error ?? "请求失败");
				if (feedback) feedback.textContent = err?.error ?? "请求失败";
			});
	});

	confirmButton.addEventListener("click", () => {
		if (modalStatus) modalStatus.textContent = "正在进入 DRC 模式...";
		confirmButton.disabled = true;
		postJSON("/api/drone/auth/confirm", {})
			.then((payload) => {
				handleState(payload?.drone?.drc_state || "drc_ready");
				if (feedback) feedback.textContent = "DRC 已就绪。";
				closeModal();
				startBatteryPoll();
			})
			.catch((err) => {
				handleState("error", err?.error ?? "进入 DRC 失败");
				if (feedback) feedback.textContent = err?.error ?? "进入 DRC 失败";
				if (modalStatus) modalStatus.textContent = "进入 DRC 失败，请重试。";
				stopBatteryPoll();
				closeModal();
			})
			.finally(() => {
				confirmButton.disabled = false;
			});
	});
}
