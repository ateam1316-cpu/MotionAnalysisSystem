"""Shared joint angle calculations with provenance envelopes."""

from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, List, Optional

from core.derived_points import resolve_effective_point, unwrap_point

CONFIGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs")
VALIDITY_PATH = os.path.join(CONFIGS_DIR, "measurement_validity.json")

_validity_cache: Optional[dict] = None


def _validity() -> dict:
    global _validity_cache
    if _validity_cache is None:
        with open(VALIDITY_PATH, "r", encoding="utf-8") as f:
            _validity_cache = json.load(f)
    return _validity_cache


def _status(key: str) -> str:
    return _validity()["statuses"][key]


def _mode(key: str) -> str:
    return _validity()["calculationModes"][key]


def _validity_for_mode(mode: str) -> dict:
    block = _validity()["validityByMode"].get(mode) or {}
    return {
        "validFor": list(block.get("validFor") or []),
        "notValidFor": list(block.get("notValidFor") or []),
    }


def _get_lm(landmarks: List[dict], name: str) -> Optional[dict]:
    for lm in landmarks:
        if lm.get("name") == name and lm.get("status") != "missing":
            return lm
    return None


def _angle_deg(a: Optional[dict], b: Optional[dict], c: Optional[dict]) -> Optional[float]:
    """Angle at point b formed by points a-b-c, in degrees."""
    if a is None or b is None or c is None:
        return None
    if a.get("x") is None or b.get("x") is None or c.get("x") is None:
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
    if left.get("x") is None or right.get("x") is None:
        return None
    dx = right["x"] - left["x"]
    dy = right["y"] - left["y"]
    if dx == 0 and dy == 0:
        return None
    return round(math.degrees(math.atan2(dy, dx)), 2)


def _trunk_lean_deg(shoulder: Optional[dict], hip: Optional[dict]) -> Optional[float]:
    """Trunk lean vs vertical (0 = upright)."""
    if shoulder is None or hip is None:
        return None
    if shoulder.get("x") is None or hip.get("x") is None:
        return None
    dx = shoulder["x"] - hip["x"]
    dy = shoulder["y"] - hip["y"]
    mag = math.hypot(dx, dy)
    if mag == 0:
        return None
    cos_v = (-dy) / mag
    cos_v = max(-1.0, min(1.0, cos_v))
    lean = math.degrees(math.acos(cos_v))
    if dx < 0:
        lean = -lean
    return round(lean, 2)


def _envelope(
    *,
    value: Optional[float],
    calculation_mode: str,
    source_landmarks: List[str],
    source_side: Optional[str] = None,
    is_estimated: bool = False,
    status: Optional[str] = None,
) -> dict:
    payload: Dict[str, Any] = {
        "value": value,
        "unit": "degree",
        "calculationMode": calculation_mode,
        "sourceLandmarks": source_landmarks,
        "isEstimated": is_estimated,
        "status": status
        or (_status("ok") if value is not None else _status("landmarksUnavailable")),
        **_validity_for_mode(calculation_mode),
    }
    if source_side is not None:
        payload["sourceSide"] = source_side
    return payload


def _triple_envelope(
    a: Optional[dict],
    b: Optional[dict],
    c: Optional[dict],
    names: List[str],
    source_side: Optional[str] = None,
) -> dict:
    value = _angle_deg(a, b, c)
    return _envelope(
        value=value,
        calculation_mode=_mode("landmarkTriple2d"),
        source_landmarks=names,
        source_side=source_side,
        is_estimated=False,
    )


class JointAngleCalculator:
    """Computes the full shared angle registry as provenance envelopes."""

    def calculate(
        self,
        landmarks: List[dict],
        derived_points: Dict[str, Any],
        *,
        exclude_side: Optional[str] = None,
    ) -> Dict[str, dict]:
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

        angles: Dict[str, dict] = {
            "leftElbowAngleDeg": _triple_envelope(
                ls, le, lw, ["LEFT_SHOULDER", "LEFT_ELBOW", "LEFT_WRIST"], "left"
            ),
            "rightElbowAngleDeg": _triple_envelope(
                rs, re, rw, ["RIGHT_SHOULDER", "RIGHT_ELBOW", "RIGHT_WRIST"], "right"
            ),
            "leftShoulderAngleDeg": _triple_envelope(
                le, ls, lh, ["LEFT_ELBOW", "LEFT_SHOULDER", "LEFT_HIP"], "left"
            ),
            "rightShoulderAngleDeg": _triple_envelope(
                re, rs, rh, ["RIGHT_ELBOW", "RIGHT_SHOULDER", "RIGHT_HIP"], "right"
            ),
            "leftHipAngleDeg": _triple_envelope(
                ls, lh, lk, ["LEFT_SHOULDER", "LEFT_HIP", "LEFT_KNEE"], "left"
            ),
            "rightHipAngleDeg": _triple_envelope(
                rs, rh, rk, ["RIGHT_SHOULDER", "RIGHT_HIP", "RIGHT_KNEE"], "right"
            ),
            "leftKneeAngleDeg": _triple_envelope(
                lh, lk, la, ["LEFT_HIP", "LEFT_KNEE", "LEFT_ANKLE"], "left"
            ),
            "rightKneeAngleDeg": _triple_envelope(
                rh, rk, ra, ["RIGHT_HIP", "RIGHT_KNEE", "RIGHT_ANKLE"], "right"
            ),
            "leftAnkleAngleDeg": _triple_envelope(
                lk, la, lfi, ["LEFT_KNEE", "LEFT_ANKLE", "LEFT_FOOT_INDEX"], "left"
            ),
            "rightAnkleAngleDeg": _triple_envelope(
                rk, ra, rfi, ["RIGHT_KNEE", "RIGHT_ANKLE", "RIGHT_FOOT_INDEX"], "right"
            ),
        }

        # Trunk lean: bilateral centers, or single-side references on pure side view.
        if exclude_side:
            shoulder = resolve_effective_point(
                derived_points, "shoulderCenter", "shoulderReference"
            )
            hip = resolve_effective_point(derived_points, "hipCenter", "hipReference")
            lean = _trunk_lean_deg(shoulder, hip)
            sh_ref = derived_points.get("shoulderReference") or {}
            hip_ref = derived_points.get("hipReference") or {}
            source_side = sh_ref.get("sourceSide") or hip_ref.get("sourceSide")
            source_lms = list(
                (sh_ref.get("sourceLandmarks") or [])
                + (hip_ref.get("sourceLandmarks") or [])
            )
            angles["trunkLeanAngleDeg"] = _envelope(
                value=lean,
                calculation_mode=_mode("singleSide2d"),
                source_landmarks=source_lms or ["shoulderReference", "hipReference"],
                source_side=source_side,
                is_estimated=True,
                status=_status("ok") if lean is not None else _status("landmarksUnavailable"),
            )
            # Tilt requires both sides — do not estimate on pure side views.
            unavailable = {
                "value": None,
                "unit": "degree",
                "calculationMode": _mode("bilateralLineTilt2d"),
                "sourceLandmarks": [],
                "isEstimated": False,
                "status": _status("bilateralUnavailable"),
                **_validity_for_mode(_mode("bilateralLineTilt2d")),
            }
            angles["shoulderTiltAngleDeg"] = dict(unavailable)
            angles["pelvisTiltAngleDeg"] = dict(unavailable)
        else:
            shoulder = unwrap_point(derived_points.get("shoulderCenter"))
            hip = unwrap_point(derived_points.get("hipCenter"))
            lean = _trunk_lean_deg(shoulder, hip)
            angles["trunkLeanAngleDeg"] = _envelope(
                value=lean,
                calculation_mode=_mode("bilateral2d"),
                source_landmarks=["LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_HIP", "RIGHT_HIP"],
                is_estimated=False,
            )
            shoulder_tilt = _line_tilt_deg(ls, rs)
            pelvis_tilt = _line_tilt_deg(lh, rh)
            angles["shoulderTiltAngleDeg"] = _envelope(
                value=shoulder_tilt,
                calculation_mode=_mode("bilateralLineTilt2d"),
                source_landmarks=["LEFT_SHOULDER", "RIGHT_SHOULDER"],
                is_estimated=False,
            )
            angles["pelvisTiltAngleDeg"] = _envelope(
                value=pelvis_tilt,
                calculation_mode=_mode("bilateralLineTilt2d"),
                source_landmarks=["LEFT_HIP", "RIGHT_HIP"],
                is_estimated=False,
            )

        return angles
