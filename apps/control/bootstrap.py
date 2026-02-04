"""Runtime bootstrap helpers for control scripts."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_project_path() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    return project_root


def ensure_pydjimqtt() -> None:
    project_root = ensure_project_path()
    sdk_root = project_root / "thirdparty" / "pydjimqtt" / "src"
    if str(sdk_root) not in sys.path:
        sys.path.insert(0, str(sdk_root))
