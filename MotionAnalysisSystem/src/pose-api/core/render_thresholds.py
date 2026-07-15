"""Render-only confidence thresholds (separate from LandmarkFilter analysis gates)."""

from __future__ import annotations

from typing import Any, Optional

# Draw skeleton / trajectory / angle labels only when both scores meet this floor.
RENDER_MIN_VISIBILITY = 0.6
RENDER_MIN_PRESENCE = 0.6


def is_drawable(point: Optional[dict]) -> bool:
    """True when a landmark/point should appear on overlay videos."""
    if not point:
        return False
    if point.get("status") in ("missing", "bilateral_landmarks_unavailable"):
        return False
    # Envelope without concrete coordinates
    if "value" in point and point.get("value") is None and point.get("x") is None:
        return False

    vis = point.get("visibility")
    presence = point.get("presence")
    if vis is not None and presence is not None:
        return float(vis) >= RENDER_MIN_VISIBILITY and float(presence) >= RENDER_MIN_PRESENCE

    confidence = point.get("confidence")
    if confidence is not None:
        return float(confidence) >= RENDER_MIN_VISIBILITY

    # Derived points without explicit scores: only trust fully valid midpoints.
    return point.get("status") == "valid"
