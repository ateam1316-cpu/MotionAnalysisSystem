# 動作偵測分析系統：C# + Python FastAPI 架構與 Pose Detection 實作規格

> 本文件提供給 Cursor 使用，作為建立「動作偵測分析系統」MVP 的開發依據。  
> 初期架構採用 **C# ASP.NET Core MVC + Python FastAPI + MediaPipe/OpenCV**。  
> 功能穩定後，再評估將 Python Pose Detection 推論層替換為 **ONNX Runtime**，讓 C# 系統部署更穩定。

---

## 1. 專案目標

建立一套可以根據影片分析人體動作節點的系統。

第一階段 MVP 目標：

1. 使用者在 C# MVC 頁面上傳影片。
2. C# MVC 將影片送到 Python FastAPI。
3. Python FastAPI 使用 OpenCV 讀取影片。
4. Python 使用 MediaPipe Pose Detection 擷取人體姿態節點。
5. Python 計算基本關節角度，例如膝關節、髖關節。
6. Python 回傳 JSON 給 C#。
7. C# 頁面顯示分析結果 JSON。

後續階段再加入：

1. 動作規則判斷，例如深蹲、弓箭步、硬舉。
2. 分析報告產生。
3. 串接 ChatGPT / Claude / Gemini API 產生自然語言回饋。
4. 將 Python 推論層替換為 ONNX Runtime。
5. C# 端直接執行 ONNX 模型，降低部署依賴。

---

## 2. 技術選擇

| 模組 | 技術 | 用途 |
|---|---|---|
| Web 系統 | ASP.NET Core MVC | 上傳影片、顯示分析結果、管理流程 |
| 姿態偵測 API | Python FastAPI | 接收影片並執行 Pose Detection |
| 影片處理 | OpenCV | 讀取影片、逐幀處理 |
| 姿態偵測 | MediaPipe Pose | 擷取人體 33 個姿態節點 |
| 資料交換 | JSON | C# 與 Python API 溝通 |
| 未來推論 | ONNX Runtime | 將 Python 推論層替換為 C# 可部署推論 |
| 開發工具 | Cursor / Visual Studio | Cursor 負責 AI 輔助開發，Visual Studio 可用於 C# 專案維護 |

---

## 3. 架構總覽

```text
使用者上傳影片
        ↓
ASP.NET Core MVC Controller
        ↓
PoseApiClient 使用 HttpClient 呼叫 Python API
        ↓
Python FastAPI /analyze/video
        ↓
OpenCV 讀取影片
        ↓
MediaPipe Pose Detection 擷取人體節點
        ↓
計算基本關節角度
        ↓
回傳 JSON
        ↓
C# MVC 顯示分析結果
```

---

## 4. 專案資料夾結構

建議專案結構如下：

```text
MotionAnalysisSystem/
│
├─ src/
│  │
│  ├─ MotionAnalysis.Web/                 # C# ASP.NET Core MVC 專案
│  │  ├─ Controllers/
│  │  │  └─ PoseController.cs
│  │  │
│  │  ├─ Models/
│  │  │  └─ VideoAnalyzeViewModel.cs
│  │  │
│  │  ├─ Services/
│  │  │  └─ PoseApiClient.cs
│  │  │
│  │  ├─ Views/
│  │  │  └─ Pose/
│  │  │     └─ Index.cshtml
│  │  │
│  │  ├─ Program.cs
│  │  └─ MotionAnalysis.Web.csproj
│  │
│  └─ pose-api/                           # Python FastAPI 專案
│     ├─ main.py
│     ├─ pose_service.py
│     ├─ requirements.txt
│     ├─ temp/
│     └─ README.md
│
├─ docs/
│  ├─ api-contract.md
│  └─ THIRD_PARTY_LICENSES.md
│
└─ README.md
```

---

## 5. 建立 C# ASP.NET Core MVC 專案

在專案根目錄執行：

```bash
mkdir MotionAnalysisSystem
cd MotionAnalysisSystem
mkdir src
cd src
dotnet new mvc -n MotionAnalysis.Web
```

進入 C# 專案：

```bash
cd MotionAnalysis.Web
dotnet run
```

確認 MVC 專案可正常啟動。

---

## 6. 建立 Python FastAPI 專案

回到 `src` 目錄：

```bash
cd ..
mkdir pose-api
cd pose-api
python -m venv .venv
```

啟用虛擬環境。

Windows PowerShell：

```bash
.venv\Scripts\Activate.ps1
```

如果 PowerShell 權限受限，可改用：

```bash
.venv\Scripts\activate.bat
```

建立 `requirements.txt`：

```txt
fastapi
uvicorn
python-multipart
opencv-python
mediapipe
numpy
```

安裝套件：

```bash
pip install -r requirements.txt
```

---

## 7. Python FastAPI 實作

### 7.1 建立 `main.py`

檔案路徑：

```text
src/pose-api/main.py
```

內容：

```python
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import tempfile
import shutil
import os

from pose_service import analyze_video_pose

app = FastAPI(title="Motion Pose Analysis API")


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "service": "pose-api"
    }


@app.post("/analyze/video")
async def analyze_video(file: UploadFile = File(...)):
    """
    接收影片檔案，執行 Pose Detection，回傳人體節點與基本角度。
    """

    temp_path = None

    try:
        suffix = os.path.splitext(file.filename)[1]

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = temp_file.name

        result = analyze_video_pose(temp_path)

        return JSONResponse(content=result)

    except Exception as ex:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": str(ex)
            }
        )

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
```

---

### 7.2 建立 `pose_service.py`

檔案路徑：

```text
src/pose-api/pose_service.py
```

內容：

```python
import cv2
import mediapipe as mp
import math


mp_pose = mp.solutions.pose


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

    with mp_pose.Pose(
        static_image_mode=False,
        model_complexity=1,
        enable_segmentation=False,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as pose:

        frame_index = 0

        while True:
            ret, frame = cap.read()

            if not ret:
                break

            if frame_index % frame_interval != 0:
                frame_index += 1
                continue

            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = pose.process(image_rgb)

            if result.pose_landmarks:
                landmarks = []

                for index, landmark in enumerate(result.pose_landmarks.landmark):
                    landmarks.append({
                        "index": index,
                        "name": mp_pose.PoseLandmark(index).name,
                        "x": float(landmark.x),
                        "y": float(landmark.y),
                        "z": float(landmark.z),
                        "visibility": float(landmark.visibility)
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
```

---

## 8. 啟動 Python FastAPI

在 `src/pose-api` 目錄執行：

```bash
uvicorn main:app --reload --port 8000
```

瀏覽器打開：

```text
http://127.0.0.1:8000/docs
```

測試：

1. 開啟 Swagger UI。
2. 找到 `POST /analyze/video`。
3. 上傳影片。
4. 確認回傳 `success: true`。
5. 確認有 `videoInfo`、`frames`、`landmarks`、`angles`。

---

## 9. C# MVC 實作

### 9.1 建立 ViewModel

檔案路徑：

```text
src/MotionAnalysis.Web/Models/VideoAnalyzeViewModel.cs
```

內容：

```csharp
using Microsoft.AspNetCore.Http;

namespace MotionAnalysis.Web.Models;

public class VideoAnalyzeViewModel
{
    public IFormFile? VideoFile { get; set; }

    public string? AnalysisJson { get; set; }

    public string? ErrorMessage { get; set; }
}
```

---

### 9.2 建立 Python API Client

檔案路徑：

```text
src/MotionAnalysis.Web/Services/PoseApiClient.cs
```

內容：

```csharp
using System.Net.Http.Headers;

namespace MotionAnalysis.Web.Services;

public class PoseApiClient
{
    private readonly HttpClient _httpClient;

    public PoseApiClient(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    public async Task<string> AnalyzeVideoAsync(IFormFile videoFile)
    {
        using var form = new MultipartFormDataContent();

        await using var stream = videoFile.OpenReadStream();

        var fileContent = new StreamContent(stream);
        fileContent.Headers.ContentType = new MediaTypeHeaderValue(
            string.IsNullOrWhiteSpace(videoFile.ContentType)
                ? "application/octet-stream"
                : videoFile.ContentType
        );

        form.Add(fileContent, "file", videoFile.FileName);

        var response = await _httpClient.PostAsync("/analyze/video", form);

        var responseText = await response.Content.ReadAsStringAsync();

        if (!response.IsSuccessStatusCode)
        {
            throw new Exception($"Pose API error: {response.StatusCode}, {responseText}");
        }

        return responseText;
    }
}
```

---

### 9.3 註冊 PoseApiClient

打開：

```text
src/MotionAnalysis.Web/Program.cs
```

加入：

```csharp
using MotionAnalysis.Web.Services;
```

在 `builder.Services` 區域加入：

```csharp
builder.Services.AddHttpClient<PoseApiClient>(client =>
{
    client.BaseAddress = new Uri("http://127.0.0.1:8000");
    client.Timeout = TimeSpan.FromMinutes(10);
});
```

---

### 9.4 建立 PoseController

檔案路徑：

```text
src/MotionAnalysis.Web/Controllers/PoseController.cs
```

內容：

```csharp
using Microsoft.AspNetCore.Mvc;
using MotionAnalysis.Web.Models;
using MotionAnalysis.Web.Services;

namespace MotionAnalysis.Web.Controllers;

public class PoseController : Controller
{
    private readonly PoseApiClient _poseApiClient;

    public PoseController(PoseApiClient poseApiClient)
    {
        _poseApiClient = poseApiClient;
    }

    [HttpGet]
    public IActionResult Index()
    {
        return View(new VideoAnalyzeViewModel());
    }

    [HttpPost]
    public async Task<IActionResult> Index(VideoAnalyzeViewModel model)
    {
        if (model.VideoFile == null || model.VideoFile.Length == 0)
        {
            model.ErrorMessage = "請上傳影片檔案。";
            return View(model);
        }

        try
        {
            var resultJson = await _poseApiClient.AnalyzeVideoAsync(model.VideoFile);
            model.AnalysisJson = resultJson;
        }
        catch (Exception ex)
        {
            model.ErrorMessage = ex.Message;
        }

        return View(model);
    }
}
```

---

### 9.5 建立 View

檔案路徑：

```text
src/MotionAnalysis.Web/Views/Pose/Index.cshtml
```

內容：

```cshtml
@model MotionAnalysis.Web.Models.VideoAnalyzeViewModel

<h2>影片姿態節點分析</h2>

<form asp-controller="Pose"
      asp-action="Index"
      method="post"
      enctype="multipart/form-data">

    <div class="mb-3">
        <label class="form-label">上傳影片</label>
        <input asp-for="VideoFile" type="file" class="form-control" accept="video/*" />
    </div>

    <button type="submit" class="btn btn-primary">
        開始分析
    </button>
</form>

@if (!string.IsNullOrWhiteSpace(Model.ErrorMessage))
{
    <div class="alert alert-danger mt-3">
        @Model.ErrorMessage
    </div>
}

@if (!string.IsNullOrWhiteSpace(Model.AnalysisJson))
{
    <h3 class="mt-4">分析結果 JSON</h3>

    <pre style="white-space: pre-wrap; background: #f5f5f5; padding: 16px; max-height: 600px; overflow: auto;">
@Model.AnalysisJson
    </pre>
}
```

---

## 10. 執行順序

### 10.1 啟動 Python API

終端機一：

```bash
cd src/pose-api
.venv\Scripts\activate.bat
uvicorn main:app --reload --port 8000
```

確認 API 可用：

```text
http://127.0.0.1:8000/docs
```

---

### 10.2 啟動 C# MVC

終端機二：

```bash
cd src/MotionAnalysis.Web
dotnet run
```

開啟 C# 網站後進入：

```text
/Pose/Index
```

上傳影片測試。

---

## 11. 預期回傳 JSON 格式

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

---

## 12. MVP 驗收標準

第一階段完成後，應符合以下條件：

- [ ] C# MVC 可以正常啟動。
- [ ] Python FastAPI 可以正常啟動。
- [ ] `http://127.0.0.1:8000/docs` 可以開啟。
- [ ] C# `/Pose/Index` 可以上傳影片。
- [ ] C# 可以成功呼叫 Python `/analyze/video`。
- [ ] Python 可以讀取影片 fps、總幀數、解析度。
- [ ] Python 可以擷取 MediaPipe 33 個人體節點。
- [ ] Python 可以計算左膝、右膝、左髖、右髖角度。
- [ ] C# 可以顯示回傳 JSON。
- [ ] 錯誤時 C# 畫面可以顯示錯誤訊息。

---

## 13. 開發注意事項

### 13.1 初期不要直接做完整動作評分

第一版先做節點與角度，不要急著做「深蹲是否標準」。

建議流程：

```text
Pose Detection
        ↓
取得關節節點
        ↓
計算角度
        ↓
找出關鍵時間點
        ↓
規則判斷
        ↓
產生摘要
        ↓
必要時交給 LLM 產生自然語言回饋
```

不建議：

```text
直接把所有逐幀座標丟給 LLM 判斷動作對錯
```

原因：

1. LLM 不適合負責精確運動學判斷。
2. 逐幀資料量很大，成本高且不穩定。
3. 角度與規則判斷應由程式處理。
4. LLM 適合把結構化結果轉成容易理解的回饋文字。

---

### 13.2 影片檔案先不儲存

MVP 階段 Python API 收到影片後，暫存到 temp file，分析完立即刪除。

正式版再決定是否要：

1. 儲存原始影片。
2. 儲存分析後影片。
3. 儲存 JSON。
4. 儲存動作分析報告。
5. 設定影片保存期限。

---

### 13.3 初期先用每 5 幀分析一次

若影片 30 FPS，每 5 幀分析一次約等於每秒分析 6 次。

好處：

1. 運算量較低。
2. 回傳 JSON 不會過大。
3. 初期足夠觀察深蹲、弓箭步等動作變化。

後續可改成：

```python
frame_interval = 1
```

代表每一幀都分析，但運算量會大幅增加。

---

### 13.4 visibility 太低的節點要小心使用

MediaPipe landmark 中的 `visibility` 代表該節點可見程度。

後續做規則判斷時，建議加上：

```text
若關鍵節點 visibility < 0.5，該幀不納入判斷。
```

例如深蹲需要：

- LEFT_HIP
- LEFT_KNEE
- LEFT_ANKLE
- RIGHT_HIP
- RIGHT_KNEE
- RIGHT_ANKLE
- LEFT_SHOULDER
- RIGHT_SHOULDER

若這些節點被遮住，角度可能不準。

---

## 14. 下一階段功能規劃

完成 MVP 後，建議依序加入：

### 14.1 資料模型化

C# 不只顯示 JSON，而是建立 DTO：

```text
PoseAnalysisResult
VideoInfo
FramePoseResult
PoseLandmarkDto
JointAnglesDto
```

---

### 14.2 深蹲分析

建立 Python 或 C# 規則判斷：

```text
找出膝角最小的幀 = 深蹲最低點
分析最低點膝角
分析左右膝角差
分析髖角
分析軀幹前傾
分析是否深度足夠
```

---

### 14.3 回傳動作摘要

例如：

```json
{
  "movement": "squat",
  "summary": {
    "bottomFrameIndex": 85,
    "minLeftKneeAngle": 72.5,
    "minRightKneeAngle": 75.1,
    "leftRightKneeDiff": 2.6,
    "depthStatus": "sufficient",
    "symmetryStatus": "good"
  },
  "issues": [
    "軀幹前傾偏多",
    "最低點左膝角度略小於右膝"
  ]
}
```

---

### 14.4 LLM 回饋

將規則判斷後的摘要交給 LLM：

```text
請根據以下深蹲動作分析結果，產生一段給使用者的動作回饋。
要求：
1. 不要做醫療診斷。
2. 語氣像專業教練。
3. 先肯定做得好的地方。
4. 再指出 1-2 個主要調整方向。
5. 給一個具體練習建議。
```

---

## 15. 未來 ONNX 替換方向

目前 Python 架構：

```text
main.py
        ↓
pose_service.py
        ↓
MediaPipe Pose
```

未來若要換 ONNX，建議維持 API contract 不變：

```text
POST /analyze/video
Input: video file
Output: landmarks + angles + summary
```

只替換內部實作：

```text
pose_service.py
從 MediaPipe 改為 ONNX Runtime
```

或改成 C# 端：

```text
MotionAnalysis.Web
        ↓
OnnxPoseEstimator.cs
        ↓
ONNX Runtime
```

C# MVC、資料庫、前端頁面、使用者流程不需要重寫。

---

## 16. 授權與成本注意事項

目前 MVP 使用的核心套件大多可以免費使用：

| 工具 | 授權狀態 |
|---|---|
| .NET / ASP.NET Core | 免費、開源 |
| Python | 免費 |
| FastAPI | 免費 |
| OpenCV | 免費 |
| MediaPipe | 通常可免費使用，但正式商用前需確認模型授權 |
| ONNX Runtime | 免費 |


正式商用前建議建立：

```text
docs/THIRD_PARTY_LICENSES.md
```

列出第三方套件與模型授權。

---

## 17. Cursor 實作指令建議

可以請 Cursor 依照以下順序實作：

```text
請根據本 Markdown 文件建立專案。
第一步：建立 src/MotionAnalysis.Web ASP.NET Core MVC 專案。
第二步：建立 src/pose-api Python FastAPI 專案。
第三步：完成 Python /analyze/video API，可接收影片並回傳 videoInfo。
第四步：加入 OpenCV 讀影片。
第五步：加入 MediaPipe Pose Detection，回傳每 5 幀的 landmarks。
第六步：加入 leftKnee、rightKnee、leftHip、rightHip 角度計算。
第七步：在 C# MVC 建立 PoseController、PoseApiClient、VideoAnalyzeViewModel、Views/Pose/Index.cshtml。
第八步：讓 C# 上傳影片並呼叫 Python API。
第九步：讓 C# 頁面顯示 Python 回傳 JSON。
第十步：確認錯誤處理與基本驗收標準。
```

---

## 18. 開發原則

本專案初期請遵守以下原則：

1. 先讓流程跑通，不先追求完整 UI。
2. 先回傳 JSON，不先做資料庫。
3. 先做節點擷取，不先做動作評分。
4. 先做規則判斷，不先依賴 LLM。
5. Python 服務要獨立，方便未來替換成 ONNX。
6. C# 端要透過 service 呼叫 Python，不要把 HTTP 呼叫寫死在 Controller。
7. API 回傳格式要穩定，未來換模型時盡量不改 C# 前端。
8. 影片與人體資料涉及個資，正式版需補隱私權政策與資料保存規則。

---

## 19. 建議 Commit 階段

```text
commit 1: 建立 C# MVC 專案
commit 2: 建立 Python FastAPI 專案
commit 3: Python API 完成影片上傳與 videoInfo 回傳
commit 4: Python API 加入 MediaPipe Pose Detection
commit 5: Python API 加入角度計算
commit 6: C# MVC 加入影片上傳頁
commit 7: C# MVC 串接 Python API
commit 8: 整理錯誤處理與 README
```

---

## 20. 本階段完成定義

當以下功能完成，就代表 MVP 第一階段完成：

```text
使用者可以在 C# MVC 頁面上傳影片
        ↓
C# 將影片送到 Python FastAPI
        ↓
Python 擷取影片中的人體姿態節點
        ↓
Python 計算基本關節角度
        ↓
Python 回傳 JSON
        ↓
C# 顯示 JSON 分析結果
```

此時可以進入下一階段：

```text
根據特定運動項目，例如深蹲，建立動作規則判斷。
```
