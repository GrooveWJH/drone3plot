"""Live streaming helpers."""
from __future__ import annotations

from typing import Optional

from pydjimqtt.core.mqtt_client import MQTTClient
from pydjimqtt.core.service_caller import ServiceCaller
from pydjimqtt.live_utils import set_live_quality, start_live, stop_live


class StreamingService:
    """Wrap `pydjimqtt.live_utils` helpers and remember the current video id."""

    def __init__(
        self,
        caller: ServiceCaller,
        client: MQTTClient,
        default_video_index: str,
        default_quality: int,
    ) -> None:
        self.caller = caller
        self.client = client
        self.default_video_index = default_video_index
        self.default_quality = default_quality
        self._video_id: Optional[str] = None

    @property
    def video_id(self) -> Optional[str]:
        return self._video_id

    def start(self, rtmp_url: str, video_index: str | None = None, quality: int | None = None) -> Optional[str]:
        video_id = start_live(
            self.caller,
            self.client,
            rtmp_url,
            video_index=video_index or self.default_video_index,
            video_quality=quality if quality is not None else self.default_quality,
        )
        if video_id:
            self._video_id = video_id
        return self._video_id

    def stop(self) -> bool:
        if not self._video_id:
            return False
        success = stop_live(self.caller, self._video_id)
        if success:
            self._video_id = None
        return success

    def change_quality(self, quality: int) -> bool:
        if not self._video_id:
            raise RuntimeError("Cannot change quality before streaming starts")
        return set_live_quality(self.caller, self._video_id, video_quality=quality)
