import cv2
import mediapipe as mp
import math
import os
import shutil
import tempfile

from mediapipe.tasks.python.vision import PoseLandmark

SOURCE_MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "models",
    "pose_landmarker_lite.task",
)


def get_model_path() -> str:
    """
    MediaPipe 在 Windows 上無法讀取含非 ASCII 字元的路徑，
    因此將模型複製到系統暫存目錄後再載入。
    """
    if not os.path.exists(SOURCE_MODEL_PATH):
        raise FileNotFoundError(f"Pose model not found: {SOURCE_MODEL_PATH}")

    temp_model_path = os.path.join(
        tempfile.gettempdir(),
        "motion_analysis_pose_landmarker_lite.task",
    )

    if (
        not os.path.exists(temp_model_path)
        or os.path.getmtime(SOURCE_MODEL_PATH) > os.path.getmtime(temp_model_path)
    ):
        shutil.copy2(SOURCE_MODEL_PATH, temp_model_path)

    return temp_model_path

BaseOptions = mp.tasks.BaseOptions
PoseLandmarker = mp.tasks.vision.PoseLandmarker
PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode


def analyze_video_pose(video_path: str):
    """
    分析影片中的人體姿態節點。

    回傳資料：
    - success
    - videoInfo
    - frames
      - frameIndex
      - timeSec
      - landmarks
      - angles
    """

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        return {
            "success": False,
            "message": "Cannot open video file."
        }

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # MVP 階段先每 5 幀分析一次，降低運算量。
    frame_interval = 5

    frames_result = []

    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=get_model_path()),
        running_mode=VisionRunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    with PoseLandmarker.create_from_options(options) as landmarker:
        frame_index = 0

        while True:
            ret, frame = cap.read()

            if not ret:
                break

            if frame_index % frame_interval != 0:
                frame_index += 1
                continue

            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
            timestamp_ms = int((frame_index / fps) * 1000) if fps else frame_index * 33
            result = landmarker.detect_for_video(mp_image, timestamp_ms)

            if result.pose_landmarks:
                pose_landmarks = result.pose_landmarks[0]
                landmarks = []

                for index, landmark in enumerate(pose_landmarks):
                    landmarks.append({
                        "index": index,
                        "name": PoseLandmark(index).name,
                        "x": float(landmark.x),
                        "y": float(landmark.y),
                        "z": float(landmark.z),
                        "visibility": float(landmark.visibility),
                    })

                angles = calculate_basic_angles(landmarks)

                frames_result.append({
                    "frameIndex": frame_index,
                    "timeSec": round(frame_index / fps, 3) if fps else None,
                    "landmarks": landmarks,
                    "angles": angles
                })

            frame_index += 1

    cap.release()

    return {
        "success": True,
        "videoInfo": {
            "fps": fps,
            "totalFrames": total_frames,
            "width": width,
            "height": height,
            "analyzedFrameCount": len(frames_result),
            "frameInterval": frame_interval
        },
        "frames": frames_result
    }


def calculate_basic_angles(landmarks):
    """
    計算基礎關節角度。

    目前先計算：
    - leftKnee
    - rightKnee
    - leftHip
    - rightHip
    """

    def get_point(name):
        for lm in landmarks:
            if lm["name"] == name:
                return lm
        return None

    def angle(a, b, c):
        """
        計算三點夾角。
        b 是角度中心點。

        例如膝關節角度：
        hip - knee - ankle
        """

        if a is None or b is None or c is None:
            return None

        ax, ay = a["x"], a["y"]
        bx, by = b["x"], b["y"]
        cx, cy = c["x"], c["y"]

        ab = (ax - bx, ay - by)
        cb = (cx - bx, cy - by)

        dot = ab[0] * cb[0] + ab[1] * cb[1]
        mag_ab = math.sqrt(ab[0] ** 2 + ab[1] ** 2)
        mag_cb = math.sqrt(cb[0] ** 2 + cb[1] ** 2)

        if mag_ab == 0 or mag_cb == 0:
            return None

        cos_value = dot / (mag_ab * mag_cb)
        cos_value = max(-1, min(1, cos_value))

        return round(math.degrees(math.acos(cos_value)), 2)

    left_hip = get_point("LEFT_HIP")
    left_knee = get_point("LEFT_KNEE")
    left_ankle = get_point("LEFT_ANKLE")

    right_hip = get_point("RIGHT_HIP")
    right_knee = get_point("RIGHT_KNEE")
    right_ankle = get_point("RIGHT_ANKLE")

    left_shoulder = get_point("LEFT_SHOULDER")
    right_shoulder = get_point("RIGHT_SHOULDER")

    return {
        "leftKnee": angle(left_hip, left_knee, left_ankle),
        "rightKnee": angle(right_hip, right_knee, right_ankle),
        "leftHip": angle(left_shoulder, left_hip, left_knee),
        "rightHip": angle(right_shoulder, right_hip, right_knee)
    }
