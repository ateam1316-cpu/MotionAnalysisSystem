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
