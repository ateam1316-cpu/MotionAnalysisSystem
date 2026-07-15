"""Orchestrate the objective pose measurement pipeline."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, List, Optional

from builders.analysis_result_builder import AnalysisResultBuilder
from core.derived_points import compute_derived_points
from core.joint_angle_calculator import JointAngleCalculator
from core.landmark_filter import LandmarkFilter
from core.motion_feature_calculator import MotionFeatureCalculator
from core.pose_estimator import PoseEstimator
from core.quality_signals import QualityAccumulator, load_thresholds
from core.video_reader import VideoReader
from movements.definition_provider import MovementDefinitionProvider
from render.skeleton_video_renderer import SkeletonVideoRenderer
from render.trajectory_renderer import TrajectoryRenderer

STORAGE_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage")


def _lookup_point(
    landmarks: List[dict],
    derived: Dict[str, dict],
    resolved_key: str,
) -> Optional[dict]:
    if resolved_key in derived:
        return derived[resolved_key]
    for lm in landmarks:
        if lm.get("name") == resolved_key and lm.get("status") != "missing":
            return lm
    return None


def _point_payload(point: Optional[dict]) -> Optional[dict]:
    if point is None:
        return None
    return {
        "x": point.get("x"),
        "y": point.get("y"),
        "z": point.get("z"),
        "pixelX": point.get("pixelX"),
        "pixelY": point.get("pixelY"),
        "status": point.get("status", "valid"),
    }


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
    ) -> dict:
        definition = self.definition_provider.load(sport_type, movement_type)
        preferred = self.definition_provider.preferred_landmarks_for_view(camera_view)
        traj_map = self.definition_provider.resolve_trajectory_keys(
            definition, dominant_side
        )
        angle_map = self.definition_provider.resolve_angles_to_output(
            definition, dominant_side
        )
        position_map = self.definition_provider.resolve_position_outputs(
            definition, dominant_side
        )
        wrist_names = self.definition_provider.wrist_landmark_names(
            definition, dominant_side
        )
        quality_thresholds = load_thresholds()
        quality = QualityAccumulator(quality_thresholds)

        analysis_id = str(uuid.uuid4())
        out_dir = os.path.join(STORAGE_ROOT, analysis_id)
        os.makedirs(out_dir, exist_ok=True)

        reader = VideoReader(video_path)
        if not reader.open():
            return {
                "schemaVersion": "1.0",
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

            with PoseEstimator(num_poses=1) as estimator:
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
                        primary = set(definition.get("primaryLandmarks") or [])
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
                        compute_derived_points(landmarks) if pose_detected else {}
                    )
                    all_angles = (
                        self.angle_calculator.calculate(landmarks, derived)
                        if pose_detected
                        else {}
                    )
                    joint_angles = {
                        out_key: all_angles.get(base_key)
                        for out_key, base_key in angle_map.items()
                    }

                    # Extra position-style outputs used by some sports
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

                    # Filter derived to useful centers
                    derived_out = {
                        k: {
                            "x": v["x"],
                            "y": v["y"],
                            "z": v["z"],
                            "pixelX": v["pixelX"],
                            "pixelY": v["pixelY"],
                            "status": v.get("status", "valid"),
                        }
                        for k, v in derived.items()
                    }

                    frames_out.append(
                        {
                            "frameIndex": frame_index,
                            "timeSec": time_sec,
                            "poseDetected": pose_detected,
                            "landmarks": landmarks,
                            "jointAngles": joint_angles,
                            "derivedPoints": derived_out,
                            "trajectoryPoints": trajectory_points,
                        }
                    )

            trajectory_summary = self.motion_calculator.summarize_trajectory(traj_series)

            avg_conf = (
                round(confidence_sum / confidence_n, 4) if confidence_n else 0.0
            )
            detection_info = {
                "poseModel": "mediapipe_pose",
                "averagePoseConfidence": avg_conf,
                "missingFrameCount": missing_frame_count,
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

            if generate_skeleton_video and analyzed_count > 0:
                sk_path = os.path.join(out_dir, "skeleton.mp4")
                written = self.skeleton_renderer.render(
                    video_path,
                    frames_out,
                    sk_path,
                    frame_interval,
                    info.fps,
                    info.width,
                    info.height,
                    browser_playable=browser_playable_video,
                )
                if written:
                    skeleton_name = "skeleton.mp4"

            if generate_trajectory_video and analyzed_count > 0:
                tr_path = os.path.join(out_dir, "trajectory.mp4")
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
                    trajectory_name = "trajectory.mp4"

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

            result_path = os.path.join(out_dir, "result.json")
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False)

            return result
        finally:
            reader.close()

    def _add_position_outputs(
        self,
        joint_angles: dict,
        position_map: Dict[str, dict],
        landmarks: List[dict],
        derived: Dict[str, dict],
    ) -> None:
        """Attach Position/Height snapshots from resolved definition map."""
        for out_key, spec in position_map.items():
            point = _lookup_point(landmarks, derived, spec["resolved"])
            if point is None:
                joint_angles[out_key] = None
            elif spec.get("kind") == "height":
                joint_angles[out_key] = round(1.0 - float(point["y"]), 4)
            else:
                joint_angles[out_key] = _point_payload(point)
