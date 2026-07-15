"""Draw MediaPipe-style skeleton overlay video."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from render.browser_video_writer import create_video_writer

# MediaPipe Pose connections (subset of landmark index pairs)
POSE_CONNECTIONS: List[Tuple[int, int]] = [
    (0, 1), (1, 2), (2, 3), (3, 7),
    (0, 4), (4, 5), (5, 6), (6, 8),
    (9, 10),
    (11, 12),
    (11, 13), (13, 15), (15, 17), (15, 19), (15, 21),
    (12, 14), (14, 16), (16, 18), (16, 20), (16, 22),
    (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27), (27, 29), (27, 31),
    (24, 26), (26, 28), (28, 30), (28, 32),
]


class SkeletonVideoRenderer:
    def render(
        self,
        video_path: str,
        frames_data: List[dict],
        output_path: str,
        frame_interval: int,
        fps: float,
        width: int,
        height: int,
        *,
        browser_playable: bool = False,
    ) -> Optional[str]:
        if not frames_data:
            return None

        by_index = {f["frameIndex"]: f for f in frames_data}
        out_fps = max(fps / frame_interval, 1.0) if fps > 0 else 10.0

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None

        frame_index = 0
        try:
            with create_video_writer(
                output_path, out_fps, width, height, browser_playable=browser_playable
            ) as writer:
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break

                    if frame_index % frame_interval == 0 and frame_index in by_index:
                        overlay = frame.copy()
                        fd = by_index[frame_index]
                        if fd.get("poseDetected") and fd.get("landmarks"):
                            self._draw_pose(overlay, fd["landmarks"])
                        writer.write(overlay)

                    frame_index += 1
        except RuntimeError:
            return None
        finally:
            cap.release()

        return output_path

    def _draw_pose(self, frame: np.ndarray, landmarks: List[dict]) -> None:
        by_index: Dict[int, dict] = {
            lm["index"]: lm
            for lm in landmarks
            if lm.get("status") not in ("missing",)
        }

        for a, b in POSE_CONNECTIONS:
            if a in by_index and b in by_index:
                pa = by_index[a]
                pb = by_index[b]
                cv2.line(
                    frame,
                    (pa["pixelX"], pa["pixelY"]),
                    (pb["pixelX"], pb["pixelY"]),
                    (0, 200, 0),
                    2,
                )

        for lm in by_index.values():
            color = (0, 255, 0) if lm.get("status") == "valid" else (0, 165, 255)
            cv2.circle(frame, (lm["pixelX"], lm["pixelY"]), 4, color, -1)
