"""Draw joint trajectory paths over video frames."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from core.render_thresholds import is_drawable
from render.browser_video_writer import create_video_writer

COLORS = [
    (255, 128, 0),
    (0, 128, 255),
    (0, 255, 128),
    (255, 0, 128),
    (128, 255, 0),
    (128, 0, 255),
]


class TrajectoryRenderer:
    def render(
        self,
        video_path: str,
        frames_data: List[dict],
        output_path: str,
        frame_interval: int,
        fps: float,
        width: int,
        height: int,
        trajectory_keys: List[str],
        *,
        browser_playable: bool = False,
    ) -> Optional[str]:
        if not frames_data or not trajectory_keys:
            return None

        by_index = {f["frameIndex"]: f for f in frames_data}
        out_fps = max(fps / frame_interval, 1.0) if fps > 0 else 10.0

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None

        histories: Dict[str, List[Tuple[int, int]]] = {k: [] for k in trajectory_keys}
        color_map = {
            k: COLORS[i % len(COLORS)] for i, k in enumerate(trajectory_keys)
        }

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
                        traj = fd.get("trajectoryPoints") or {}

                        for key in trajectory_keys:
                            pt = traj.get(key)
                            if not pt or pt.get("x") is None or pt.get("y") is None:
                                continue
                            if not is_drawable(pt):
                                continue
                            px = int(round(pt["x"] * width))
                            py = int(round(pt["y"] * height))
                            histories[key].append((px, py))

                        for key in trajectory_keys:
                            pts = histories[key]
                            color = color_map[key]
                            if len(pts) >= 2:
                                for i in range(1, len(pts)):
                                    cv2.line(overlay, pts[i - 1], pts[i], color, 2)
                            if pts:
                                cv2.circle(overlay, pts[-1], 5, color, -1)
                                cv2.putText(
                                    overlay,
                                    key,
                                    (pts[-1][0] + 6, pts[-1][1] - 6),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.4,
                                    color,
                                    1,
                                    cv2.LINE_AA,
                                )

                        writer.write(overlay)

                    frame_index += 1
        except RuntimeError:
            return None
        finally:
            cap.release()

        return output_path
