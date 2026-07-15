# API Contract

schemaVersion：**1.0**（客觀姿態量測；不含動作品質評分欄位）

---

## GET /

健康檢查。

```json
{
  "status": "ok",
  "service": "pose-api",
  "schemaVersion": "1.0"
}
```

---

## GET /movements

列出目前支援的運動／動作（由 `configs/movements/*.json` 載入）。

```json
{
  "schemaVersion": "1.0",
  "movements": [
    {
      "sportType": "fitness",
      "movementType": "squat",
      "label": "健身／深蹲",
      "suggestedCameraViews": ["front", "side_left", "side_right"],
      "suggestedMinFps": 30,
      "file": "fitness_squat.json"
    }
  ]
}
```

支援的 sport／movement：

| sportType | movementType |
|-----------|--------------|
| fitness | squat, deadlift, lunge |
| badminton | smash, clear |
| tennis | forehand, backhand, serve |
| baseball | pitch, bat |

---

## POST /analyze/video

接收影片與動作中繼資料，回傳統一 JSON；可選產生骨架／軌跡影片。

### Request

- Content-Type: `multipart/form-data`

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `file` | file | 是 | 影片檔案 |
| `sportType` | string | 否 | 預設 `fitness`；見 `GET /movements` |
| `movementType` | string | 否 | 預設 `squat`；見 `GET /movements` |
| `cameraView` | string | 否 | 預設 `unknown`；見拍攝角度清單 |
| `dominantSide` | string | 否 | `right`（預設）或 `left` |
| `frameInterval` | int | 否 | 每幾幀分析一次，預設 `1` |
| `generateSkeletonVideo` | bool | 否 | 預設 `true` |
| `generateTrajectoryVideo` | bool | 否 | 預設 `true` |

### 拍攝角度

`front` / `rear` / `side_left` / `side_right` / `front_diagonal_left` / `front_diagonal_right` / `rear_diagonal_left` / `rear_diagonal_right` / `unknown`

### Response（成功）

HTTP 200

```json
{
  "schemaVersion": "1.0",
  "analysisId": "uuid",
  "success": true,
  "movement": {
    "sportType": "baseball",
    "movementType": "pitch",
    "cameraView": "side_right",
    "dominantSide": "right"
  },
  "videoInfo": {
    "fps": 120,
    "width": 1920,
    "height": 1080,
    "durationSec": 4.2,
    "totalFrames": 504,
    "analyzedFrameCount": 504,
    "frameInterval": 1
  },
  "detectionInfo": {
    "poseModel": "mediapipe_pose",
    "averagePoseConfidence": 0.91,
    "missingFrameCount": 5
  },
  "frames": [
    {
      "frameIndex": 126,
      "timeSec": 2.1,
      "poseDetected": true,
      "landmarks": [
        {
          "index": 16,
          "name": "RIGHT_WRIST",
          "x": 0.712,
          "y": 0.284,
          "z": -0.193,
          "pixelX": 1367,
          "pixelY": 307,
          "visibility": 0.94,
          "presence": 0.91,
          "status": "valid"
        }
      ],
      "jointAngles": {
        "throwingShoulderAngleDeg": 120.5,
        "throwingElbowAngleDeg": 95.2
      },
      "derivedPoints": {
        "shoulderCenter": { "x": 0.5, "y": 0.3, "z": 0.0, "pixelX": 960, "pixelY": 324, "status": "valid" },
        "hipCenter": { "x": 0.5, "y": 0.55, "z": 0.0, "pixelX": 960, "pixelY": 594, "status": "valid" }
      },
      "trajectoryPoints": {
        "throwingWrist": {
          "x": 0.71,
          "y": 0.28,
          "z": -0.19,
          "pixelX": 1367,
          "pixelY": 307,
          "status": "valid",
          "displacementNormalized": 0.031,
          "velocityNormalizedPerSec": 1.82,
          "accelerationNormalizedPerSec2": 4.15,
          "directionDeg": 42.6
        }
      }
    }
  ],
  "trajectorySummary": {},
  "outputFiles": {
    "skeletonVideoUrl": "http://127.0.0.1:8000/files/{analysisId}/skeleton.mp4",
    "trajectoryVideoUrl": "http://127.0.0.1:8000/files/{analysisId}/trajectory.mp4",
    "rawJsonUrl": "http://127.0.0.1:8000/files/{analysisId}/result.json"
  },
  "warnings": [
    {
      "code": "LOW_FPS",
      "message": "影片 FPS 偏低……"
    }
  ]
}
```

### landmark.status

`valid` / `low_visibility` / `estimated` / `missing`

### warnings（僅資料品質）

`LOW_LANDMARK_VISIBILITY` / `LOW_WRIST_VISIBILITY` / `BODY_OUT_OF_FRAME` / `MULTIPLE_PEOPLE_DETECTED` / `LOW_FPS` / `MOTION_BLUR` / `UNSUPPORTED_CAMERA_VIEW` / `POSE_NOT_DETECTED`

### Response（影片無法開啟）

HTTP 200，`success: false`

```json
{
  "schemaVersion": "1.0",
  "analysisId": "uuid",
  "success": false,
  "message": "Cannot open video file.",
  "warnings": []
}
```

### Response（不支援的動作定義）

HTTP 400

```json
{
  "schemaVersion": "1.0",
  "success": false,
  "message": "Movement definition not found: ...",
  "warnings": []
}
```

### Response（伺服器錯誤）

HTTP 500

```json
{
  "schemaVersion": "1.0",
  "success": false,
  "message": "錯誤訊息",
  "warnings": []
}
```

---

## GET /files/{analysisId}/{filename}

安全下載分析產物（限制在 `storage/{analysisId}/` 內）。

- `analysisId`：UUID
- `filename`：例如 `skeleton.mp4`、`trajectory.mp4`、`result.json`

---

## 已移除欄位（不應出現）

`overallScore`、`qualityAssessment`、`qualityDimensions`、`evaluations`、`strengths`、`issues`、`recommendations`、`referenceRange`、`pass`、`fail`、`warning`（動作品質語意）、`severity`
