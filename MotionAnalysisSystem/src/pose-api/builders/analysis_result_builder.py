"""Assemble schemaVersion 1.1 analysis result and data-quality warnings."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class AnalysisResultBuilder:
    def build(
        self,
        *,
        analysis_id: str,
        movement: dict,
        video_info: dict,
        detection_info: dict,
        frames: List[dict],
        trajectory_summary: dict,
        output_files: dict,
        warnings: List[dict],
        success: bool = True,
        message: Optional[str] = None,
    ) -> dict:
        result: Dict[str, Any] = {
            "schemaVersion": "1.1",
            "analysisId": analysis_id,
            "success": success,
            "movement": movement,
            "videoInfo": video_info,
            "detectionInfo": detection_info,
            "frames": frames,
            "trajectorySummary": trajectory_summary,
            "outputFiles": output_files,
            "warnings": warnings,
        }
        if message:
            result["message"] = message
        return result

    def collect_warnings(
        self,
        *,
        fps: float,
        suggested_min_fps: float,
        camera_view: str,
        suggested_camera_views: List[str],
        missing_frame_count: int,
        analyzed_frame_count: int,
        multiple_people_any: bool,
        low_visibility_ratio: float,
        pose_never_detected: bool,
        body_out_of_frame_ratio: float = 0.0,
        motion_blur_ratio: float = 0.0,
        low_wrist_ratio: float = 0.0,
        body_out_of_frame_threshold: float = 0.2,
        motion_blur_threshold: float = 0.35,
        low_wrist_threshold: float = 0.3,
        track_wrists: bool = False,
    ) -> List[dict]:
        warnings: List[dict] = []

        if pose_never_detected:
            warnings.append(
                {
                    "code": "POSE_NOT_DETECTED",
                    "message": "整段分析影格皆未偵測到人體姿態。",
                }
            )
        elif missing_frame_count > 0 and analyzed_frame_count > 0:
            warnings.append(
                {
                    "code": "POSE_NOT_DETECTED",
                    "message": f"有 {missing_frame_count} 個分析影格未偵測到姿態。",
                }
            )

        if fps > 0 and suggested_min_fps > 0 and fps < suggested_min_fps:
            warnings.append(
                {
                    "code": "LOW_FPS",
                    "message": (
                        f"影片 FPS 為 {fps:.1f}，低於此動作建議最低 {suggested_min_fps:.0f} FPS，"
                        "可能漏失快速動作影格。"
                    ),
                }
            )

        if (
            suggested_camera_views
            and camera_view
            and camera_view != "unknown"
            and camera_view not in suggested_camera_views
        ):
            warnings.append(
                {
                    "code": "UNSUPPORTED_CAMERA_VIEW",
                    "message": (
                        f"拍攝角度「{camera_view}」不在此動作建議角度清單中；"
                        "系統仍會輸出節點資料，但部分節點可見度可能較差。"
                    ),
                }
            )

        if multiple_people_any:
            warnings.append(
                {
                    "code": "MULTIPLE_PEOPLE_DETECTED",
                    "message": "部分影格偵測到多人，系統僅使用第一人姿態。",
                }
            )

        if low_visibility_ratio >= 0.25:
            warnings.append(
                {
                    "code": "LOW_LANDMARK_VISIBILITY",
                    "message": "部分影格主要關節可見度偏低。",
                }
            )

        if body_out_of_frame_ratio >= body_out_of_frame_threshold:
            warnings.append(
                {
                    "code": "BODY_OUT_OF_FRAME",
                    "message": "部分影格人體主要軀幹節點接近或超出畫面邊界。",
                }
            )

        if motion_blur_ratio >= motion_blur_threshold:
            warnings.append(
                {
                    "code": "MOTION_BLUR",
                    "message": "部分影格影像清晰度偏低，可能影響節點定位穩定度。",
                }
            )

        if track_wrists and low_wrist_ratio >= low_wrist_threshold:
            warnings.append(
                {
                    "code": "LOW_WRIST_VISIBILITY",
                    "message": "部分影格手腕可見度偏低。",
                }
            )

        return warnings
