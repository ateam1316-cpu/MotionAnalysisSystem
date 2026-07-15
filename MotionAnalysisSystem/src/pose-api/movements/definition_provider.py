"""Load movement definitions and resolve dominant-side aliases."""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Set, Tuple

CONFIGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs")
MOVEMENTS_DIR = os.path.join(CONFIGS_DIR, "movements")
CAMERA_VIEWS_PATH = os.path.join(CONFIGS_DIR, "camera_views.json")

# Semantic aliases → MediaPipe landmark name template
_SIDE_LANDMARK_ALIASES = {
    "racketSideWrist": "{side}_WRIST",
    "racketSideElbow": "{side}_ELBOW",
    "racketSideShoulder": "{side}_SHOULDER",
    "throwingWrist": "{side}_WRIST",
    "throwingElbow": "{side}_ELBOW",
    "throwingShoulder": "{side}_SHOULDER",
    "servingWrist": "{side}_WRIST",
    "servingElbow": "{side}_ELBOW",
    "servingShoulder": "{side}_SHOULDER",
    "nonServingWrist": "{other}_WRIST",
    "dominantWrist": "{side}_WRIST",
    "dominantElbow": "{side}_ELBOW",
    "dominantShoulder": "{side}_SHOULDER",
    "leadAnkle": "{other}_ANKLE",
    "leadKnee": "{other}_KNEE",
    "trailAnkle": "{side}_ANKLE",
    "trailKnee": "{side}_KNEE",
    "leftKnee": "LEFT_KNEE",
    "rightKnee": "RIGHT_KNEE",
    "leftAnkle": "LEFT_ANKLE",
    "rightAnkle": "RIGHT_ANKLE",
    "leftWrist": "LEFT_WRIST",
    "rightWrist": "RIGHT_WRIST",
    "leftElbow": "LEFT_ELBOW",
    "rightElbow": "RIGHT_ELBOW",
    "hipCenter": "hipCenter",
    "shoulderCenter": "shoulderCenter",
    "bodyCenter": "bodyCenter",
}

# Output Position/Height keys → semantic landmark alias (before side resolve)
_POSITION_OUTPUT_ALIASES = {
    "racketSideWristPosition": "racketSideWrist",
    "throwingWristPosition": "throwingWrist",
    "dominantWristPosition": "dominantWrist",
    "servingWristPosition": "servingWrist",
    "servingWristHeightNormalized": "servingWrist",
    "shoulderCenterPosition": "shoulderCenter",
    "hipCenterPosition": "hipCenter",
}

# Semantic angle → base registry angle key
_SIDE_ANGLE_ALIASES = {
    "racketSideShoulderAngleDeg": "{side}ShoulderAngleDeg",
    "racketSideElbowAngleDeg": "{side}ElbowAngleDeg",
    "throwingShoulderAngleDeg": "{side}ShoulderAngleDeg",
    "throwingElbowAngleDeg": "{side}ElbowAngleDeg",
    "servingShoulderAngleDeg": "{side}ShoulderAngleDeg",
    "servingElbowAngleDeg": "{side}ElbowAngleDeg",
    "dominantShoulderAngleDeg": "{side}ShoulderAngleDeg",
    "dominantElbowAngleDeg": "{side}ElbowAngleDeg",
    "leadKneeAngleDeg": "{other}KneeAngleDeg",
    "trailKneeAngleDeg": "{side}KneeAngleDeg",
}

_WRIST_TRAJECTORY_KEYS = {
    "racketSideWrist",
    "throwingWrist",
    "dominantWrist",
    "servingWrist",
    "nonServingWrist",
    "leftWrist",
    "rightWrist",
}


def _side_tokens(dominant_side: str) -> Tuple[str, str, str, str]:
    """Returns (SIDE, OTHER, sideCamel, otherCamel) e.g. RIGHT, LEFT, right, left."""
    if (dominant_side or "right").lower() == "left":
        return "LEFT", "RIGHT", "left", "right"
    return "RIGHT", "LEFT", "right", "left"


def _resolve_landmark_alias(semantic_key: str, dominant_side: str) -> str:
    side, other, _side_c, _other_c = _side_tokens(dominant_side)
    template = _SIDE_LANDMARK_ALIASES.get(semantic_key, semantic_key)
    if "{side}" in template or "{other}" in template:
        return template.format(side=side, other=other)
    return template


class MovementDefinitionProvider:
    def __init__(self):
        self._camera_views = self._load_camera_views()

    def _load_camera_views(self) -> dict:
        if not os.path.exists(CAMERA_VIEWS_PATH):
            return {}
        with open(CAMERA_VIEWS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def load(self, sport_type: str, movement_type: str) -> dict:
        key = f"{sport_type}_{movement_type}".lower()
        path = os.path.join(MOVEMENTS_DIR, f"{key}.json")
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Movement definition not found: {sport_type}/{movement_type} ({path})"
            )
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def preferred_landmarks_for_view(self, camera_view: str) -> Set[str]:
        view = self._camera_views.get(camera_view) or self._camera_views.get("unknown") or {}
        return set(view.get("preferredLandmarks") or [])

    def resolve_trajectory_keys(
        self, definition: dict, dominant_side: str
    ) -> Dict[str, str]:
        """
        Map semantic trajectory key → lookup key in landmarks or derivedPoints.
        Landmark names stay UPPER_SNAKE; derived stay camelCase.
        """
        mapping: Dict[str, str] = {}
        for key in definition.get("trajectoryLandmarks") or []:
            mapping[key] = _resolve_landmark_alias(key, dominant_side)
        return mapping

    def resolve_angles_to_output(
        self, definition: dict, dominant_side: str
    ) -> Dict[str, str]:
        """Map output angle name → base registry angle name."""
        _side, _other, side_c, other_c = _side_tokens(dominant_side)
        mapping: Dict[str, str] = {}
        for out_key in definition.get("anglesToOutput") or []:
            if out_key.endswith("Position") or out_key.endswith("HeightNormalized"):
                continue
            if out_key in _SIDE_ANGLE_ALIASES:
                mapping[out_key] = _SIDE_ANGLE_ALIASES[out_key].format(
                    side=side_c, other=other_c
                )
            else:
                mapping[out_key] = out_key
        return mapping

    def resolve_position_outputs(
        self, definition: dict, dominant_side: str
    ) -> Dict[str, dict]:
        """
        Map Position/Height output key → {resolved, kind}.
        kind: 'position' | 'height'
        resolved: landmark or derived key to look up.
        """
        mapping: Dict[str, dict] = {}
        for out_key in definition.get("anglesToOutput") or []:
            if out_key in _POSITION_OUTPUT_ALIASES:
                semantic = _POSITION_OUTPUT_ALIASES[out_key]
                mapping[out_key] = {
                    "resolved": _resolve_landmark_alias(semantic, dominant_side),
                    "kind": "height"
                    if out_key.endswith("HeightNormalized")
                    else "position",
                }
            elif out_key.endswith("Position"):
                semantic = out_key[: -len("Position")]
                # camelCase first letter lower if needed
                if semantic and semantic[0].isupper():
                    semantic = semantic[0].lower() + semantic[1:]
                mapping[out_key] = {
                    "resolved": _resolve_landmark_alias(semantic, dominant_side),
                    "kind": "position",
                }
            elif out_key.endswith("HeightNormalized"):
                semantic = out_key[: -len("HeightNormalized")]
                if semantic and semantic[0].isupper():
                    semantic = semantic[0].lower() + semantic[1:]
                mapping[out_key] = {
                    "resolved": _resolve_landmark_alias(semantic, dominant_side),
                    "kind": "height",
                }
        return mapping

    def wrist_landmark_names(
        self, definition: dict, dominant_side: str
    ) -> List[str]:
        """Resolved MediaPipe wrist names referenced by trajectories or position outputs."""
        names: Set[str] = set()
        traj = self.resolve_trajectory_keys(definition, dominant_side)
        for semantic, resolved in traj.items():
            if semantic in _WRIST_TRAJECTORY_KEYS or "WRIST" in resolved:
                names.add(resolved)
        for spec in self.resolve_position_outputs(definition, dominant_side).values():
            resolved = spec["resolved"]
            if "WRIST" in resolved:
                names.add(resolved)
        return sorted(names)

    def list_supported(self) -> List[Dict[str, object]]:
        items = []
        if not os.path.isdir(MOVEMENTS_DIR):
            return items
        for name in sorted(os.listdir(MOVEMENTS_DIR)):
            if name.endswith(".json"):
                with open(os.path.join(MOVEMENTS_DIR, name), "r", encoding="utf-8") as f:
                    data = json.load(f)
                label = self._label_for(data.get("sportType"), data.get("movementType"))
                items.append(
                    {
                        "sportType": data.get("sportType"),
                        "movementType": data.get("movementType"),
                        "label": label,
                        "suggestedCameraViews": data.get("suggestedCameraViews") or [],
                        "suggestedMinFps": data.get("suggestedMinFps"),
                        "file": name,
                    }
                )
        return items

    @staticmethod
    def _label_for(sport: Optional[str], movement: Optional[str]) -> str:
        labels = {
            ("fitness", "squat"): "健身／深蹲",
            ("fitness", "deadlift"): "健身／硬舉",
            ("fitness", "lunge"): "健身／弓箭步",
            ("badminton", "smash"): "羽球／殺球",
            ("badminton", "clear"): "羽球／高遠球",
            ("tennis", "forehand"): "網球／正手",
            ("tennis", "backhand"): "網球／反手",
            ("tennis", "serve"): "網球／發球",
            ("baseball", "pitch"): "棒球／投球",
            ("baseball", "bat"): "棒球／打擊",
        }
        return labels.get((sport or "", movement or ""), f"{sport}/{movement}")
