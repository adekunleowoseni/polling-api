from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

SIMILARITY_THRESHOLD = 0.88
DETECT_MAX_SIDE = 480


@dataclass
class FaceDetectionResult:
    unique_total: int
    new_faces: int
    faces_in_frame: int


@lru_cache(maxsize=1)
def _cv2():
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("OpenCV is not installed.") from exc
    if not hasattr(cv2, "CascadeClassifier"):
        raise RuntimeError(
            "OpenCV install is broken (no CascadeClassifier). "
            "Rebuild the image with opencv-python-headless and system libs."
        )
    return cv2


@lru_cache(maxsize=1)
def _cascade():
    cv2 = _cv2()
    path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    classifier = cv2.CascadeClassifier(path)
    if classifier.empty():
        raise RuntimeError(f"Failed to load Haar cascade from {path}")
    return classifier


def _embedding(face_gray: np.ndarray) -> np.ndarray:
    cv2 = _cv2()
    resized = cv2.resize(face_gray, (64, 64))
    vec = resized.astype(np.float32).flatten()
    norm = float(np.linalg.norm(vec))
    if norm <= 0:
        return vec
    return vec / norm


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


def _matches_known(embedding: np.ndarray, known: list[list[float]]) -> bool:
    for stored in known:
        if _cosine_similarity(embedding, np.array(stored, dtype=np.float32)) >= SIMILARITY_THRESHOLD:
            return True
    return False


def process_frame_with_face_dedup(
    image_bytes: bytes,
    known_embeddings: list[list[float]],
    unique_total: int,
) -> tuple[FaceDetectionResult, list[list[float]]]:
    cv2 = _cv2()
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Could not decode image frame.")

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    scale = 1.0
    detect_gray = gray
    if max(h, w) > DETECT_MAX_SIDE:
        scale = DETECT_MAX_SIDE / float(max(h, w))
        detect_gray = cv2.resize(gray, (int(w * scale), int(h * scale)))

    faces = _cascade().detectMultiScale(
        detect_gray,
        scaleFactor=1.15,
        minNeighbors=4,
        minSize=(28, 28),
    )

    new_embeddings: list[list[float]] = []
    new_faces = 0

    for x, y, fw, fh in faces:
        if scale != 1.0:
            x = int(x / scale)
            y = int(y / scale)
            fw = int(fw / scale)
            fh = int(fh / scale)
        crop = gray[y : y + fh, x : x + fw]
        if crop.size == 0:
            continue
        embedding = _embedding(crop)
        if not _matches_known(embedding, known_embeddings + new_embeddings):
            new_embeddings.append(embedding.tolist())
            new_faces += 1

    unique_total += new_faces
    return (
        FaceDetectionResult(
            unique_total=unique_total,
            new_faces=new_faces,
            faces_in_frame=len(faces),
        ),
        new_embeddings,
    )
