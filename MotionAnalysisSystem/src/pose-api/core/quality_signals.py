"""Data-quality signal helpers (no movement quality scoring)."""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

import cv2
import numpy as np

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "configs",
    "quality_thresholds.json",
)

_TORSO_NAMES = ("LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_HIP", "RIGHT_HIP")


def load_thresholds() -> dict:
    defaults = {
        "borderMargin": 0.02,
        "bodyOutOfFrameMinTorsoPoints": 2,
        "bodyOutOfFrameFrameRatio": 0.2,
        "laplacianBlurThreshold": 40.0,
        "motionBlurFrameRatio": 0.35,
        "lowVisibilityFrameRatio": 0.25,
        "lowWristVisibility": 0.45,
        "lowWristFrameRatio": 0.3,
    }
    if not os.path.exists(CONFIG_PATH):
        return defaults
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    defaults.update(data)
    return defaults


def frame_laplacian_variance(frame_bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def is_motion_blurry(frame_bgr: np.ndarray, threshold: float) -> bool:
    return frame_laplacian_variance(frame_bgr) < threshold


def torso_near_border_count(landmarks: List[dict], margin: float) -> int:
    count = 0
    by_name = {lm.get("name"): lm for lm in landmarks}
    for name in _TORSO_NAMES:
        lm = by_name.get(name)
        if lm is None:
            count += 1
            continue
        if lm.get("status") == "missing":
            count += 1
            continue
        x = float(lm.get("x") or 0.5)
        y = float(lm.get("y") or 0.5)
        if x < margin or x > 1.0 - margin or y < margin or y > 1.0 - margin:
            count += 1
    return count


def is_body_out_of_frame(
    landmarks: List[dict], margin: float, min_torso_points: int
) -> bool:
    return torso_near_border_count(landmarks, margin) >= min_torso_points


def wrist_low_visibility(
    landmarks: List[dict],
    wrist_names: List[str],
    visibility_threshold: float,
) -> bool:
    if not wrist_names:
        return False
    by_name = {lm.get("name"): lm for lm in landmarks}
    low = 0
    checked = 0
    for name in wrist_names:
        lm = by_name.get(name)
        checked += 1
        if lm is None or lm.get("status") in ("missing", "low_visibility"):
            low += 1
            continue
        if float(lm.get("visibility") or 0.0) < visibility_threshold:
            low += 1
    return checked > 0 and low >= max(1, (checked + 1) // 2)


class QualityAccumulator:
    def __init__(self, thresholds: Optional[dict] = None):
        self.t = thresholds or load_thresholds()
        self.blurry_frames = 0
        self.out_of_frame_frames = 0
        self.low_wrist_frames = 0
        self.analyzed = 0
        self.pose_frames = 0

    def observe(
        self,
        frame_bgr: np.ndarray,
        pose_detected: bool,
        landmarks: List[dict],
        wrist_names: List[str],
    ) -> None:
        self.analyzed += 1
        if is_motion_blurry(frame_bgr, float(self.t["laplacianBlurThreshold"])):
            self.blurry_frames += 1

        if not pose_detected:
            return

        self.pose_frames += 1
        if is_body_out_of_frame(
            landmarks,
            float(self.t["borderMargin"]),
            int(self.t["bodyOutOfFrameMinTorsoPoints"]),
        ):
            self.out_of_frame_frames += 1

        if wrist_low_visibility(
            landmarks, wrist_names, float(self.t["lowWristVisibility"])
        ):
            self.low_wrist_frames += 1

    def ratios(self) -> Dict[str, float]:
        n = max(self.analyzed, 1)
        pose_n = max(self.pose_frames, 1)
        return {
            "motionBlurRatio": self.blurry_frames / n,
            "bodyOutOfFrameRatio": self.out_of_frame_frames / pose_n
            if self.pose_frames
            else 0.0,
            "lowWristRatio": self.low_wrist_frames / pose_n
            if self.pose_frames
            else 0.0,
        }
