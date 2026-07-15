"""Landmark confidence filtering, status tagging, and temporal smoothing."""

from __future__ import annotations

from typing import Dict, List, Optional, Set

VISIBILITY_VALID = 0.5
PRESENCE_VALID = 0.5
VISIBILITY_LOW = 0.3
SMOOTH_ALPHA = 0.4


class LandmarkFilter:
    def __init__(
        self,
        preferred_landmarks: Optional[Set[str]] = None,
        smooth_alpha: float = SMOOTH_ALPHA,
    ):
        self.preferred_landmarks = preferred_landmarks or set()
        self.smooth_alpha = smooth_alpha
        self._prev_smoothed: Dict[str, dict] = {}

    def apply_status(self, landmarks: List[dict]) -> List[dict]:
        updated = []
        for lm in landmarks:
            visibility = float(lm.get("visibility") or 0.0)
            presence = float(lm.get("presence") or 0.0)
            name = lm.get("name", "")

            if presence < VISIBILITY_LOW and visibility < VISIBILITY_LOW:
                status = "missing"
            elif visibility < VISIBILITY_VALID or presence < PRESENCE_VALID:
                status = "low_visibility"
            else:
                status = "valid"

            # Non-preferred for camera view: keep coordinates but demote valid → low_visibility
            if (
                self.preferred_landmarks
                and name not in self.preferred_landmarks
                and status == "valid"
            ):
                status = "low_visibility"

            item = dict(lm)
            item["status"] = status
            updated.append(item)
        return updated

    def smooth(self, landmarks: List[dict], pose_detected: bool) -> List[dict]:
        """EMA smoothing for valid / low_visibility points; mark gaps as estimated when filled."""
        if not pose_detected or not landmarks:
            self._prev_smoothed = {}
            return landmarks

        smoothed: List[dict] = []
        for lm in landmarks:
            name = lm["name"]
            status = lm.get("status", "valid")
            item = dict(lm)

            if status == "missing":
                prev = self._prev_smoothed.get(name)
                if prev is not None:
                    item["x"] = prev["x"]
                    item["y"] = prev["y"]
                    item["z"] = prev["z"]
                    item["pixelX"] = prev["pixelX"]
                    item["pixelY"] = prev["pixelY"]
                    item["status"] = "estimated"
                    self._prev_smoothed[name] = {
                        "x": item["x"],
                        "y": item["y"],
                        "z": item["z"],
                        "pixelX": item["pixelX"],
                        "pixelY": item["pixelY"],
                    }
                smoothed.append(item)
                continue

            prev = self._prev_smoothed.get(name)
            if prev is None:
                self._prev_smoothed[name] = {
                    "x": item["x"],
                    "y": item["y"],
                    "z": item["z"],
                    "pixelX": item["pixelX"],
                    "pixelY": item["pixelY"],
                }
                smoothed.append(item)
                continue

            a = self.smooth_alpha
            item["x"] = a * item["x"] + (1 - a) * prev["x"]
            item["y"] = a * item["y"] + (1 - a) * prev["y"]
            item["z"] = a * item["z"] + (1 - a) * prev["z"]
            item["pixelX"] = int(round(a * item["pixelX"] + (1 - a) * prev["pixelX"]))
            item["pixelY"] = int(round(a * item["pixelY"] + (1 - a) * prev["pixelY"]))

            self._prev_smoothed[name] = {
                "x": item["x"],
                "y": item["y"],
                "z": item["z"],
                "pixelX": item["pixelX"],
                "pixelY": item["pixelY"],
            }
            smoothed.append(item)

        return smoothed

    def missing_landmarks_frame(self, width: int, height: int) -> List[dict]:
        """Empty landmark list for undetected frames (caller may skip filling all 33)."""
        return []
