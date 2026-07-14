# Motion Analysis System

動作偵測分析系統 MVP — C# ASP.NET Core MVC + Python FastAPI + MediaPipe Pose Detection。

## 專案結構

```text
MotionAnalysisSystem/
├─ src/
│  ├─ MotionAnalysis.Web/    # C# MVC 前端
│  └─ pose-api/              # Python FastAPI 姿態分析
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

確認：`http://127.0.0.1:8000/docs`

### 2. C# MVC（終端機二）

```bash
cd src/MotionAnalysis.Web
dotnet run
```

開啟網站後進入 `/Pose/Index`，上傳含人體的影片進行分析。

## 功能

- 上傳影片至 C# MVC 頁面
- C# 轉送影片至 Python FastAPI
- MediaPipe 擷取 33 個人體姿態節點
- 計算左膝、右膝、左髖、右髖角度
- 頁面顯示 JSON 分析結果

## 文件

- [API Contract](docs/api-contract.md)
- [Third-Party Licenses](docs/THIRD_PARTY_LICENSES.md)
