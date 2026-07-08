"""Assemble agent relay frames into on-disk MP4 recordings.

Frames arrive over HTTP one at a time (roughly one every couple of seconds),
so a recording is a low-frame-rate "timelapse" of the live feed. This keeps
CPU/storage cost minimal — no LiveKit Egress / Chrome service needed, we simply
reuse the JPEG frames already sent for people counting.

Encoding strategy:
  * If the ``ffmpeg`` binary is available we pipe the JPEG frames into it and
    produce H.264 (libx264) MP4 — plays inline in every browser.
  * Otherwise we fall back to OpenCV's VideoWriter (mp4v). The file still
    downloads and plays in desktop players such as VLC.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .recording_storage import ensure_recordings_dir, recording_file_path

logger = logging.getLogger(__name__)

# Playback frame rate for the assembled file. Frames come in slowly, so the
# result is a sped-up timelapse — fine for reviewing what happened on site.
OUTPUT_FPS = 4.0
# Finalize a recording automatically if no new frame arrives for this long.
IDLE_FINALIZE_SECONDS = 30
# Safety cap so a single file cannot grow unbounded (rotates to a new file).
MAX_FRAMES_PER_FILE = 20000
# OpenCV fallback codecs, tried in order.
FALLBACK_CODECS = ("avc1", "mp4v")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


def _jpeg_dimensions(jpeg: bytes) -> tuple[int, int]:
    """Return (width, height) of a JPEG, or (0, 0) if it cannot be decoded."""
    arr = np.frombuffer(jpeg, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        return 0, 0
    height, width = frame.shape[:2]
    return width, height


class FfmpegWriter:
    """Pipes JPEG frames to an ffmpeg process producing an H.264 MP4."""

    def __init__(self, path: Path, fps: float, ffmpeg_bin: str) -> None:
        self.path = path
        self.width = 0
        self.height = 0
        self._alive = True
        self._proc = subprocess.Popen(
            [
                ffmpeg_bin,
                "-y",
                "-hide_banner",
                "-loglevel", "error",
                "-f", "image2pipe",
                "-framerate", str(fps),
                "-i", "-",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-an",
                str(path),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def write(self, jpeg: bytes) -> bool:
        if not self._alive or self._proc.stdin is None:
            return False
        if self.width == 0:
            self.width, self.height = _jpeg_dimensions(jpeg)
        try:
            self._proc.stdin.write(jpeg)
            return True
        except (BrokenPipeError, OSError):
            self._alive = False
            return False

    def close(self) -> None:
        if self._proc.stdin is not None:
            try:
                self._proc.stdin.close()
            except OSError:
                pass
        try:
            self._proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self._proc.kill()


class OpenCvWriter:
    """Fallback writer using OpenCV's VideoWriter (mp4v/avc1)."""

    def __init__(self, path: Path, fps: float) -> None:
        self.path = path
        self.fps = fps
        self.width = 0
        self.height = 0
        self._writer: Any = None

    def _open(self, width: int, height: int) -> Any:
        for codec in FALLBACK_CODECS:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            writer = cv2.VideoWriter(str(self.path), fourcc, self.fps, (width, height))
            if writer.isOpened():
                logger.info("Recording %s opened with OpenCV codec %s", self.path.name, codec)
                return writer
            writer.release()
        logger.error("Could not open an OpenCV VideoWriter for %s", self.path)
        return None

    def write(self, jpeg: bytes) -> bool:
        arr = np.frombuffer(jpeg, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return False
        if self._writer is None:
            height, width = frame.shape[:2]
            width -= width % 2
            height -= height % 2
            if width <= 0 or height <= 0:
                return False
            self.width = width
            self.height = height
            self._writer = self._open(width, height)
            if self._writer is None:
                return False
        if frame.shape[1] != self.width or frame.shape[0] != self.height:
            frame = cv2.resize(frame, (self.width, self.height))
        self._writer.write(frame)
        return True

    def close(self) -> None:
        if self._writer is not None:
            self._writer.release()


@dataclass
class RecordingSession:
    recording_id: str
    code: str
    path: Path
    fps: float
    writer: Any = None
    frame_count: int = 0
    started_at: datetime = field(default_factory=_now)
    last_frame_at: datetime = field(default_factory=_now)


@dataclass
class RecordingStats:
    recording_id: str
    code: str
    frame_count: int
    fps: float
    width: int
    height: int
    started_at: datetime
    ended_at: datetime
    duration_seconds: float
    file_size: int


class RecordingManager:
    """Owns one open writer per polling-unit code while recording."""

    def __init__(self) -> None:
        self._sessions: dict[str, RecordingSession] = {}
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def _lock(self, code: str) -> asyncio.Lock:
        return self._locks[code]

    def has_session(self, code: str) -> bool:
        return code in self._sessions

    def _make_writer(self, path: Path, fps: float) -> Any:
        ffmpeg_bin = _ffmpeg_path()
        if ffmpeg_bin:
            try:
                return FfmpegWriter(path, fps, ffmpeg_bin)
            except Exception:  # noqa: BLE001 - fall back if ffmpeg fails to start
                logger.exception("ffmpeg writer failed to start; using OpenCV fallback")
        return OpenCvWriter(path, fps)

    async def start_session(self, code: str, recording_id: str) -> bool:
        async with self._lock(code):
            if code in self._sessions:
                return False
            ensure_recordings_dir()
            path = recording_file_path(recording_id)
            loop = asyncio.get_event_loop()
            writer = await loop.run_in_executor(None, self._make_writer, path, OUTPUT_FPS)
            self._sessions[code] = RecordingSession(
                recording_id=recording_id,
                code=code,
                path=path,
                fps=OUTPUT_FPS,
                writer=writer,
            )
            return True

    async def add_frame(self, code: str, jpeg: bytes) -> bool:
        async with self._lock(code):
            session = self._sessions.get(code)
            if session is None or session.writer is None:
                return False
            loop = asyncio.get_event_loop()
            ok = await loop.run_in_executor(None, session.writer.write, jpeg)
            if ok:
                session.frame_count += 1
                session.last_frame_at = _now()
            return ok

    async def finalize(self, code: str) -> RecordingStats | None:
        async with self._lock(code):
            session = self._sessions.pop(code, None)
            if session is None:
                return None
            return await self._finalize_session(session)

    async def _finalize_session(self, session: RecordingSession) -> RecordingStats:
        loop = asyncio.get_event_loop()
        if session.writer is not None:
            await loop.run_in_executor(None, session.writer.close)
        ended = _now()
        try:
            file_size = session.path.stat().st_size if session.path.is_file() else 0
        except OSError:
            file_size = 0
        duration = session.frame_count / session.fps if session.fps else 0.0
        width = getattr(session.writer, "width", 0)
        height = getattr(session.writer, "height", 0)
        return RecordingStats(
            recording_id=session.recording_id,
            code=session.code,
            frame_count=session.frame_count,
            fps=session.fps,
            width=width,
            height=height,
            started_at=session.started_at,
            ended_at=ended,
            duration_seconds=round(duration, 2),
            file_size=file_size,
        )

    def idle_codes(self, seconds: int = IDLE_FINALIZE_SECONDS) -> list[str]:
        cutoff = _now().timestamp() - seconds
        return [
            code
            for code, session in self._sessions.items()
            if session.last_frame_at.timestamp() < cutoff
        ]

    def frame_count(self, code: str) -> int:
        session = self._sessions.get(code)
        return session.frame_count if session else 0

    def active_codes(self) -> list[str]:
        return list(self._sessions.keys())


recording_manager = RecordingManager()
