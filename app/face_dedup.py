from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

SIMILARITY_THRESHOLD = 0.88

_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


@dataclass
class FaceDetectionResult:
    unique_total: int
    new_faces: int
    faces_in_frame: int
    annotated_jpeg: bytes


def _embedding(face_gray: np.ndarray) -> np.ndarray:
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
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Could not decode image frame.")

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = _cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(48, 48))

    new_embeddings: list[list[float]] = []
    new_faces = 0

    for x, y, w, h in faces:
        crop = gray[y : y + h, x : x + w]
        embedding = _embedding(crop)
        is_new = not _matches_known(embedding, known_embeddings + new_embeddings)
        if is_new:
            new_embeddings.append(embedding.tolist())
            new_faces += 1
            color = (16, 185, 129)
            label = "New"
        else:
            color = (100, 116, 139)
            label = "Known"

        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        cv2.putText(
            frame,
            label,
            (x, y - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1,
            cv2.LINE_AA,
        )

    unique_total += new_faces
    cv2.putText(
        frame,
        f"Unique people: {unique_total}",
        (12, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (16, 185, 129),
        2,
        cv2.LINE_AA,
    )
    if new_faces:
        cv2.putText(
            frame,
            f"+{new_faces} new this frame",
            (12, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (52, 211, 153),
            1,
            cv2.LINE_AA,
        )

    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise ValueError("Failed to encode annotated frame.")

    return (
        FaceDetectionResult(
            unique_total=unique_total,
            new_faces=new_faces,
            faces_in_frame=len(faces),
            annotated_jpeg=encoded.tobytes(),
        ),
        new_embeddings,
    )
