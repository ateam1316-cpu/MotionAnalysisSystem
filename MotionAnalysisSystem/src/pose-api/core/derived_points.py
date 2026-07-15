"""Derived body points — bilateral center envelope + optional single-side proxy."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from core.side_exclusion import kept_camera_side

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


def _get(landmarks: List[dict], name: str) -> Optional[dict]:
    for lm in landmarks:
        if lm.get("name") == name and lm.get("status") != "missing":
            return lm
    return None


def _min_score(a: dict, b: dict, key: str) -> Optional[float]:
    va = a.get(key)
    vb = b.get(key)
    if va is None or vb is None:
        return None
    return min(float(va), float(vb))


def _coords_from_landmark(lm: dict) -> dict:
    item = {
        "x": lm["x"],
        "y": lm["y"],
        "z": lm.get("z"),
        "pixelX": lm["pixelX"],
        "pixelY": lm["pixelY"],
    }
    if lm.get("visibility") is not None:
        item["visibility"] = lm["visibility"]
    if lm.get("presence") is not None:
        item["presence"] = lm["presence"]
    return item


def _midpoint_coords(a: dict, b: dict) -> dict:
    visibility = _min_score(a, b, "visibility")
    presence = _min_score(a, b, "presence")
    item = {
        "x": (a["x"] + b["x"]) / 2.0,
        "y": (a["y"] + b["y"]) / 2.0,
        "z": (a["z"] + b["z"]) / 2.0 if a.get("z") is not None and b.get("z") is not None else None,
        "pixelX": int(round((a["pixelX"] + b["pixelX"]) / 2.0)),
        "pixelY": int(round((a["pixelY"] + b["pixelY"]) / 2.0)),
        "status": "valid"
        if a.get("status") == "valid" and b.get("status") == "valid"
        else "estimated",
    }
    if visibility is not None:
        item["visibility"] = visibility
    if presence is not None:
        item["presence"] = presence
    return item


def _confidence(lm: dict) -> float:
    vis = float(lm.get("visibility") or 0.0)
    presence = float(lm.get("presence") or 0.0)
    return round(min(vis, presence), 4)


def _unavailable_center() -> dict:
    return {
        "value": None,
        "status": _status("bilateralUnavailable"),
    }


def _bilateral_center(a: Optional[dict], b: Optional[dict], names: List[str]) -> dict:
    if a is None or b is None:
        return _unavailable_center()
    coords = _midpoint_coords(a, b)
    return {
        "value": coords,
        "status": _status("ok"),
        "calculationMode": _mode("bilateralMidpoint"),
        "sourceLandmarks": names,
    }


def _single_side_proxy(lm: Optional[dict], landmark_name: str, source_side: str) -> Optional[dict]:
    if lm is None:
        return None
    coords = _coords_from_landmark(lm)
    return {
        "x": coords["x"],
        "y": coords["y"],
        "z": coords.get("z"),
        "pixelX": coords["pixelX"],
        "pixelY": coords["pixelY"],
        "visibility": coords.get("visibility"),
        "presence": coords.get("presence"),
        "sourceLandmarks": [landmark_name],
        "calculationMode": _mode("singleSideProxy"),
        "sourceSide": source_side,
        "confidence": _confidence(lm),
        "status": lm.get("status", "valid"),
    }


def unwrap_point(point: Optional[dict]) -> Optional[dict]:
    """
    Normalize envelope / proxy / legacy point to a drawable coordinate dict.
    """
    if not point:
        return None
    if isinstance(point.get("value"), dict):
        return point["value"]
    if point.get("x") is not None and point.get("y") is not None:
        return point
    return None


def resolve_effective_point(
    derived: Dict[str, Any],
    center_key: str,
    reference_key: str,
) -> Optional[dict]:
    """Prefer bilateral center value; fall back to single-side reference."""
    center = derived.get(center_key)
    coords = unwrap_point(center) if isinstance(center, dict) else None
    if coords is not None:
        return coords
    ref = derived.get(reference_key)
    return unwrap_point(ref) if isinstance(ref, dict) else None


def compute_derived_points(
    landmarks: List[dict],
    *,
    exclude_side: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Always emit envelope centers. On pure side views (exclude_side set), bilateral
    centers are unavailable and single-side *Reference proxies are added.
    """
    result: Dict[str, Any] = {}

    left_shoulder = _get(landmarks, "LEFT_SHOULDER")
    right_shoulder = _get(landmarks, "RIGHT_SHOULDER")
    left_hip = _get(landmarks, "LEFT_HIP")
    right_hip = _get(landmarks, "RIGHT_HIP")
    left_heel = _get(landmarks, "LEFT_HEEL")
    left_foot = _get(landmarks, "LEFT_FOOT_INDEX")
    right_heel = _get(landmarks, "RIGHT_HEEL")
    right_foot = _get(landmarks, "RIGHT_FOOT_INDEX")

    keep = kept_camera_side(exclude_side)

    if exclude_side:
        result["shoulderCenter"] = _unavailable_center()
        result["hipCenter"] = _unavailable_center()
        result["bodyCenter"] = _unavailable_center()

        if keep == "left":
            result["shoulderReference"] = _single_side_proxy(
                left_shoulder, "LEFT_SHOULDER", "left"
            )
            result["hipReference"] = _single_side_proxy(left_hip, "LEFT_HIP", "left")
        elif keep == "right":
            result["shoulderReference"] = _single_side_proxy(
                right_shoulder, "RIGHT_SHOULDER", "right"
            )
            result["hipReference"] = _single_side_proxy(right_hip, "RIGHT_HIP", "right")

        # Drop None references
        for key in ("shoulderReference", "hipReference"):
            if result.get(key) is None:
                result.pop(key, None)

        sh_ref = result.get("shoulderReference")
        hip_ref = result.get("hipReference")
        if sh_ref and hip_ref:
            mid = _midpoint_coords(sh_ref, hip_ref)
            result["bodyReference"] = {
                **{k: mid[k] for k in ("x", "y", "z", "pixelX", "pixelY") if k in mid},
                "visibility": mid.get("visibility"),
                "presence": mid.get("presence"),
                "sourceLandmarks": list(
                    (sh_ref.get("sourceLandmarks") or [])
                    + (hip_ref.get("sourceLandmarks") or [])
                ),
                "calculationMode": _mode("singleSideProxy"),
                "sourceSide": keep,
                "confidence": round(
                    min(
                        float(sh_ref.get("confidence") or 0.0),
                        float(hip_ref.get("confidence") or 0.0),
                    ),
                    4,
                ),
                "status": "estimated",
            }
    else:
        result["shoulderCenter"] = _bilateral_center(
            left_shoulder, right_shoulder, ["LEFT_SHOULDER", "RIGHT_SHOULDER"]
        )
        result["hipCenter"] = _bilateral_center(
            left_hip, right_hip, ["LEFT_HIP", "RIGHT_HIP"]
        )
        sh_coords = unwrap_point(result["shoulderCenter"])
        hip_coords = unwrap_point(result["hipCenter"])
        if sh_coords and hip_coords:
            mid = _midpoint_coords(sh_coords, hip_coords)
            result["bodyCenter"] = {
                "value": mid,
                "status": _status("ok"),
                "calculationMode": _mode("bilateralMidpoint"),
                "sourceLandmarks": [
                    "LEFT_SHOULDER",
                    "RIGHT_SHOULDER",
                    "LEFT_HIP",
                    "RIGHT_HIP",
                ],
            }
        else:
            result["bodyCenter"] = _unavailable_center()

    # Foot centers (side-specific; omitted for excluded side by landmark absence)
    if left_heel and left_foot:
        result["leftFootCenter"] = {
            "value": _midpoint_coords(left_heel, left_foot),
            "status": _status("ok"),
            "calculationMode": _mode("bilateralMidpoint"),
            "sourceLandmarks": ["LEFT_HEEL", "LEFT_FOOT_INDEX"],
        }
    elif left_foot:
        result["leftFootCenter"] = {
            "value": _coords_from_landmark(left_foot),
            "status": _status("ok"),
            "calculationMode": _mode("singleSideProxy"),
            "sourceLandmarks": ["LEFT_FOOT_INDEX"],
            "sourceSide": "left",
        }

    if right_heel and right_foot:
        result["rightFootCenter"] = {
            "value": _midpoint_coords(right_heel, right_foot),
            "status": _status("ok"),
            "calculationMode": _mode("bilateralMidpoint"),
            "sourceLandmarks": ["RIGHT_HEEL", "RIGHT_FOOT_INDEX"],
        }
    elif right_foot:
        result["rightFootCenter"] = {
            "value": _coords_from_landmark(right_foot),
            "status": _status("ok"),
            "calculationMode": _mode("singleSideProxy"),
            "sourceLandmarks": ["RIGHT_FOOT_INDEX"],
            "sourceSide": "right",
        }

    return result
