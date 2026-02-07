import { getJSON, postJSON } from "../utils/http.js";

function phaseLabel(phase) {
	const labels = {
		IDLE: "待命",
		VALIDATING: "校验中",
		ARMING: "解锁中",
		TAKING_OFF: "起飞中",
		ALIGNING_TO_FIRST: "首段对准",
		RUNNING_WAYPOINTS: "执行航点",
		RETURNING_HOME: "返航点",
		LANDING: "降落中",
		COMPLETED: "完成",
		FAILED: "失败",
		ABORTING: "中止中",
		ABORTED: "已中止",
	};
	return labels[phase] || phase || "未知";
}

export function initTrajectoryControl() {
	const startButton = document.querySelector("[data-trajectory-start]");
	const statusEl = document.querySelector("[data-trajectory-status]");
	if (!startButton) return;

	let confirmPending = false;
	let confirmTimer = null;
	let statusTimer = null;
	const defaultLabel = startButton.textContent;

	const setStatus = (text, state) => {
		if (statusEl) statusEl.textContent = text;
		startButton.classList.remove("success", "error");
		if (state) startButton.classList.add(state);
	};

	const resetConfirm = () => {
		confirmPending = false;
		startButton.textContent = defaultLabel;
		startButton.classList.remove("error");
		if (confirmTimer) {
			clearTimeout(confirmTimer);
			confirmTimer = null;
		}
	};

	const renderMission = (payload) => {
		const run = payload?.run || {};
		const runId = run?.run_id || "--";
		const phase = run?.phase || "IDLE";
		const idx = Number(run?.current_index ?? -1) + 1;
		const total = Number(run?.total_points ?? 0);
		const progress = idx > 0 && total > 0 ? `${idx}/${total}` : "--/--";
		const text = `任务 ${runId} | ${phaseLabel(phase)} | 进度 ${progress}`;
		const state =
			phase === "COMPLETED"
				? "success"
				: phase === "FAILED" || phase === "ABORTED"
					? "error"
					: null;
		setStatus(text, state);
	};

	const pollStatus = () => {
		getJSON("/api/mission/status")
			.then((payload) => {
				renderMission(payload);
			})
			.catch(() => {
				setStatus("任务状态不可用", "error");
			});
	};

	const startStatusPoll = () => {
		if (statusTimer) return;
		pollStatus();
		statusTimer = setInterval(pollStatus, 1000);
	};

	const requestExecute = () => {
		setStatus("正在启动任务...", null);
		postJSON("/api/mission/start", {})
			.then((payload) => {
				renderMission(payload?.mission || {});
				startStatusPoll();
			})
			.catch((error) => {
				setStatus(error?.error || "执行失败", "error");
			})
			.finally(() => {
				resetConfirm();
			});
	};

	startButton.addEventListener("click", () => {
		if (!confirmPending) {
			confirmPending = true;
			startButton.textContent = "确认开始";
			startButton.classList.add("error");
			setStatus("请确认基于当前轨迹启动任务", null);
			confirmTimer = setTimeout(resetConfirm, 3000);
			return;
		}
		requestExecute();
	});

	if (window.io) {
		const socket = window.io("/mission", { transports: ["websocket"] });
		socket.on("mission:update", (payload) => {
			renderMission(payload);
		});
	}

	startStatusPoll();
}
