export function postJSON(url, body) {
	return fetch(url, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body),
	}).then((resp) => {
		if (!resp.ok) {
			return resp.json().then((payload) => Promise.reject(payload));
		}
		return resp.json();
	});
}

export function getJSON(url) {
	return fetch(url).then((resp) => {
		if (!resp.ok) {
			return resp.json().then((payload) => Promise.reject(payload));
		}
		return resp.json();
	});
}
