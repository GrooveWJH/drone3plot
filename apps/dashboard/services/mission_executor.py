"""Mission executor: dashboard orchestration over control runtime."""

from __future__ import annotations

from collections import deque
import copy
import logging
import threading
import time
import uuid
from typing import Any, cast

from rich.console import Console

from apps.control.core.mission_runner import run_complex_mission
from apps.control.main_takeoff import TakeoffState, _arm_drone, _land, _run_takeoff

from .mission_adapter import (
    ReturnPoint,
    RuntimeHubDataSource,
    RuntimeHubPoseFeed,
    build_snapshot,
    parse_mission_waypoints,
    slam_payload_is_fresh,
    to_control_spec,
)
from .mission_models import MissionPhase, MissionRun, MissionSnapshot


_TERMINAL_PHASES = {
    MissionPhase.IDLE,
    MissionPhase.COMPLETED,
    MissionPhase.FAILED,
    MissionPhase.ABORTED,
}


class MissionAbortRequested(Exception):
    """Raised when operator requested mission abort."""


class MissionExecutor:
    """Single-thread mission state machine and background worker."""

    def __init__(self, runtime_hub: Any, app_config: dict[str, Any], history_size: int = 20):
        self._hub = runtime_hub
        self._config = app_config
        self._logger = logging.getLogger("dashboard")
        self._console = Console()
        self._lock = threading.Lock()
        self._history: deque[dict[str, Any]] = deque(maxlen=history_size)
        self._revision = 0
        self._draft_points: list[dict[str, Any]] = []
        self._draft_meta: dict[str, Any] = {}
        self._active_snapshot: MissionSnapshot | None = None
        self._active_run = MissionRun(run_id="")
        self._worker: threading.Thread | None = None
        self._abort_event = threading.Event()

    def _is_running_locked(self) -> bool:
        phase = self._active_run.phase
        worker_alive = self._worker.is_alive() if self._worker else False
        return phase not in _TERMINAL_PHASES or worker_alive

    def update_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        points_raw = payload.get("points")
        if not isinstance(points_raw, list):
            raise ValueError("points must be a list.")
        # Validate shape early; keep original JSON-serializable dict for replay.
        parse_mission_waypoints(points_raw)
        with self._lock:
            self._revision += 1
            self._draft_points = copy.deepcopy(points_raw)
            self._draft_meta = {
                "trajectory_id": payload.get("trajectory_id") or "current",
                "name": payload.get("name") or "trajectory",
                "updated_at": payload.get("updated_at") or int(time.time() * 1000),
            }
            return {
                "revision": self._revision,
                "points": len(self._draft_points),
                "meta": dict(self._draft_meta),
            }

    def get_draft(self) -> dict[str, Any]:
        with self._lock:
            return {
                "revision": self._revision,
                "points": copy.deepcopy(self._draft_points),
                "meta": dict(self._draft_meta),
            }

    def is_running(self) -> bool:
        with self._lock:
            return self._is_running_locked()

    def start(self, payload: dict[str, Any] | None = None) -> str:
        payload = payload or {}
        self._validate_runtime_ready()
        with self._lock:
            if self._is_running_locked():
                raise RuntimeError("Mission already running.")
            points_raw = payload.get("points")
            if points_raw is None:
                points_raw = copy.deepcopy(self._draft_points)
            if not isinstance(points_raw, list) or len(points_raw) == 0:
                raise ValueError("No mission waypoints available.")

            points = parse_mission_waypoints(points_raw)
            self._revision += 1
            run_id = uuid.uuid4().hex[:12]
            return_point = self._resolve_return_point(payload)
            snapshot = build_snapshot(
                run_id=run_id,
                revision=self._revision,
                points=points,
                options={
                    "return_point": {
                        "x": return_point.x,
                        "y": return_point.y,
                        "z": return_point.z,
                        "yaw": return_point.yaw,
                        "takePhoto": return_point.take_photo,
                    }
                },
            )

            self._abort_event.clear()
            self._active_snapshot = snapshot
            self._active_run = MissionRun(run_id=run_id)
            self._active_run.start(
                total_points=len(snapshot.points) + 1,
                snapshot_revision=snapshot.revision,
            )

            self._worker = threading.Thread(
                target=self._run_worker,
                args=(snapshot, return_point),
                name=f"mission-executor-{run_id}",
                daemon=True,
            )
            self._worker.start()
            return run_id

    def abort(self) -> None:
        with self._lock:
            if not self._is_running_locked():
                return
            self._active_run.phase = MissionPhase.ABORTING
            self._active_run.aborted = True
        self._abort_event.set()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "run": self._active_run.to_dict(),
                "snapshot": self._active_snapshot.to_dict() if self._active_snapshot else None,
                "draft": {
                    "revision": self._revision,
                    "points": len(self._draft_points),
                    "meta": dict(self._draft_meta),
                },
            }

    def history(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._history)

    def shutdown(self) -> None:
        self.abort()
        worker = None
        with self._lock:
            worker = self._worker
        if worker and worker.is_alive():
            worker.join(timeout=6.0)

    def _resolve_return_point(self, payload: dict[str, Any]) -> ReturnPoint:
        raw = payload.get("return_point")
        if not isinstance(raw, dict):
            return ReturnPoint()
        try:
            return ReturnPoint(
                x=float(raw.get("x", 0.0)),
                y=float(raw.get("y", 0.0)),
                z=float(raw.get("z", 1.0)),
                yaw=float(raw.get("yaw", 0.0)),
                take_photo=bool(raw.get("takePhoto", False)),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid return_point payload.") from exc

    def _run_worker(self, snapshot: MissionSnapshot, return_point: ReturnPoint) -> None:
        run_id = snapshot.run_id
        state = TakeoffState()
        mqtt = None
        try:
            self._set_phase(run_id, MissionPhase.VALIDATING)
            self._validate_runtime_ready()
            self._raise_if_abort_requested()

            mqtt = self._hub.drone.mqtt_client
            if mqtt is None:
                raise RuntimeError("Drone MQTT client unavailable.")

            pose_feed = RuntimeHubPoseFeed(self._hub)
            datasource = RuntimeHubDataSource(self._hub)
            spec = to_control_spec(snapshot, return_point)

            self._set_phase(run_id, MissionPhase.ARMING)
            _arm_drone(mqtt, self._console)
            self._raise_if_abort_requested()

            self._set_phase(run_id, MissionPhase.TAKING_OFF)
            ok = _run_takeoff(
                mqtt,
                self._console,
                state,
                cast(Any, pose_feed),
                auto_land_on_fail=False,
            )
            if not ok:
                raise RuntimeError("Takeoff failed.")
            self._raise_if_abort_requested()

            self._set_phase(run_id, MissionPhase.ALIGNING_TO_FIRST)
            self._set_phase(run_id, MissionPhase.RUNNING_WAYPOINTS)
            run_complex_mission(
                mqtt=mqtt,
                datasource=datasource,
                console=self._console,
                spec=spec,
                should_abort=self._abort_requested,
                on_progress=lambda idx, total: self._set_progress(
                    run_id, idx, total
                ),
            )
            self._raise_if_abort_requested()

            self._set_phase(run_id, MissionPhase.RETURNING_HOME)
            self._set_phase(run_id, MissionPhase.LANDING)
            _land(mqtt, self._console, state, cast(Any, pose_feed))
            self._set_phase(run_id, MissionPhase.COMPLETED)
        except MissionAbortRequested:
            self._handle_abort(run_id, mqtt, state)
        except Exception as exc:  # noqa: BLE001
            if self._abort_requested() or str(exc) == "Mission aborted by operator.":
                self._handle_abort(run_id, mqtt, state)
                return
            self._logger.exception("[mission] run failed")
            with self._lock:
                if self._active_run.run_id == run_id:
                    self._active_run.error = str(exc)
            try:
                if mqtt is not None:
                    self._set_phase(run_id, MissionPhase.LANDING)
                    _land(
                        mqtt,
                        self._console,
                        state,
                        cast(Any, RuntimeHubPoseFeed(self._hub)),
                    )
            except Exception as landing_exc:  # noqa: BLE001
                self._logger.warning("[mission] failure landing failed: %s", landing_exc)
            self._set_phase(run_id, MissionPhase.FAILED)
        finally:
            with self._lock:
                if self._active_run.run_id == run_id:
                    record = {
                        "run": self._active_run.to_dict(),
                        "snapshot": self._active_snapshot.to_dict()
                        if self._active_snapshot
                        else None,
                    }
                    self._history.appendleft(record)
                    self._worker = None

    def _validate_runtime_ready(self) -> None:
        if not self._hub.slam.connected or not self._hub.slam.pose:
            raise RuntimeError("SLAM runtime is not connected.")
        pose_payload = self._hub.slam.pose.latest()
        if not slam_payload_is_fresh(pose_payload):
            raise RuntimeError("SLAM pose is stale.")

        drone_status = self._hub.drone.status()
        if not drone_status.connected:
            raise RuntimeError("Drone runtime is disconnected.")
        if drone_status.drc_state != "drc_ready":
            raise RuntimeError("DRC is not ready. Please connect and authorize first.")

    def _abort_requested(self) -> bool:
        return self._abort_event.is_set()

    def _raise_if_abort_requested(self) -> None:
        if self._abort_requested():
            raise MissionAbortRequested

    def _set_phase(self, run_id: str, phase: MissionPhase) -> None:
        with self._lock:
            if self._active_run.run_id != run_id:
                return
            self._active_run.phase = phase
            if phase in {MissionPhase.COMPLETED, MissionPhase.FAILED, MissionPhase.ABORTED}:
                self._active_run.finish(phase)

    def _set_progress(self, run_id: str, current_index: int, total_points: int) -> None:
        with self._lock:
            if self._active_run.run_id != run_id:
                return
            self._active_run.current_index = current_index
            if total_points > 0:
                self._active_run.total_points = total_points

    def _handle_abort(self, run_id: str, mqtt: Any, state: TakeoffState) -> None:
        self._set_phase(run_id, MissionPhase.ABORTING)
        try:
            if mqtt is not None:
                self._set_phase(run_id, MissionPhase.LANDING)
                _land(
                    mqtt,
                    self._console,
                    state,
                    cast(Any, RuntimeHubPoseFeed(self._hub)),
                )
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("[mission] abort landing failed: %s", exc)
        self._set_phase(run_id, MissionPhase.ABORTED)
