"""Draw MediaPipe-style skeleton overlay video with optional joint angles."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from core.angle_overlay import resolve_angle_overlays
from core.render_thresholds import is_drawable
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
        angle_map: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        if not frames_data:
            return None

        by_index = {f["frameIndex"]: f for f in frames_data}
        out_fps = max(fps / frame_interval, 1.0) if fps > 0 else 10.0
        angle_map = angle_map or {}

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
                            if angle_map:
                                overlays = resolve_angle_overlays(
                                    fd.get("jointAngles") or {},
                                    fd.get("landmarks") or [],
                                    fd.get("derivedPoints") or {},
                                    angle_map,
                                )
                                self._draw_angles(overlay, overlays)
                        writer.write(overlay)

                    frame_index += 1
        except RuntimeError:
            return None
        finally:
            cap.release()

        return output_path

    def _draw_pose(self, frame: np.ndarray, landmarks: List[dict]) -> None:
        by_index: Dict[int, dict] = {
            lm["index"]: lm for lm in landmarks if is_drawable(lm)
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
            cv2.circle(frame, (lm["pixelX"], lm["pixelY"]), 4, (0, 255, 0), -1)

    def _draw_angles(
        self,
        frame: np.ndarray,
        overlays: List[Tuple[str, float, int, int]],
    ) -> None:
        for i, (label, _deg, px, py) in enumerate(overlays):
            # Slight stagger so nearby joints are less overlapping.
            ox = 8 + (i % 3) * 2
            oy = -8 - (i % 4) * 12
            org = (px + ox, max(16, py + oy))
            cv2.putText(
                frame,
                label,
                org,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 0, 0),
                3,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                label,
                org,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )
