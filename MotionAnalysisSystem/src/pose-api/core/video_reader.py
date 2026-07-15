"""Video metadata and frame iteration helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Optional, Tuple

import cv2
import numpy as np


@dataclass
class VideoInfo:
    fps: float
    total_frames: int
    width: int
    height: int
    duration_sec: float

    def to_dict(self, analyzed_frame_count: int, frame_interval: int) -> dict:
        return {
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "durationSec": round(self.duration_sec, 3) if self.duration_sec else 0.0,
            "totalFrames": self.total_frames,
            "analyzedFrameCount": analyzed_frame_count,
            "frameInterval": frame_interval,
        }


class VideoReader:
    def __init__(self, video_path: str):
        self.video_path = video_path
        self._cap: Optional[cv2.VideoCapture] = None

    def open(self) -> bool:
        self._cap = cv2.VideoCapture(self.video_path)
        return bool(self._cap and self._cap.isOpened())

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def get_info(self) -> VideoInfo:
        if self._cap is None:
            raise RuntimeError("Video is not open.")

        fps = float(self._cap.get(cv2.CAP_PROP_FPS) or 0.0)
        total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        duration_sec = (total_frames / fps) if fps > 0 else 0.0

        return VideoInfo(
            fps=fps,
            total_frames=total_frames,
            width=width,
            height=height,
            duration_sec=duration_sec,
        )

    def iter_frames(
        self, frame_interval: int = 1
    ) -> Iterator[Tuple[int, np.ndarray]]:
        """Yield (frame_index, BGR frame) for analyzed frames only."""
        if self._cap is None:
            raise RuntimeError("Video is not open.")

        frame_index = 0
        while True:
            ret, frame = self._cap.read()
            if not ret:
                break

            if frame_index % frame_interval == 0:
                yield frame_index, frame

            frame_index += 1

    def reset(self) -> None:
        if self._cap is not None:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
