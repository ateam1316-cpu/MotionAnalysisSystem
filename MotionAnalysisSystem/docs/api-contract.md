# API Contract

## POST /analyze/video

接收影片檔案，回傳人體姿態節點與基本關節角度。

### Request

- Content-Type: `multipart/form-data`
- Field: `file`（影片檔案）

### Response（成功）

```json
{
  "success": true,
  "videoInfo": {
    "fps": 30.0,
    "totalFrames": 300,
    "width": 1920,
    "height": 1080,
    "analyzedFrameCount": 60,
    "frameInterval": 5
  },
  "frames": [
    {
      "frameIndex": 0,
      "timeSec": 0.0,
      "landmarks": [
        {
          "index": 23,
          "name": "LEFT_HIP",
          "x": 0.48,
          "y": 0.52,
          "z": -0.12,
          "visibility": 0.98
        }
      ],
      "angles": {
        "leftKnee": 105.2,
        "rightKnee": 106.8,
        "leftHip": 78.4,
        "rightHip": 80.1
      }
    }
  ]
}
```

### Response（影片無法開啟）

HTTP 200，`success: false`

```json
{
  "success": false,
  "message": "Cannot open video file."
}
```

### Response（伺服器錯誤）

HTTP 500

```json
{
  "success": false,
  "message": "錯誤訊息"
}
```
