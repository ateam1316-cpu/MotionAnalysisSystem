# 運動動作分析功能說明

> schemaVersion **1.0** — 客觀姿態量測系統  
> 本文件整理目前專案能做到的運動／動作分析能力，以及輸出內容如何解讀。

---

## 1. 功能定位

系統接收動作影片與中繼資料（運動類型、動作類型、拍攝角度、慣用側等），透過 **MediaPipe Pose** 偵測人體骨架，輸出：

| 可做到 | 做不到 |
|--------|--------|
| 關節座標、可見度、狀態 | 動作品質評分（如 overallScore） |
| 關節角度／位置量測 | 通過／失敗判定 |
| 關鍵點位移、速度、加速度、方向 | 優缺點評語、改善建議 |
| 骨架標註影片、軌跡影片 | 球軌跡、器材偵測 |
| 拍攝／偵測**資料品質**警告 | 多人姿態同時追蹤（僅取第一人） |

架構：ASP.NET Core MVC（上傳介面）+ Python FastAPI（分析管線）。

---

## 2. 支援的運動與動作一覽

| 運動（sportType） | 動作（movementType） | 顯示名稱 | 建議最低 FPS | 設定檔 |
|-------------------|----------------------|----------|--------------|--------|
| fitness | squat | 健身／深蹲 | 30 | `fitness_squat.json` |
| fitness | deadlift | 健身／硬舉 | 30 | `fitness_deadlift.json` |
| fitness | lunge | 健身／弓箭步 | 30 | `fitness_lunge.json` |
| badminton | smash | 羽球／殺球 | 30 | `badminton_smash.json` |
| badminton | clear | 羽球／高遠球 | 30 | `badminton_clear.json` |
| tennis | forehand | 網球／正手 | 30 | `tennis_forehand.json` |
| tennis | backhand | 網球／反手 | 30 | `tennis_backhand.json` |
| tennis | serve | 網球／發球 | 30 | `tennis_serve.json` |
| baseball | pitch | 棒球／投球 | 60 | `baseball_pitch.json` |
| baseball | bat | 棒球／打擊 | 60 | `baseball_bat.json` |

動作定義來源：`src/pose-api/configs/movements/*.json`  
清單 API：`GET /movements`

---

## 3. 共通分析能力

無論選擇哪種動作，管線都會提供下列能力。

### 3.1 輸入參數

| 參數 | 說明 |
|------|------|
| 影片檔 | 必填，常見影音格式 |
| sportType / movementType | 運動與動作；預設 fitness / squat |
| cameraView | 拍攝角度（見下方清單） |
| dominantSide | 慣用側：`right`（預設）或 `left`；影響投擲／揮拍側等衍生點 |
| frameInterval | 每 N 幀分析一次；`1` = 全幀 |
| generateSkeletonVideo | 是否產生骨架標註影片（預設 true） |
| generateTrajectoryVideo | 是否產生關節軌跡影片（預設 true） |

### 3.2 拍攝角度（cameraView）

| 值 | 含義 |
|----|------|
| front | 正面 |
| rear | 背面 |
| side_left | 左側 |
| side_right | 右側 |
| front_diagonal_left | 左前斜 |
| front_diagonal_right | 右前斜 |
| rear_diagonal_left | 左後斜 |
| rear_diagonal_right | 右後斜 |
| unknown | 未指定（預設） |

若指定角度不在該動作的「建議角度」內，仍會分析，但可能出現 `UNSUPPORTED_CAMERA_VIEW` 品質警告。

### 3.3 輸出產物

| 產物 | 說明 |
|------|------|
| `skeleton.mp4` | 原片疊加骨架標註 |
| `trajectory.mp4` | 依該動作設定繪製關鍵點移動軌跡 |
| `result.json` | 完整量測資料（見第 5 節） |

網頁路徑：`/Pose`（動作分析頁）。亦可直接呼叫 `POST /analyze/video`。

### 3.4 逐幀量測內容

每一分析幀包含：

- **landmarks**：MediaPipe 最多 33 個人體節點（正規化座標 + 像素座標 + visibility / presence / status）
- **jointAngles**：依動作設定輸出的角度或位置量（欄位因動作而異）
- **derivedPoints**：衍生點（如肩中心、髖中心、身體中心、足部中心等）
- **trajectoryPoints**：該動作追蹤的關鍵點，含位移／速度／加速度／方向

### 3.5 軌跡摘要（trajectorySummary）

整段影片對各追蹤點彙總：

- `pointCount`：有效點數
- `totalDisplacementNormalized`：路徑總位移（正規化）
- `maxVelocityNormalizedPerSec`：最大速度
- `start` / `end`：起點、終點座標

### 3.6 資料品質警告（warnings）

僅反映拍攝／偵測品質，**不是**動作評語。

| code | 含義 |
|------|------|
| POSE_NOT_DETECTED | 部分或全部分析幀未偵測到人體 |
| LOW_FPS | FPS 低於該動作建議值 |
| UNSUPPORTED_CAMERA_VIEW | 角度不在建議清單 |
| MULTIPLE_PEOPLE_DETECTED | 偵測到多人，僅使用第一人 |
| LOW_LANDMARK_VISIBILITY | 主要關節可見度偏低 |
| BODY_OUT_OF_FRAME | 軀幹節點接近或超出畫面 |
| MOTION_BLUR | 畫面模糊，可能影響定位 |
| LOW_WRIST_VISIBILITY | 手腕可見度偏低（與腕部追蹤相關動作） |

### 3.7 landmark.status

| 值 | 解讀 |
|----|------|
| valid | 可信，可作為量測 |
| low_visibility | 可見度偏低，慎用 |
| estimated | 估計值 |
| missing | 缺測 |

---

## 4. 各動作量測細項

以下「主要節點」為品質評估與重點關注用的 `primaryLandmarks`；實際每幀仍會輸出完整 landmarks（有偵測到時）。  
「角度／量測」對應 JSON 的 `jointAngles`；「軌跡追蹤點」對應 `trajectoryPoints`／`trajectorySummary`。

慣用側相關命名說明：

- **throwing***／**serving***／**racketSide***／**dominant***：依 `dominantSide` 對應慣用手（或持拍側）一側
- **lead***／**trail***：依慣用側推導的前導／後側肢段

### 4.1 健身／深蹲（fitness · squat）

| 項目 | 內容 |
|------|------|
| 建議拍攝 | front、side_left、side_right |
| 建議最低 FPS | 30 |
| 主要節點 | 肩、髖、膝、踝、踵、腳尖（左右） |
| 角度／量測 | `leftKneeAngleDeg`、`rightKneeAngleDeg`、`leftHipAngleDeg`、`rightHipAngleDeg`、`leftAnkleAngleDeg`、`rightAnkleAngleDeg`、`trunkLeanAngleDeg` |
| 軌跡追蹤 | hipCenter、leftKnee、rightKnee、leftAnkle、rightAnkle |
| 解讀提示 | 膝角越小通常蹲越深；可對照軀幹傾角與髖角觀察前後倒趨勢 |

### 4.2 健身／硬舉（fitness · deadlift）

| 項目 | 內容 |
|------|------|
| 建議拍攝 | front、side_left、side_right |
| 建議最低 FPS | 30 |
| 主要節點 | 肩、髖、膝、踝、腕（左右） |
| 角度／量測 | `leftHipAngleDeg`、`rightHipAngleDeg`、`leftKneeAngleDeg`、`rightKneeAngleDeg`、`trunkLeanAngleDeg` |
| 軌跡追蹤 | shoulderCenter、hipCenter、leftWrist、rightWrist |
| 解讀提示 | 適合觀察髖／膝伸展與軀幹傾角隨時間變化；手腕軌跡可輔助看槓鈴／手位移 |

### 4.3 健身／弓箭步（fitness · lunge）

| 項目 | 內容 |
|------|------|
| 建議拍攝 | front、side_left、side_right |
| 建議最低 FPS | 30 |
| 主要節點 | 髖、膝、踝、踵、腳尖（左右） |
| 角度／量測 | `leftKneeAngleDeg`、`rightKneeAngleDeg`、`leftHipAngleDeg`、`rightHipAngleDeg`、`pelvisTiltAngleDeg`、`trunkLeanAngleDeg` |
| 軌跡追蹤 | hipCenter、leftKnee、rightKnee、leftAnkle、rightAnkle |
| 解讀提示 | 可比較前／後膝角度與骨盆傾斜、軀幹傾角 |

### 4.4 羽球／殺球（badminton · smash）

| 項目 | 內容 |
|------|------|
| 建議拍攝 | rear_diagonal_left／right、side_left／right、rear |
| 建議最低 FPS | 30 |
| 主要節點 | 肩、肘、腕、髖、膝、踝（左右） |
| 角度／量測 | `racketSideShoulderAngleDeg`、`racketSideElbowAngleDeg`、`racketSideWristPosition`、`shoulderTiltAngleDeg`、`pelvisTiltAngleDeg`、`trunkLeanAngleDeg` |
| 軌跡追蹤 | racketSideWrist、racketSideElbow、racketSideShoulder、hipCenter |
| 解讀提示 | 重點在持拍側手臂路徑與肩／骨盆／軀幹傾角 |

### 4.5 羽球／高遠球（badminton · clear）

| 項目 | 內容 |
|------|------|
| 建議拍攝 | 同殺球 |
| 建議最低 FPS | 30 |
| 主要節點 | 同殺球 |
| 角度／量測 | 同殺球（持拍側肩／肘／腕位置 + 肩傾／骨盆傾／軀幹傾） |
| 軌跡追蹤 | 同殺球 |
| 解讀提示 | 與殺球共用量測欄位，便於同類揮拍比較；不自動區分技術好壞 |

### 4.6 網球／正手（tennis · forehand）

| 項目 | 內容 |
|------|------|
| 建議拍攝 | side_left／right、front_diagonal_left／right |
| 建議最低 FPS | 30 |
| 主要節點 | 肩、肘、腕、髖、膝、踝（左右） |
| 角度／量測 | `dominantShoulderAngleDeg`、`dominantElbowAngleDeg`、`dominantWristPosition`、`shoulderCenterPosition`、`hipCenterPosition` |
| 軌跡追蹤 | dominantWrist、dominantElbow、shoulderCenter、hipCenter |
| 解讀提示 | 慣用側手臂與軀幹中心相對位置／軌跡為主要觀察重點 |

### 4.7 網球／反手（tennis · backhand）

| 項目 | 內容 |
|------|------|
| 建議拍攝 | 同正手 |
| 建議最低 FPS | 30 |
| 主要節點 | 同正手 |
| 角度／量測 | 同正手 |
| 軌跡追蹤 | 同正手 |
| 解讀提示 | 欄位與正手一致；請正確設定 `dominantSide`（及雙手反手時的拍攝角度） |

### 4.8 網球／發球（tennis · serve）

| 項目 | 內容 |
|------|------|
| 建議拍攝 | side_left／right、front |
| 建議最低 FPS | 30 |
| 主要節點 | 鼻、肩、肘、腕、髖、膝、踝（左右） |
| 角度／量測 | `servingShoulderAngleDeg`、`servingElbowAngleDeg`、`servingWristHeightNormalized`、`leftKneeAngleDeg`、`rightKneeAngleDeg`、`trunkLeanAngleDeg` |
| 軌跡追蹤 | servingWrist、servingElbow、nonServingWrist、hipCenter |
| 解讀提示 | `servingWristHeightNormalized` 可觀察揮臂高度變化；雙膝角與軀幹傾角可看下肢與軀幹配合 |

### 4.9 棒球／投球（baseball · pitch）

| 項目 | 內容 |
|------|------|
| 建議拍攝 | side_left／right、front_diagonal_left／right |
| 建議最低 FPS | **60**（快速動作建議較高幀率） |
| 主要節點 | 肩、肘、腕、髖、膝、踝（左右） |
| 角度／量測 | `throwingShoulderAngleDeg`、`throwingElbowAngleDeg`、`throwingWristPosition`、`leadKneeAngleDeg`、`trailKneeAngleDeg`、`trunkLeanAngleDeg`、`shoulderTiltAngleDeg`、`pelvisTiltAngleDeg` |
| 軌跡追蹤 | throwingWrist、throwingElbow、leadAnkle、leadKnee、shoulderCenter、hipCenter |
| 解讀提示 | 投擲側手臂與前導腿（lead）軌跡／角度為重點；低 FPS 易漏影格 |

### 4.10 棒球／打擊（baseball · bat）

| 項目 | 內容 |
|------|------|
| 建議拍攝 | side_left／right、front_diagonal_left／right |
| 建議最低 FPS | **60** |
| 主要節點 | 肩、肘、腕、髖、膝、踝（左右） |
| 角度／量測 | `leftElbowAngleDeg`、`rightElbowAngleDeg`、`leftKneeAngleDeg`、`rightKneeAngleDeg`、`shoulderTiltAngleDeg`、`pelvisTiltAngleDeg`、`trunkLeanAngleDeg` |
| 軌跡追蹤 | leftWrist、rightWrist、shoulderCenter、hipCenter、leadKnee |
| 解讀提示 | 雙腕軌跡可觀察揮棒路徑；肩／骨盆／軀幹傾角可看旋轉與前傾 |

---

## 5. 結果 JSON 結構摘要

成功時主要欄位：

```text
schemaVersion, analysisId, success
movement          → sportType, movementType, cameraView, dominantSide
videoInfo         → fps, width, height, durationSec, totalFrames, analyzedFrameCount, frameInterval
detectionInfo     → poseModel, averagePoseConfidence, missingFrameCount
frames[]          → frameIndex, timeSec, poseDetected, landmarks, jointAngles, derivedPoints, trajectoryPoints
trajectorySummary → 各追蹤點彙總
outputFiles       → skeletonVideoUrl, trajectoryVideoUrl, rawJsonUrl
warnings[]        → code, message
```

座標約定：

- `x`、`y`：相對畫面的正規化座標（約 0～1）；`y` 向下為正
- `pixelX`、`pixelY`：像素座標
- 軌跡位移／速度等為**正規化單位**（非公尺）

詳細 request／response 契約見 [api-contract.md](./api-contract.md)。

---

## 6. 擴充新動作

在 `src/pose-api/configs/movements/` 新增 JSON，指定：

- `sportType`、`movementType`
- `primaryLandmarks`
- `anglesToOutput`（須為管線已支援的角度／位置鍵名）
- `trajectoryLandmarks`
- `suggestedCameraViews`、`suggestedMinFps`

通常無需修改角度計算機本體；中文顯示名稱可於 `definition_provider` 的 label 對照表補強。

---

## 7. 相關文件

| 文件 | 說明 |
|------|------|
| [README.md](../README.md) | 專案總覽與啟動方式 |
| [api-contract.md](./api-contract.md) | HTTP API 契約 |
| `src/pose-api/configs/movements/` | 各動作量測定義 |
| `src/pose-api/configs/camera_views.json` | 各拍攝角度偏好節點 |
| `src/pose-api/configs/quality_thresholds.json` | 品質警告門檻 |
