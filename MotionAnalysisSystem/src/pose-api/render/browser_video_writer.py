"""Video writers for download-only (mp4v) vs browser-playable (H.264) output.

OpenCV's default mp4v (MPEG-4 Part 2) is faster but not playable in HTML5 <video>.
Browser playback uses imageio-ffmpeg (libx264 + yuv420p + faststart).
"""

from __future__ import annotations

import subprocess
from typing import Optional, Protocol

import cv2
import imageio_ffmpeg
import numpy as np


class VideoFrameWriter(Protocol):
    def write(self, frame: np.ndarray) -> None: ...

    def __enter__(self) -> "VideoFrameWriter": ...

    def __exit__(self, exc_type, exc, tb) -> None: ...


class OpenCvMp4Writer:
    """Fast MPEG-4 Part 2 writer (suitable for download, not browser playback)."""

    def __init__(self, output_path: str, fps: float, width: int, height: int) -> None:
        self.output_path = output_path
        self.fps = max(float(fps), 1.0)
        self.width = width
        self.height = height
        self._writer: Optional[cv2.VideoWriter] = None

    def __enter__(self) -> "OpenCvMp4Writer":
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._writer = cv2.VideoWriter(
            self.output_path, fourcc, self.fps, (self.width, self.height)
        )
        if not self._writer.isOpened():
            raise RuntimeError("OpenCV VideoWriter failed to open.")
        return self

    def write(self, frame: np.ndarray) -> None:
        if self._writer is None:
            raise RuntimeError("OpenCvMp4Writer is not open.")
        self._writer.write(frame)

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._writer is not None:
            self._writer.release()
            self._writer = None


class BrowserVideoWriter:
    """H.264 writer that HTML5 <video> can play in modern browsers."""

    def __init__(self, output_path: str, fps: float, width: int, height: int) -> None:
        # libx264 / yuv420p requires even dimensions
        self.width = width - (width % 2)
        self.height = height - (height % 2)
        self.fps = max(float(fps), 1.0)
        self.output_path = output_path
        self._proc: Optional[subprocess.Popen] = None

    def __enter__(self) -> "BrowserVideoWriter":
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{self.width}x{self.height}",
            "-r",
            str(self.fps),
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-movflags",
            "+faststart",
            self.output_path,
        ]
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        return self

    def write(self, frame: np.ndarray) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise RuntimeError("BrowserVideoWriter is not open.")

        if frame.shape[0] != self.height or frame.shape[1] != self.width:
            frame = frame[: self.height, : self.width]

        if not frame.flags["C_CONTIGUOUS"] or frame.dtype != np.uint8:
            frame = np.ascontiguousarray(frame, dtype=np.uint8)

        try:
            self._proc.stdin.write(frame.tobytes())
        except BrokenPipeError as ex:
            err = self._stderr_text()
            raise RuntimeError(f"ffmpeg write failed: {err or ex}") from ex

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._proc is None:
            return

        stderr_data = b""
        try:
            if self._proc.stdin is not None:
                self._proc.stdin.close()
            stderr_data = self._proc.stderr.read() if self._proc.stderr else b""
            code = self._proc.wait(timeout=120)
        finally:
            self._proc = None

        if exc_type is not None:
            return

        if code != 0:
            err = stderr_data.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"ffmpeg exited with {code}: {err or 'unknown error'}")

    def _stderr_text(self) -> str:
        if self._proc is None or self._proc.stderr is None:
            return ""
        try:
            return self._proc.stderr.read().decode("utf-8", errors="replace").strip()
        except Exception:
            return ""


def create_video_writer(
    output_path: str,
    fps: float,
    width: int,
    height: int,
    *,
    browser_playable: bool,
) -> OpenCvMp4Writer | BrowserVideoWriter:
    if browser_playable:
        return BrowserVideoWriter(output_path, fps, width, height)
    return OpenCvMp4Writer(output_path, fps, width, height)
