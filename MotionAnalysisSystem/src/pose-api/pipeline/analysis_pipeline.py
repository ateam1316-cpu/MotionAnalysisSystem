"""Orchestrate the objective pose measurement pipeline."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from typing import Any, Dict, List, Optional

from builders.analysis_result_builder import AnalysisResultBuilder
from core.derived_points import (
    compute_derived_points,
    resolve_effective_point,
    unwrap_point,
)
from core.joint_angle_calculator import JointAngleCalculator
from core.landmark_filter import LandmarkFilter
from core.model_diff import compare_landmark_frames
from core.motion_feature_calculator import MotionFeatureCalculator
from core.pose_estimator import PoseEstimator
from core.quality_signals import QualityAccumulator, load_thresholds
from core.side_exclusion import (
    exclude_body_side_for_view,
    filter_landmarks,
    is_angle_key_excluded,
    is_landmark_excluded,
    is_resolved_traj_excluded,
)
from core.video_reader import VideoReader
from movements.definition_provider import MovementDefinitionProvider
from render.skeleton_video_renderer import SkeletonVideoRenderer
from render.trajectory_renderer import TrajectoryRenderer

STORAGE_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage")
RUN_META_NAME = "run_meta.json"
SOURCE_VIDEO_NAME = "source_video"

_CENTER_TO_REFERENCE = {
    "shoulderCenter": "shoulderReference",
    "hipCenter": "hipReference",
    "bodyCenter": "bodyReference",
}


def _lookup_point(
    landmarks: List[dict],
    derived: Dict[str, Any],
    resolved_key: str,
) -> Optional[dict]:
    if resolved_key in _CENTER_TO_REFERENCE:
        return resolve_effective_point(
            derived, resolved_key, _CENTER_TO_REFERENCE[resolved_key]
        )
    if resolved_key in derived:
        return unwrap_point(derived[resolved_key])
    for lm in landmarks:
        if lm.get("name") == resolved_key and lm.get("status") != "missing":
            return lm
    return None


def _point_payload(point: Optional[dict]) -> Optional[dict]:
    if point is None:
        return None
    coords = unwrap_point(point) if isinstance(point, dict) else None
    if coords is None and point.get("x") is not None:
        coords = point
    if coords is None:
        return None
    payload = {
        "x": coords.get("x"),
        "y": coords.get("y"),
        "z": coords.get("z"),
        "pixelX": coords.get("pixelX"),
        "pixelY": coords.get("pixelY"),
        "status": coords.get("status", point.get("status", "valid")),
    }
    if coords.get("visibility") is not None:
        payload["visibility"] = coords.get("visibility")
    elif point.get("visibility") is not None:
        payload["visibility"] = point.get("visibility")
    if coords.get("presence") is not None:
        payload["presence"] = coords.get("presence")
    elif point.get("presence") is not None:
        payload["presence"] = point.get("presence")
    if point.get("confidence") is not None:
        payload["confidence"] = point.get("confidence")
    return payload


class AnalysisPipeline:
    def __init__(self, public_base_url: str = "http://127.0.0.1:8000"):
        self.public_base_url = public_base_url.rstrip("/")
        self.definition_provider = MovementDefinitionProvider()
        self.angle_calculator = JointAngleCalculator()
        self.motion_calculator = MotionFeatureCalculator()
        self.result_builder = AnalysisResultBuilder()
        self.skeleton_renderer = SkeletonVideoRenderer()
        self.trajectory_renderer = TrajectoryRenderer()

    def run(
        self,
        video_path: str,
        *,
        sport_type: str,
        movement_type: str,
        camera_view: str = "unknown",
        dominant_side: str = "right",
        frame_interval: int = 1,
        generate_skeleton_video: bool = True,
        generate_trajectory_video: bool = True,
        browser_playable_video: bool = False,
        model_variant: str = "lite",
        compare_with_full: bool = False,
        analysis_id: Optional[str] = None,
        keep_source_video: bool = False,
        video_name_suffix: str = "",
    ) -> dict:
        """
        Run a single-model analysis pass.

        When compare_with_full=True, runs Lite, keeps source video, and marks
        modelComparison.status = pending_full for a later compare_full call.
        """
        if compare_with_full:
            model_variant = "lite"
            keep_source_video = True
            video_name_suffix = video_name_suffix or "_lite"

        return self._run_pass(
            video_path,
            sport_type=sport_type,
            movement_type=movement_type,
            camera_view=camera_view,
            dominant_side=dominant_side,
            frame_interval=frame_interval,
            generate_skeleton_video=generate_skeleton_video,
            generate_trajectory_video=generate_trajectory_video,
            browser_playable_video=browser_playable_video,
            model_variant=model_variant,
            analysis_id=analysis_id,
            keep_source_video=keep_source_video,
            video_name_suffix=video_name_suffix,
            pending_full_compare=compare_with_full,
        )

    def compare_full(self, analysis_id: str) -> dict:
        """Continue a Lite compare session: run Full on saved source and merge metrics."""
        out_dir = os.path.join(STORAGE_ROOT, analysis_id)
        meta_path = os.path.join(out_dir, RUN_META_NAME)
        lite_result_path = os.path.join(out_dir, "result_lite.json")
        result_path = os.path.join(out_dir, "result.json")

        if not os.path.isfile(meta_path):
            return {
                "schemaVersion": "1.1",
                "analysisId": analysis_id,
                "success": False,
                "message": "Compare session not found (missing run metadata).",
                "warnings": [],
            }

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        source_name = meta.get("sourceVideoName") or ""
        source_path = os.path.join(out_dir, source_name) if source_name else ""
        if not source_path or not os.path.isfile(source_path):
            return {
                "schemaVersion": "1.1",
                "analysisId": analysis_id,
                "success": False,
                "message": "Source video for compare-full not found.",
                "warnings": [],
            }

        lite_frames: List[dict] = []
        lite_result: dict = {}
        if os.path.isfile(lite_result_path):
            with open(lite_result_path, "r", encoding="utf-8") as f:
                lite_result = json.load(f)
            lite_frames = list(lite_result.get("frames") or [])
        elif os.path.isfile(result_path):
            with open(result_path, "r", encoding="utf-8") as f:
                lite_result = json.load(f)
            lite_frames = list(lite_result.get("frames") or [])

        full_result = self._run_pass(
            source_path,
            sport_type=meta["sportType"],
            movement_type=meta["movementType"],
            camera_view=meta.get("cameraView") or "unknown",
            dominant_side=meta.get("dominantSide") or "right",
            frame_interval=int(meta.get("frameInterval") or 1),
            generate_skeleton_video=bool(meta.get("generateSkeletonVideo", True)),
            generate_trajectory_video=bool(meta.get("generateTrajectoryVideo", True)),
            browser_playable_video=bool(meta.get("browserPlayableVideo", False)),
            model_variant="full",
            analysis_id=analysis_id,
            keep_source_video=False,
            video_name_suffix="_full",
            pending_full_compare=False,
            write_result_json=False,
        )

        if not full_result.get("success"):
            return full_result

        comparison = compare_landmark_frames(
            lite_frames, list(full_result.get("frames") or [])
        )

        lite_files = (lite_result.get("outputFiles") or {}) if lite_result else {}
        full_files = full_result.get("outputFiles") or {}

        lite_json_url = f"{self.public_base_url}/files/{analysis_id}/result_lite.json"
        full_json_url = f"{self.public_base_url}/files/{analysis_id}/result_full.json"
        merged_files = {
            "skeletonVideoUrl": lite_files.get("skeletonVideoUrl"),
            "trajectoryVideoUrl": lite_files.get("trajectoryVideoUrl"),
            "skeletonLiteVideoUrl": lite_files.get("skeletonVideoUrl"),
            "trajectoryLiteVideoUrl": lite_files.get("trajectoryVideoUrl"),
            "skeletonFullVideoUrl": full_files.get("skeletonVideoUrl"),
            "trajectoryFullVideoUrl": full_files.get("trajectoryVideoUrl"),
            "browserPlayable": bool(
                lite_files.get("browserPlayable") or full_files.get("browserPlayable")
            ),
            "rawJsonUrl": lite_json_url,
            "rawLiteJsonUrl": lite_json_url,
            "rawFullJsonUrl": full_json_url,
        }

        comparison["outputFiles"] = {
            "skeletonLiteVideoUrl": merged_files.get("skeletonLiteVideoUrl"),
            "trajectoryLiteVideoUrl": merged_files.get("trajectoryLiteVideoUrl"),
            "skeletonFullVideoUrl": merged_files.get("skeletonFullVideoUrl"),
            "trajectoryFullVideoUrl": merged_files.get("trajectoryFullVideoUrl"),
            "rawLiteJsonUrl": lite_json_url,
            "rawFullJsonUrl": full_json_url,
        }

        # Primary payload remains Lite frames (already shown); attach Full + comparison.
        merged = dict(lite_result) if lite_result else dict(full_result)
        merged["analysisId"] = analysis_id
        merged["success"] = True
        merged["outputFiles"] = merged_files
        merged["modelComparison"] = comparison
        merged["fullDetectionInfo"] = full_result.get("detectionInfo")
        # Keep full frames for debugging / download size control: store separately.
        full_result_path = os.path.join(out_dir, "result_full.json")
        with open(full_result_path, "w", encoding="utf-8") as f:
            json.dump(full_result, f, ensure_ascii=False)

        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False)

        meta["compareStatus"] = "completed"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)

        return merged

    def _run_pass(
        self,
        video_path: str,
        *,
        sport_type: str,
        movement_type: str,
        camera_view: str,
        dominant_side: str,
        frame_interval: int,
        generate_skeleton_video: bool,
        generate_trajectory_video: bool,
        browser_playable_video: bool,
        model_variant: str,
        analysis_id: Optional[str],
        keep_source_video: bool,
        video_name_suffix: str,
        pending_full_compare: bool,
        write_result_json: bool = True,
    ) -> dict:
        definition = self.definition_provider.load(sport_type, movement_type)
        preferred = self.definition_provider.preferred_landmarks_for_view(camera_view)
        exclude_side = exclude_body_side_for_view(camera_view)
        traj_map = self.definition_provider.resolve_trajectory_keys(
            definition, dominant_side
        )
        if exclude_side:
            traj_map = {
                k: v
                for k, v in traj_map.items()
                if not is_resolved_traj_excluded(v, exclude_side)
            }
        angle_map = self.definition_provider.resolve_angles_to_output(
            definition, dominant_side
        )
        if exclude_side:
            angle_map = {
                k: v
                for k, v in angle_map.items()
                if not is_angle_key_excluded(v, exclude_side)
            }
        position_map = self.definition_provider.resolve_position_outputs(
            definition, dominant_side
        )
        if exclude_side:
            position_map = {
                k: v
                for k, v in position_map.items()
                if not is_landmark_excluded(v.get("resolved", ""), exclude_side)
                and not is_resolved_traj_excluded(v.get("resolved", ""), exclude_side)
            }
        wrist_names = self.definition_provider.wrist_landmark_names(
            definition, dominant_side
        )
        if exclude_side:
            wrist_names = [
                n for n in wrist_names if not is_landmark_excluded(n, exclude_side)
            ]
        quality_thresholds = load_thresholds()
        quality = QualityAccumulator(quality_thresholds)

        analysis_id = analysis_id or str(uuid.uuid4())
        out_dir = os.path.join(STORAGE_ROOT, analysis_id)
        os.makedirs(out_dir, exist_ok=True)

        if keep_source_video:
            ext = os.path.splitext(video_path)[1] or ".mp4"
            source_name = f"{SOURCE_VIDEO_NAME}{ext}"
            source_dest = os.path.join(out_dir, source_name)
            if os.path.abspath(video_path) != os.path.abspath(source_dest):
                shutil.copy2(video_path, source_dest)
            video_path = source_dest
            meta = {
                "sportType": sport_type,
                "movementType": movement_type,
                "cameraView": camera_view,
                "dominantSide": dominant_side,
                "frameInterval": frame_interval,
                "generateSkeletonVideo": generate_skeleton_video,
                "generateTrajectoryVideo": generate_trajectory_video,
                "browserPlayableVideo": browser_playable_video,
                "sourceVideoName": source_name,
                "compareStatus": "pending_full" if pending_full_compare else "none",
            }
            with open(os.path.join(out_dir, RUN_META_NAME), "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False)

        reader = VideoReader(video_path)
        if not reader.open():
            return {
                "schemaVersion": "1.1",
                "analysisId": analysis_id,
                "success": False,
                "message": "Cannot open video file.",
                "warnings": [],
            }

        try:
            info = reader.get_info()
            frame_interval = max(int(frame_interval or 1), 1)

            landmark_filter = LandmarkFilter(preferred_landmarks=preferred)
            self.motion_calculator.reset()

            frames_out: List[dict] = []
            traj_series: Dict[str, List[dict]] = {k: [] for k in traj_map.keys()}
            confidence_sum = 0.0
            confidence_n = 0
            missing_frame_count = 0
            multiple_people_any = False
            low_vis_frames = 0
            detected_any = False

            with PoseEstimator(
                num_poses=1, model_variant=model_variant
            ) as estimator:
                for frame_index, frame in reader.iter_frames(frame_interval):
                    time_sec = (
                        round(frame_index / info.fps, 3) if info.fps > 0 else 0.0
                    )
                    timestamp_ms = (
                        int((frame_index / info.fps) * 1000)
                        if info.fps > 0
                        else frame_index * 33
                    )

                    detection = estimator.detect(
                        frame, timestamp_ms, info.width, info.height
                    )

                    if detection["personCount"] > 1:
                        multiple_people_any = True

                    pose_detected = detection["poseDetected"]
                    landmarks = detection["landmarks"]

                    if pose_detected:
                        detected_any = True
                        landmarks = landmark_filter.apply_status(landmarks)
                        landmarks = landmark_filter.smooth(landmarks, True)
                        landmarks = filter_landmarks(landmarks, exclude_side)
                        primary = set(definition.get("primaryLandmarks") or [])
                        if exclude_side:
                            primary = {
                                n
                                for n in primary
                                if not is_landmark_excluded(n, exclude_side)
                            }
                        if primary:
                            low_count = sum(
                                1
                                for lm in landmarks
                                if lm["name"] in primary
                                and lm.get("status") in ("low_visibility", "missing")
                            )
                            if low_count >= max(1, len(primary) // 3):
                                low_vis_frames += 1
                        for lm in landmarks:
                            confidence_sum += float(lm.get("visibility") or 0.0)
                            confidence_n += 1
                    else:
                        missing_frame_count += 1
                        landmarks = landmark_filter.smooth([], False)

                    quality.observe(frame, pose_detected, landmarks, wrist_names)

                    derived = (
                        compute_derived_points(
                            landmarks, exclude_side=exclude_side
                        )
                        if pose_detected
                        else {}
                    )
                    all_angles = (
                        self.angle_calculator.calculate(
                            landmarks, derived, exclude_side=exclude_side
                        )
                        if pose_detected
                        else {}
                    )
                    joint_angles = {
                        out_key: all_angles.get(base_key)
                        for out_key, base_key in angle_map.items()
                        if all_angles.get(base_key) is not None
                    }

                    if pose_detected:
                        self._add_position_outputs(
                            joint_angles,
                            position_map,
                            landmarks,
                            derived,
                        )
                    else:
                        for out_key in position_map:
                            joint_angles[out_key] = None

                    trajectory_points: Dict[str, Any] = {}
                    for semantic_key, resolved in traj_map.items():
                        point = (
                            _lookup_point(landmarks, derived, resolved)
                            if pose_detected
                            else None
                        )
                        payload = _point_payload(point)
                        motion = self.motion_calculator.update_point(
                            semantic_key,
                            payload["x"] if payload else None,
                            payload["y"] if payload else None,
                            time_sec,
                        )
                        entry = payload or {}
                        if motion:
                            entry = {**entry, **motion}
                        trajectory_points[semantic_key] = entry if entry else None
                        traj_series[semantic_key].append(
                            {
                                "x": entry.get("x") if entry else None,
                                "y": entry.get("y") if entry else None,
                                "timeSec": time_sec,
                            }
                        )

                    frames_out.append(
                        {
                            "frameIndex": frame_index,
                            "timeSec": time_sec,
                            "poseDetected": pose_detected,
                            "landmarks": landmarks,
                            "jointAngles": joint_angles,
                            "derivedPoints": derived,
                            "trajectoryPoints": trajectory_points,
                        }
                    )

            trajectory_summary = self.motion_calculator.summarize_trajectory(traj_series)

            avg_conf = (
                round(confidence_sum / confidence_n, 4) if confidence_n else 0.0
            )
            detection_info = {
                "poseModel": f"mediapipe_pose_landmarker_{model_variant}",
                "modelVariant": model_variant,
                "averagePoseConfidence": avg_conf,
                "missingFrameCount": missing_frame_count,
                "excludeBodySide": exclude_side,
            }

            analyzed_count = len(frames_out)
            low_vis_ratio = (
                low_vis_frames / analyzed_count if analyzed_count else 0.0
            )
            q_ratios = quality.ratios()

            warnings = self.result_builder.collect_warnings(
                fps=info.fps,
                suggested_min_fps=float(definition.get("suggestedMinFps") or 0),
                camera_view=camera_view,
                suggested_camera_views=list(
                    definition.get("suggestedCameraViews") or []
                ),
                missing_frame_count=missing_frame_count,
                analyzed_frame_count=analyzed_count,
                multiple_people_any=multiple_people_any,
                low_visibility_ratio=low_vis_ratio,
                pose_never_detected=not detected_any,
                body_out_of_frame_ratio=q_ratios["bodyOutOfFrameRatio"],
                motion_blur_ratio=q_ratios["motionBlurRatio"],
                low_wrist_ratio=q_ratios["lowWristRatio"],
                body_out_of_frame_threshold=float(
                    quality_thresholds["bodyOutOfFrameFrameRatio"]
                ),
                motion_blur_threshold=float(
                    quality_thresholds["motionBlurFrameRatio"]
                ),
                low_wrist_threshold=float(quality_thresholds["lowWristFrameRatio"]),
                track_wrists=bool(wrist_names),
            )

            skeleton_name = None
            trajectory_name = None
            sk_file = f"skeleton{video_name_suffix}.mp4"
            tr_file = f"trajectory{video_name_suffix}.mp4"

            if generate_skeleton_video and analyzed_count > 0:
                sk_path = os.path.join(out_dir, sk_file)
                written = self.skeleton_renderer.render(
                    video_path,
                    frames_out,
                    sk_path,
                    frame_interval,
                    info.fps,
                    info.width,
                    info.height,
                    browser_playable=browser_playable_video,
                    angle_map=angle_map,
                )
                if written:
                    skeleton_name = sk_file

            if generate_trajectory_video and analyzed_count > 0:
                tr_path = os.path.join(out_dir, tr_file)
                written = self.trajectory_renderer.render(
                    video_path,
                    frames_out,
                    tr_path,
                    frame_interval,
                    info.fps,
                    info.width,
                    info.height,
                    list(traj_map.keys()),
                    browser_playable=browser_playable_video,
                )
                if written:
                    trajectory_name = tr_file

            if browser_playable_video and (skeleton_name or trajectory_name):
                marker = os.path.join(out_dir, ".browser_playable")
                with open(marker, "w", encoding="utf-8") as f:
                    f.write("1")

            output_files = {
                "skeletonVideoUrl": (
                    f"{self.public_base_url}/files/{analysis_id}/{skeleton_name}"
                    if skeleton_name
                    else None
                ),
                "trajectoryVideoUrl": (
                    f"{self.public_base_url}/files/{analysis_id}/{trajectory_name}"
                    if trajectory_name
                    else None
                ),
                "browserPlayable": bool(
                    browser_playable_video and (skeleton_name or trajectory_name)
                ),
                "rawJsonUrl": f"{self.public_base_url}/files/{analysis_id}/result.json",
            }

            result = self.result_builder.build(
                analysis_id=analysis_id,
                movement={
                    "sportType": sport_type,
                    "movementType": movement_type,
                    "cameraView": camera_view,
                    "dominantSide": dominant_side,
                },
                video_info=info.to_dict(analyzed_count, frame_interval),
                detection_info=detection_info,
                frames=frames_out,
                trajectory_summary=trajectory_summary,
                output_files=output_files,
                warnings=warnings,
                success=True,
            )

            if pending_full_compare:
                lite_json_url = (
                    f"{self.public_base_url}/files/{analysis_id}/result_lite.json"
                )
                output_files["skeletonLiteVideoUrl"] = output_files.get(
                    "skeletonVideoUrl"
                )
                output_files["trajectoryLiteVideoUrl"] = output_files.get(
                    "trajectoryVideoUrl"
                )
                output_files["rawJsonUrl"] = lite_json_url
                output_files["rawLiteJsonUrl"] = lite_json_url
                result["outputFiles"] = output_files
                result["modelComparison"] = {
                    "baseline": "full",
                    "candidate": "lite",
                    "status": "pending_full",
                    "summary": None,
                    "metricDescription": (
                        "以 Full 為基準：可比關節之平均 (|Lite−Full| / Full身體尺度) × 100%。"
                    ),
                }

            if write_result_json:
                result_path = os.path.join(out_dir, "result.json")
                with open(result_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False)
                if pending_full_compare:
                    lite_path = os.path.join(out_dir, "result_lite.json")
                    with open(lite_path, "w", encoding="utf-8") as f:
                        json.dump(result, f, ensure_ascii=False)

            return result
        finally:
            reader.close()

    def _add_position_outputs(
        self,
        joint_angles: dict,
        position_map: Dict[str, dict],
        landmarks: List[dict],
        derived: Dict[str, Any],
    ) -> None:
        """Attach Position/Height snapshots from resolved definition map."""
        for out_key, spec in position_map.items():
            point = _lookup_point(landmarks, derived, spec["resolved"])
            payload = _point_payload(point)
            if payload is None:
                joint_angles[out_key] = None
            elif spec.get("kind") == "height":
                joint_angles[out_key] = round(1.0 - float(payload["y"]), 4)
            else:
                joint_angles[out_key] = payload
