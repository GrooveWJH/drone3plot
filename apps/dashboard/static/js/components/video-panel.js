export function hydrateVideoPanel(element, streamUrl) {
	if (!element) return;
	const video = element.querySelector("video");
	if (video && streamUrl) {
		video.src = streamUrl;
	}
}
