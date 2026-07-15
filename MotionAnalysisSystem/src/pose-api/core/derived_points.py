"""Derived body center points from landmarks."""

from __future__ import annotations

from typing import Dict, List, Optional


def _get(landmarks: List[dict], name: str) -> Optional[dict]:
    for lm in landmarks:
        if lm.get("name") == name and lm.get("status") != "missing":
            return lm
    return None


def _midpoint(a: dict, b: dict, name: str) -> dict:
    return {
        "name": name,
        "x": (a["x"] + b["x"]) / 2.0,
        "y": (a["y"] + b["y"]) / 2.0,
        "z": (a["z"] + b["z"]) / 2.0,
        "pixelX": int(round((a["pixelX"] + b["pixelX"]) / 2.0)),
        "pixelY": int(round((a["pixelY"] + b["pixelY"]) / 2.0)),
        "status": "valid"
        if a.get("status") == "valid" and b.get("status") == "valid"
        else "estimated",
    }


def compute_derived_points(landmarks: List[dict]) -> Dict[str, dict]:
    result: Dict[str, dict] = {}

    left_shoulder = _get(landmarks, "LEFT_SHOULDER")
    right_shoulder = _get(landmarks, "RIGHT_SHOULDER")
    left_hip = _get(landmarks, "LEFT_HIP")
    right_hip = _get(landmarks, "RIGHT_HIP")
    left_heel = _get(landmarks, "LEFT_HEEL")
    left_foot = _get(landmarks, "LEFT_FOOT_INDEX")
    right_heel = _get(landmarks, "RIGHT_HEEL")
    right_foot = _get(landmarks, "RIGHT_FOOT_INDEX")

    if left_shoulder and right_shoulder:
        result["shoulderCenter"] = _midpoint(
            left_shoulder, right_shoulder, "shoulderCenter"
        )

    if left_hip and right_hip:
        result["hipCenter"] = _midpoint(left_hip, right_hip, "hipCenter")

    if "shoulderCenter" in result and "hipCenter" in result:
        result["bodyCenter"] = _midpoint(
            result["shoulderCenter"], result["hipCenter"], "bodyCenter"
        )

    if left_heel and left_foot:
        result["leftFootCenter"] = _midpoint(left_heel, left_foot, "leftFootCenter")
    elif left_foot:
        result["leftFootCenter"] = {
            "name": "leftFootCenter",
            "x": left_foot["x"],
            "y": left_foot["y"],
            "z": left_foot["z"],
            "pixelX": left_foot["pixelX"],
            "pixelY": left_foot["pixelY"],
            "status": left_foot.get("status", "valid"),
        }

    if right_heel and right_foot:
        result["rightFootCenter"] = _midpoint(right_heel, right_foot, "rightFootCenter")
    elif right_foot:
        result["rightFootCenter"] = {
            "name": "rightFootCenter",
            "x": right_foot["x"],
            "y": right_foot["y"],
            "z": right_foot["z"],
            "pixelX": right_foot["pixelX"],
            "pixelY": right_foot["pixelY"],
            "status": right_foot.get("status", "valid"),
        }

    return result
