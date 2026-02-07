import { postJSON } from "../utils/http.js";

export function initPhotoButton() {
	const button = document.querySelector("[data-photo-take]");
	if (!button) return;

	const defaultLabel = button.textContent;
	let resetTimer = null;

	const resetState = () => {
		button.classList.remove("success", "error");
		button.textContent = defaultLabel;
		button.disabled = false;
	};

	const showState = (state, label) => {
		if (resetTimer) {
			clearTimeout(resetTimer);
			resetTimer = null;
		}
		button.classList.remove("success", "error");
		if (state) {
			button.classList.add(state);
		}
		button.textContent = label;
		button.disabled = true;
		resetTimer = setTimeout(resetState, 2000);
	};

	button.addEventListener("click", () => {
		button.disabled = true;
		button.textContent = "等待拍照结果...";
		postJSON("/api/camera/photo", { timeout: 10 })
			.then((payload) => {
				const ok =
					payload?.result?.ok === true || payload?.result?.result === 0;
				showState(ok ? "success" : "error", ok ? "拍照成功" : "拍照失败");
			})
			.catch(() => {
				showState("error", "拍照失败");
			});
	});
}
