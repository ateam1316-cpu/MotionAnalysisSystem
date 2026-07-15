from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import shutil
import os
import re

from pipeline.analysis_pipeline import AnalysisPipeline, STORAGE_ROOT
from movements.definition_provider import MovementDefinitionProvider

app = FastAPI(title="Motion Pose Analysis API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PUBLIC_BASE_URL = os.environ.get("POSE_API_PUBLIC_URL", "http://127.0.0.1:8000")
pipeline = AnalysisPipeline(public_base_url=PUBLIC_BASE_URL)
definition_provider = MovementDefinitionProvider()

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "service": "pose-api",
        "schemaVersion": "1.1",
    }


@app.get("/movements")
def list_movements():
    """List supported sport/movement definitions loaded from configs/movements."""
    return {
        "schemaVersion": "1.1",
        "movements": definition_provider.list_supported(),
    }


@app.post("/analyze/video")
async def analyze_video(
    file: UploadFile = File(...),
    sportType: str = Form("fitness"),
    movementType: str = Form("squat"),
    cameraView: str = Form("unknown"),
    dominantSide: str = Form("right"),
    frameInterval: int = Form(1),
    generateSkeletonVideo: bool = Form(True),
    generateTrajectoryVideo: bool = Form(True),
    browserPlayableVideo: bool = Form(False),
    modelVariant: str = Form("lite"),
    compareWithFull: bool = Form(False),
):
    """
    Receive a video plus movement metadata, run objective pose measurement,
    return schemaVersion 1.1 JSON (no quality scoring).

    When compareWithFull=true: runs Lite first, keeps source video, returns
    modelComparison.status=pending_full. Client should then call
    POST /analyze/{analysisId}/compare-full.
    """
    temp_path = None

    try:
        suffix = os.path.splitext(file.filename or "")[1] or ".mp4"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = temp_file.name

        result = pipeline.run(
            temp_path,
            sport_type=sportType.strip().lower(),
            movement_type=movementType.strip().lower(),
            camera_view=cameraView.strip().lower() or "unknown",
            dominant_side=dominantSide.strip().lower() or "right",
            frame_interval=frameInterval,
            generate_skeleton_video=generateSkeletonVideo,
            generate_trajectory_video=generateTrajectoryVideo,
            browser_playable_video=browserPlayableVideo,
            model_variant=(modelVariant or "lite").strip().lower(),
            compare_with_full=compareWithFull,
        )

        status = 200 if result.get("success", False) else 200
        return JSONResponse(content=result, status_code=status)

    except FileNotFoundError as ex:
        return JSONResponse(
            status_code=400,
            content={
                "schemaVersion": "1.1",
                "success": False,
                "message": str(ex),
                "warnings": [],
            },
        )
    except Exception as ex:
        return JSONResponse(
            status_code=500,
            content={
                "schemaVersion": "1.1",
                "success": False,
                "message": str(ex),
                "warnings": [],
            },
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            # When compare keeps a copy under storage/, temp upload can be removed.
            os.remove(temp_path)


@app.post("/analyze/{analysis_id}/compare-full")
async def compare_full(analysis_id: str):
    """Run Full model against a prior Lite compare session and return merged result."""
    if not UUID_RE.match(analysis_id):
        raise HTTPException(status_code=400, detail="Invalid analysisId.")

    try:
        result = pipeline.compare_full(analysis_id)
        return JSONResponse(content=result, status_code=200)
    except FileNotFoundError as ex:
        return JSONResponse(
            status_code=400,
            content={
                "schemaVersion": "1.1",
                "analysisId": analysis_id,
                "success": False,
                "message": str(ex),
                "warnings": [],
            },
        )
    except Exception as ex:
        return JSONResponse(
            status_code=500,
            content={
                "schemaVersion": "1.1",
                "analysisId": analysis_id,
                "success": False,
                "message": str(ex),
                "warnings": [],
            },
        )


@app.get("/files/{analysis_id}/{filename}")
def get_analysis_file(analysis_id: str, filename: str):
    if not UUID_RE.match(analysis_id):
        raise HTTPException(status_code=400, detail="Invalid analysisId.")
    if not SAFE_FILENAME_RE.match(filename) or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    path = os.path.realpath(os.path.join(STORAGE_ROOT, analysis_id, filename))
    root = os.path.realpath(STORAGE_ROOT)
    if not path.startswith(root + os.sep) and path != root:
        raise HTTPException(status_code=400, detail="Invalid path.")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found.")

    is_json = filename.endswith(".json")
    media_type = "application/json" if is_json else "video/mp4"
    browser_playable = os.path.isfile(
        os.path.join(os.path.dirname(path), ".browser_playable")
    )
    # inline only for H.264 browser-playable videos; otherwise prefer download
    disposition = (
        "inline" if (not is_json and browser_playable) else "attachment"
    )
    return FileResponse(
        path,
        media_type=media_type,
        filename=filename,
        content_disposition_type=disposition,
    )
