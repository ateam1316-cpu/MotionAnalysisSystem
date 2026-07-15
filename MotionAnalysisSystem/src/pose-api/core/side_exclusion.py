"""Pure side-view body-side exclusion (side_left / side_right only)."""

from __future__ import annotations

import json
import os
from typing import List, Optional

CONFIGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs")
CAMERA_VIEWS_PATH = os.path.join(CONFIGS_DIR, "camera_views.json")

# Camera-facing body side for pure side views.
# side_left  = subject left side toward camera → keep LEFT, exclude RIGHT
# side_right = subject right side toward camera → keep RIGHT, exclude LEFT
_VIEW_EXCLUDE_SIDE = {
    "side_left": "right",
    "side_right": "left",
}

_LEFT_LANDMARK_PREFIX = "LEFT_"
_RIGHT_LANDMARK_PREFIX = "RIGHT_"

_LEFT_ANGLE_KEYS = {
    "leftElbowAngleDeg",
    "leftShoulderAngleDeg",
    "leftHipAngleDeg",
    "leftKneeAngleDeg",
    "leftAnkleAngleDeg",
}
_RIGHT_ANGLE_KEYS = {
    "rightElbowAngleDeg",
    "rightShoulderAngleDeg",
    "rightHipAngleDeg",
    "rightKneeAngleDeg",
    "rightAnkleAngleDeg",
}

_LEFT_DERIVED = {"leftFootCenter"}
_RIGHT_DERIVED = {"rightFootCenter"}


def _load_camera_views() -> dict:
    if not os.path.exists(CAMERA_VIEWS_PATH):
        return {}
    with open(CAMERA_VIEWS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def exclude_body_side_for_view(camera_view: str) -> Optional[str]:
    """
    Returns 'left' or 'right' when the view is pure side_left/side_right.
    Prefers explicit excludeBodySide in JSON; falls back to built-in map.
    """
    view_key = (camera_view or "unknown").strip().lower()
    views = _load_camera_views()
    cfg = views.get(view_key) or {}
    explicit = cfg.get("excludeBodySide")
    if explicit in ("left", "right"):
        return explicit
    return _VIEW_EXCLUDE_SIDE.get(view_key)


def landmark_body_side(name: str) -> Optional[str]:
    if not name:
        return None
    if name.startswith(_LEFT_LANDMARK_PREFIX):
        return "left"
    if name.startswith(_RIGHT_LANDMARK_PREFIX):
        return "right"
    return None


def is_landmark_excluded(name: str, exclude_side: Optional[str]) -> bool:
    if not exclude_side:
        return False
    return landmark_body_side(name) == exclude_side


def filter_landmarks(
    landmarks: List[dict], exclude_side: Optional[str]
) -> List[dict]:
    if not exclude_side:
        return landmarks
    return [
        lm for lm in landmarks if not is_landmark_excluded(lm.get("name", ""), exclude_side)
    ]


def is_angle_key_excluded(base_key: str, exclude_side: Optional[str]) -> bool:
    if not exclude_side:
        return False
    if exclude_side == "left":
        return base_key in _LEFT_ANGLE_KEYS
    if exclude_side == "right":
        return base_key in _RIGHT_ANGLE_KEYS
    return False


def is_derived_key_excluded(key: str, exclude_side: Optional[str]) -> bool:
    if not exclude_side:
        return False
    if exclude_side == "left":
        return key in _LEFT_DERIVED
    if exclude_side == "right":
        return key in _RIGHT_DERIVED
    return False


def is_resolved_traj_excluded(resolved_key: str, exclude_side: Optional[str]) -> bool:
    """True when a trajectory lookup key belongs to the excluded body side."""
    if not exclude_side:
        return False
    if is_landmark_excluded(resolved_key, exclude_side):
        return True
    return is_derived_key_excluded(resolved_key, exclude_side)


def kept_camera_side(exclude_side: Optional[str]) -> Optional[str]:
    if exclude_side == "left":
        return "right"
    if exclude_side == "right":
        return "left"
    return None
