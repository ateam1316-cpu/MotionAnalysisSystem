# Pose Analysis API

Python FastAPI 服務，負責接收影片並執行 MediaPipe Pose Detection。

## 環境需求

- Python 3.10+
- 建議使用虛擬環境

## 安裝

```bash
cd src/pose-api
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

## 啟動

```bash
uvicorn main:app --reload --port 8000
```

## API

- `GET /` — 健康檢查
- `POST /analyze/video` — 上傳影片，回傳姿態節點與關節角度 JSON

Swagger UI：`http://127.0.0.1:8000/docs`
