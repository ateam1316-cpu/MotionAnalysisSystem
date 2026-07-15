# Motion Analysis System

動作偵測分析系統 — C# ASP.NET Core MVC + Python FastAPI + MediaPipe Pose Detection。

輸出客觀節點／角度／軌跡資料，**不評價動作品質**。

## 專案結構

```text
MotionAnalysisSystem/
├─ src/
│  ├─ MotionAnalysis.Web/    # C# MVC 前端
│  └─ pose-api/              # Python FastAPI 姿態分析管線
├─ docs/
└─ README.md
```

## 啟動方式

需要同時啟動兩個服務。

### 1. Python Pose API（終端機一）

```bash
cd src/pose-api
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

確認：`http://127.0.0.1:8000/docs` 或 `http://127.0.0.1:8000/movements`

### 2. C# MVC（終端機二）

```bash
cd src/MotionAnalysis.Web
dotnet run
```

開啟網站後進入 `/Pose/Index`（導覽列「動作分析」）。動作下拉會向 Pose API 的 `GET /movements` 動態載入。

Pose API 位址可於 `appsettings.json` 的 `PoseApi:BaseUrl` 設定。

## 支援動作

- 健身：深蹲、硬舉、弓箭步
- 羽球：殺球、高遠球
- 網球：正手、反手、發球
- 棒球：投球、打擊

新增動作：在 `pose-api/configs/movements/` 加入 JSON 即可（無需改角度計算機）。

## 功能（schemaVersion 1.0）

- 依運動／動作／拍攝角度／慣用側分析
- MediaPipe 33 點 + status／可見度過濾／平滑
- 關節角度、位置輸出、位移／速度／方向
- 可選骨架標註影片與關節軌跡影片
- 資料品質 warnings（含出框、模糊、腕部可見度等；非動作評分）

## 文件

- [運動動作分析功能說明](docs/現階段動作分析功能.md)
- [API Contract](docs/api-contract.md)
- [Third-Party Licenses](docs/THIRD_PARTY_LICENSES.md)
