"""MediaPipe pose estimation only — no movement-specific logic."""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Any, List, Optional

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python.vision import PoseLandmark

BaseOptions = mp.tasks.BaseOptions
PoseLandmarker = mp.tasks.vision.PoseLandmarker
PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")

MODEL_FILES = {
    "lite": "pose_landmarker_lite.task",
    "full": "pose_landmarker_full.task",
}


def get_model_path(model_variant: str = "lite") -> str:
    """
    MediaPipe on Windows cannot read non-ASCII paths.
    Copy the model into the system temp directory before loading.
    """
    variant = (model_variant or "lite").strip().lower()
    if variant not in MODEL_FILES:
        raise ValueError(f"Unsupported model variant: {model_variant}")

    source_model_path = os.path.join(MODELS_DIR, MODEL_FILES[variant])
    if not os.path.exists(source_model_path):
        raise FileNotFoundError(f"Pose model not found: {source_model_path}")

    temp_model_path = os.path.join(
        tempfile.gettempdir(),
        f"motion_analysis_pose_landmarker_{variant}.task",
    )

    if (
        not os.path.exists(temp_model_path)
        or os.path.getmtime(source_model_path) > os.path.getmtime(temp_model_path)
    ):
        shutil.copy2(source_model_path, temp_model_path)

    return temp_model_path


class PoseEstimator:
    def __init__(self, num_poses: int = 1, model_variant: str = "lite"):
        self.num_poses = num_poses
        self.model_variant = (model_variant or "lite").strip().lower()
        self._landmarker: Optional[Any] = None

    def __enter__(self) -> "PoseEstimator":
        options = PoseLandmarkerOptions(
            base_options=BaseOptions(
                model_asset_path=get_model_path(self.model_variant)
            ),
            running_mode=VisionRunningMode.VIDEO,
            num_poses=self.num_poses,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._landmarker = PoseLandmarker.create_from_options(options)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None

    def detect(
        self,
        frame_bgr: np.ndarray,
        timestamp_ms: int,
        width: int,
        height: int,
    ) -> dict:
        """
        Returns:
          poseDetected, personCount, landmarks (raw list or empty)
        """
        if self._landmarker is None:
            raise RuntimeError("PoseEstimator is not started.")

        image_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        person_count = len(result.pose_landmarks) if result.pose_landmarks else 0
        if not result.pose_landmarks:
            return {
                "poseDetected": False,
                "personCount": 0,
                "landmarks": [],
            }

        pose_landmarks = result.pose_landmarks[0]
        landmarks: List[dict] = []

        for index, landmark in enumerate(pose_landmarks):
            visibility = float(getattr(landmark, "visibility", 0.0) or 0.0)
            presence = float(getattr(landmark, "presence", visibility) or visibility)
            x = float(landmark.x)
            y = float(landmark.y)
            z = float(landmark.z)

            landmarks.append(
                {
                    "index": index,
                    "name": PoseLandmark(index).name,
                    "x": x,
                    "y": y,
                    "z": z,
                    "pixelX": int(round(x * width)),
                    "pixelY": int(round(y * height)),
                    "visibility": visibility,
                    "presence": presence,
                    "status": "valid",
                }
            )

        return {
            "poseDetected": True,
            "personCount": person_count,
            "landmarks": landmarks,
        }
