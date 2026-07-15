"""Shared joint angle calculations — numeric only, no quality judgment."""

from __future__ import annotations

import math
from typing import Dict, List, Optional


def _get_lm(landmarks: List[dict], name: str) -> Optional[dict]:
    for lm in landmarks:
        if lm.get("name") == name and lm.get("status") != "missing":
            return lm
    return None


def _angle_deg(a: Optional[dict], b: Optional[dict], c: Optional[dict]) -> Optional[float]:
    """Angle at point b formed by points a-b-c, in degrees."""
    if a is None or b is None or c is None:
        return None

    ab = (a["x"] - b["x"], a["y"] - b["y"])
    cb = (c["x"] - b["x"], c["y"] - b["y"])

    mag_ab = math.hypot(ab[0], ab[1])
    mag_cb = math.hypot(cb[0], cb[1])
    if mag_ab == 0 or mag_cb == 0:
        return None

    cos_value = (ab[0] * cb[0] + ab[1] * cb[1]) / (mag_ab * mag_cb)
    cos_value = max(-1.0, min(1.0, cos_value))
    return round(math.degrees(math.acos(cos_value)), 2)


def _line_tilt_deg(left: Optional[dict], right: Optional[dict]) -> Optional[float]:
    """Tilt of left→right line relative to horizontal, degrees."""
    if left is None or right is None:
        return None
    dx = right["x"] - left["x"]
    dy = right["y"] - left["y"]
    if dx == 0 and dy == 0:
        return None
    return round(math.degrees(math.atan2(dy, dx)), 2)


def _trunk_lean_deg(
    shoulder_center: Optional[dict], hip_center: Optional[dict]
) -> Optional[float]:
    """Trunk lean vs vertical (0 = upright). Positive leans depend on y-down image coords."""
    if shoulder_center is None or hip_center is None:
        return None
    dx = shoulder_center["x"] - hip_center["x"]
    dy = shoulder_center["y"] - hip_center["y"]
    # Vertical in image coords is (0, -1) from hip to shoulder (up)
    mag = math.hypot(dx, dy)
    if mag == 0:
        return None
    # Angle from upward vertical
    # upward vector: (0, -1)
    cos_v = (-dy) / mag
    cos_v = max(-1.0, min(1.0, cos_v))
    lean = math.degrees(math.acos(cos_v))
    # Sign by lateral offset
    if dx < 0:
        lean = -lean
    return round(lean, 2)


class JointAngleCalculator:
    """Computes the full shared angle registry for a frame."""

    def calculate(
        self, landmarks: List[dict], derived_points: Dict[str, dict]
    ) -> Dict[str, Optional[float]]:
        ls = _get_lm(landmarks, "LEFT_SHOULDER")
        rs = _get_lm(landmarks, "RIGHT_SHOULDER")
        le = _get_lm(landmarks, "LEFT_ELBOW")
        re = _get_lm(landmarks, "RIGHT_ELBOW")
        lw = _get_lm(landmarks, "LEFT_WRIST")
        rw = _get_lm(landmarks, "RIGHT_WRIST")
        lh = _get_lm(landmarks, "LEFT_HIP")
        rh = _get_lm(landmarks, "RIGHT_HIP")
        lk = _get_lm(landmarks, "LEFT_KNEE")
        rk = _get_lm(landmarks, "RIGHT_KNEE")
        la = _get_lm(landmarks, "LEFT_ANKLE")
        ra = _get_lm(landmarks, "RIGHT_ANKLE")
        lfi = _get_lm(landmarks, "LEFT_FOOT_INDEX")
        rfi = _get_lm(landmarks, "RIGHT_FOOT_INDEX")

        shoulder_center = derived_points.get("shoulderCenter")
        hip_center = derived_points.get("hipCenter")

        return {
            "leftElbowAngleDeg": _angle_deg(ls, le, lw),
            "rightElbowAngleDeg": _angle_deg(rs, re, rw),
            "leftShoulderAngleDeg": _angle_deg(le, ls, lh),
            "rightShoulderAngleDeg": _angle_deg(re, rs, rh),
            "leftHipAngleDeg": _angle_deg(ls, lh, lk),
            "rightHipAngleDeg": _angle_deg(rs, rh, rk),
            "leftKneeAngleDeg": _angle_deg(lh, lk, la),
            "rightKneeAngleDeg": _angle_deg(rh, rk, ra),
            "leftAnkleAngleDeg": _angle_deg(lk, la, lfi),
            "rightAnkleAngleDeg": _angle_deg(rk, ra, rfi),
            "trunkLeanAngleDeg": _trunk_lean_deg(shoulder_center, hip_center),
            "shoulderTiltAngleDeg": _line_tilt_deg(ls, rs),
            "pelvisTiltAngleDeg": _line_tilt_deg(lh, rh),
        }
