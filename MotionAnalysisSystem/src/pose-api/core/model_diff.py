"""Compare Lite vs Full pose frames — Full as baseline body-scale metric."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from core.render_thresholds import RENDER_MIN_PRESENCE, RENDER_MIN_VISIBILITY


def _lm_by_name(landmarks: List[dict]) -> Dict[str, dict]:
    return {lm["name"]: lm for lm in landmarks if lm.get("name")}


def _is_high_confidence(lm: dict) -> bool:
    vis = float(lm.get("visibility") or 0.0)
    presence = float(lm.get("presence") or 0.0)
    return vis >= RENDER_MIN_VISIBILITY and presence >= RENDER_MIN_PRESENCE


def _body_scale(landmarks: List[dict]) -> Optional[float]:
    by_name = _lm_by_name(landmarks)
    ls = by_name.get("LEFT_SHOULDER")
    rs = by_name.get("RIGHT_SHOULDER")
    if ls and rs and ls.get("x") is not None and rs.get("x") is not None:
        w = math.hypot(float(ls["x"]) - float(rs["x"]), float(ls["y"]) - float(rs["y"]))
        if w > 1e-6:
            return w

    lh = by_name.get("LEFT_HIP")
    rh = by_name.get("RIGHT_HIP")
    if lh and rh and lh.get("x") is not None and rh.get("x") is not None:
        w = math.hypot(float(lh["x"]) - float(rh["x"]), float(lh["y"]) - float(rh["y"]))
        if w > 1e-6:
            return w

    if ls and lh and ls.get("x") is not None and lh.get("x") is not None:
        h = math.hypot(float(ls["x"]) - float(lh["x"]), float(ls["y"]) - float(lh["y"]))
        if h > 1e-6:
            return h
    return None


def compare_landmark_frames(
    lite_frames: List[dict],
    full_frames: List[dict],
) -> dict:
    """
    Primary metric: mean (|p_lite - p_full| / body_scale_full) * 100,
    only over landmarks where Full meets visibility/presence thresholds.
    """
    full_by_index = {f["frameIndex"]: f for f in full_frames}
    relative_errors: List[float] = []
    compared_pairs = 0
    detection_agree = 0
    detection_total = 0

    for lite_f in lite_frames:
        idx = lite_f.get("frameIndex")
        full_f = full_by_index.get(idx)
        if full_f is None:
            continue

        detection_total += 1
        lite_det = bool(lite_f.get("poseDetected"))
        full_det = bool(full_f.get("poseDetected"))
        if lite_det == full_det:
            detection_agree += 1

        if not lite_det or not full_det:
            continue

        scale = _body_scale(full_f.get("landmarks") or [])
        if scale is None or scale <= 1e-6:
            continue

        lite_map = _lm_by_name(lite_f.get("landmarks") or [])
        full_map = _lm_by_name(full_f.get("landmarks") or [])

        for name, flm in full_map.items():
            if not _is_high_confidence(flm):
                continue
            llm = lite_map.get(name)
            if llm is None or llm.get("x") is None or flm.get("x") is None:
                continue
            if llm.get("y") is None or flm.get("y") is None:
                continue

            dist = math.hypot(
                float(llm["x"]) - float(flm["x"]),
                float(llm["y"]) - float(flm["y"]),
            )
            relative_errors.append(dist / scale)
            compared_pairs += 1

    if relative_errors:
        mean_rel = sum(relative_errors) / len(relative_errors)
        overall = round(mean_rel * 100.0, 2)
    else:
        overall = None

    return {
        "baseline": "full",
        "candidate": "lite",
        "status": "completed",
        "summary": {
            "overallDiffPercent": overall,
            "landmarkPositionDiffPercent": overall,
            "comparedLandmarkPairs": compared_pairs,
            "detectionAgreementPercent": (
                round(100.0 * detection_agree / detection_total, 2)
                if detection_total
                else None
            ),
        },
        "metricDescription": (
            "以 Full 為基準：可比關節之平均 (|Lite−Full| / Full身體尺度) × 100%；"
            "僅統計 Full 節點 visibility 與 presence 皆 ≥ 0.6 的點。"
        ),
    }
