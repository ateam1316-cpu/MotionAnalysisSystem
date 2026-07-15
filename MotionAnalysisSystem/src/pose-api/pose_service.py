"""
Backward-compatible entry for simple pose analysis.

New code should call pipeline.analysis_pipeline.AnalysisPipeline.
"""

from pipeline.analysis_pipeline import AnalysisPipeline


def analyze_video_pose(video_path: str):
    """Run default fitness/squat analysis with schemaVersion 1.0 output."""
    pipeline = AnalysisPipeline()
    return pipeline.run(
        video_path,
        sport_type="fitness",
        movement_type="squat",
        camera_view="unknown",
        dominant_side="right",
        frame_interval=5,
        generate_skeleton_video=False,
        generate_trajectory_video=False,
    )


# Re-export model path helper used by older scripts
from core.pose_estimator import get_model_path  # noqa: E402,F401
