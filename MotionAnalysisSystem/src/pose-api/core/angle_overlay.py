"""Angle overlay specs for skeleton video — anchors and short labels."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.derived_points import resolve_effective_point, unwrap_point
from core.render_thresholds import is_drawable

# Base registry angle key → landmark name or derived center key.
ANGLE_ANCHORS: Dict[str, str] = {
    "leftElbowAngleDeg": "LEFT_ELBOW",
    "rightElbowAngleDeg": "RIGHT_ELBOW",
    "leftShoulderAngleDeg": "LEFT_SHOULDER",
    "rightShoulderAngleDeg": "RIGHT_SHOULDER",
    "leftHipAngleDeg": "LEFT_HIP",
    "rightHipAngleDeg": "RIGHT_HIP",
    "leftKneeAngleDeg": "LEFT_KNEE",
    "rightKneeAngleDeg": "RIGHT_KNEE",
    "leftAnkleAngleDeg": "LEFT_ANKLE",
    "rightAnkleAngleDeg": "RIGHT_ANKLE",
    "trunkLeanAngleDeg": "bodyCenter",
    "shoulderTiltAngleDeg": "shoulderCenter",
    "pelvisTiltAngleDeg": "hipCenter",
}

_CENTER_TO_REFERENCE = {
    "bodyCenter": "bodyReference",
    "shoulderCenter": "shoulderReference",
    "hipCenter": "hipReference",
}

_SHORT_LABELS: Dict[str, str] = {
    "leftElbowAngleDeg": "L-Elbow",
    "rightElbowAngleDeg": "R-Elbow",
    "leftShoulderAngleDeg": "L-Shoulder",
    "rightShoulderAngleDeg": "R-Shoulder",
    "leftHipAngleDeg": "L-Hip",
    "rightHipAngleDeg": "R-Hip",
    "leftKneeAngleDeg": "L-Knee",
    "rightKneeAngleDeg": "R-Knee",
    "leftAnkleAngleDeg": "L-Ankle",
    "rightAnkleAngleDeg": "R-Ankle",
    "trunkLeanAngleDeg": "Trunk",
    "shoulderTiltAngleDeg": "ShoulderTilt",
    "pelvisTiltAngleDeg": "PelvisTilt",
}


def short_label(output_key: str, base_key: str) -> str:
    if base_key in _SHORT_LABELS:
        return _SHORT_LABELS[base_key]
    if output_key.endswith("AngleDeg"):
        return output_key[: -len("AngleDeg")]
    return output_key


def _angle_degrees(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, dict):
        if value.get("value") is None:
            return None
        try:
            return float(value["value"])
        except (TypeError, ValueError):
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _lookup_anchor(
    landmarks: List[dict],
    derived: Dict[str, dict],
    key: str,
) -> Optional[dict]:
    if key in _CENTER_TO_REFERENCE:
        return resolve_effective_point(derived, key, _CENTER_TO_REFERENCE[key])
    if key in derived:
        return unwrap_point(derived[key])
    for lm in landmarks:
        if lm.get("name") == key:
            return lm
    return None


def resolve_angle_overlays(
    joint_angles: dict,
    landmarks: List[dict],
    derived: Dict[str, dict],
    angle_map: Dict[str, str],
) -> List[Tuple[str, float, int, int]]:
    """
    Build drawable angle labels for one frame.

    Returns list of (label_text, degrees, pixel_x, pixel_y).
    """
    overlays: List[Tuple[str, float, int, int]] = []
    if not joint_angles or not angle_map:
        return overlays

    for out_key, base_key in angle_map.items():
        degrees = _angle_degrees(joint_angles.get(out_key))
        if degrees is None:
            continue

        anchor_key = ANGLE_ANCHORS.get(base_key)
        if not anchor_key:
            continue

        point = _lookup_anchor(landmarks, derived, anchor_key)
        if not is_drawable(point):
            continue

        px = int(point.get("pixelX", 0))
        py = int(point.get("pixelY", 0))
        label = f"{short_label(out_key, base_key)} {degrees:.0f}"
        overlays.append((label, degrees, px, py))

    return overlays
