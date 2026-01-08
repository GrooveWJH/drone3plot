from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DrcState(str, Enum):
    IDLE = "idle"
    DISCONNECTED = "disconnected"
    WAITING = "waiting_for_user"
    READY = "drc_ready"
    ERROR = "error"


class DrcEvent(str, Enum):
    REQUESTED = "requested"
    REQUEST_FAILED = "request_failed"
    CONFIRMED = "confirmed"
    CONFIRM_FAILED = "confirm_failed"
    OFFLINE = "offline"
    RESET = "reset"


@dataclass(frozen=True)
class DrcTransition:
    source: DrcState
    event: DrcEvent
    target: DrcState


TRANSITIONS = {
    (DrcState.IDLE, DrcEvent.REQUESTED): DrcState.WAITING,
    (DrcState.IDLE, DrcEvent.REQUEST_FAILED): DrcState.ERROR,
    (DrcState.IDLE, DrcEvent.OFFLINE): DrcState.DISCONNECTED,
    (DrcState.IDLE, DrcEvent.RESET): DrcState.IDLE,
    (DrcState.DISCONNECTED, DrcEvent.REQUESTED): DrcState.WAITING,
    (DrcState.DISCONNECTED, DrcEvent.RESET): DrcState.IDLE,
    (DrcState.WAITING, DrcEvent.CONFIRMED): DrcState.READY,
    (DrcState.WAITING, DrcEvent.CONFIRM_FAILED): DrcState.ERROR,
    (DrcState.WAITING, DrcEvent.OFFLINE): DrcState.DISCONNECTED,
    (DrcState.READY, DrcEvent.OFFLINE): DrcState.DISCONNECTED,
    (DrcState.READY, DrcEvent.RESET): DrcState.IDLE,
    (DrcState.ERROR, DrcEvent.REQUESTED): DrcState.WAITING,
    (DrcState.ERROR, DrcEvent.RESET): DrcState.IDLE,
}

