"""Displacement, velocity, acceleration, and direction from trajectory points."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple


class MotionFeatureCalculator:
    def __init__(self):
        # key -> (x, y, time_sec, velocity)
        self._prev: Dict[str, Tuple[float, float, float, float]] = {}

    def reset(self) -> None:
        self._prev = {}

    def update_point(
        self,
        key: str,
        x: Optional[float],
        y: Optional[float],
        time_sec: float,
    ) -> Optional[dict]:
        if x is None or y is None:
            return None

        prev = self._prev.get(key)
        if prev is None:
            self._prev[key] = (x, y, time_sec, 0.0)
            return {
                "displacementNormalized": 0.0,
                "velocityNormalizedPerSec": 0.0,
                "accelerationNormalizedPerSec2": 0.0,
                "directionDeg": None,
            }

        px, py, pt, pvel = prev
        dt = time_sec - pt
        if dt <= 0:
            dt = 1e-6

        dx = x - px
        dy = y - py
        displacement = math.hypot(dx, dy)
        velocity = displacement / dt
        acceleration = (velocity - pvel) / dt
        direction = round(math.degrees(math.atan2(-dy, dx)), 2)  # image y-down → atan2(-dy)

        self._prev[key] = (x, y, time_sec, velocity)

        return {
            "displacementNormalized": round(displacement, 6),
            "velocityNormalizedPerSec": round(velocity, 4),
            "accelerationNormalizedPerSec2": round(acceleration, 4),
            "directionDeg": direction,
        }

    def summarize_trajectory(
        self, series: Dict[str, List[dict]]
    ) -> Dict[str, dict]:
        """Build trajectorySummary from lists of {x,y,timeSec} per key."""
        summary: Dict[str, dict] = {}
        for key, points in series.items():
            valid = [p for p in points if p.get("x") is not None and p.get("y") is not None]
            if len(valid) < 2:
                summary[key] = {
                    "pointCount": len(valid),
                    "totalDisplacementNormalized": 0.0,
                    "maxVelocityNormalizedPerSec": 0.0,
                    "path": valid,
                }
                continue

            total_disp = 0.0
            max_vel = 0.0
            for i in range(1, len(valid)):
                dx = valid[i]["x"] - valid[i - 1]["x"]
                dy = valid[i]["y"] - valid[i - 1]["y"]
                d = math.hypot(dx, dy)
                total_disp += d
                dt = valid[i].get("timeSec", 0) - valid[i - 1].get("timeSec", 0)
                if dt > 0:
                    max_vel = max(max_vel, d / dt)

            summary[key] = {
                "pointCount": len(valid),
                "totalDisplacementNormalized": round(total_disp, 6),
                "maxVelocityNormalizedPerSec": round(max_vel, 4),
                "start": {"x": valid[0]["x"], "y": valid[0]["y"]},
                "end": {"x": valid[-1]["x"], "y": valid[-1]["y"]},
            }
        return summary
