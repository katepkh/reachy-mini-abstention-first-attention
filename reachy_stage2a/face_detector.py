"""RAM-only local face-position extraction.

Frames enter :meth:`FacePositionDetector.observe`, are reduced immediately to
numbers, and are never returned, encoded, displayed or written.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .calibration import face_center_to_heading
from .models import FaceObservation


class FacePositionDetector:
    """OpenCV YuNet detector producing no identity or biometric embedding."""

    MODEL_PATH = (
        Path(__file__).resolve().parents[1]
        / "models"
        / "face_detection_yunet_2023mar.onnx"
    )
    MODEL_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
    SCORE_THRESHOLD = 0.90
    NMS_THRESHOLD = 0.30
    TOP_K = 5000
    MAX_ANALYSIS_WIDTH = 640

    def __init__(self) -> None:
        self._classifier: Any | None = None
        self._input_size: tuple[int, int] | None = None

    def _load(self) -> Any:
        if self._classifier is None:
            import cv2

            if not self.MODEL_PATH.is_file():
                raise RuntimeError("LOCAL_FACE_MODEL_UNAVAILABLE")
            self._classifier = cv2.FaceDetectorYN.create(
                str(self.MODEL_PATH),
                "",
                (320, 320),
                self.SCORE_THRESHOLD,
                self.NMS_THRESHOLD,
                self.TOP_K,
            )
        return self._classifier

    @staticmethod
    def _confidence(raw_score: float) -> float:
        # YuNet emits a bounded detector score, not an identity probability.
        return min(1.0, max(0.0, float(raw_score)))

    def observe(self, bgr_frame: Any) -> FaceObservation:
        started = time.perf_counter()
        captured = datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")
        captured_monotonic = time.perf_counter()
        try:
            import cv2

            detector = self._load()
            source_height, source_width = bgr_frame.shape[:2]
            if source_width <= 0 or source_height <= 0:
                raise ValueError("EMPTY_FRAME")
            analysis_frame = bgr_frame
            if source_width > self.MAX_ANALYSIS_WIDTH:
                scale = self.MAX_ANALYSIS_WIDTH / float(source_width)
                analysis_frame = cv2.resize(
                    bgr_frame,
                    (self.MAX_ANALYSIS_WIDTH, max(1, int(round(source_height * scale)))),
                    interpolation=cv2.INTER_AREA,
                )
            height, width = analysis_frame.shape[:2]
            input_size = (int(width), int(height))
            if self._input_size != input_size:
                detector.setInputSize(input_size)
                self._input_size = input_size
            _status, faces = detector.detect(analysis_frame)
            count = 0 if faces is None else int(len(faces))
            if count == 0:
                return FaceObservation(
                    captured, captured_monotonic, False, 0, None, None, None,
                    0.0, None, (time.perf_counter() - started) * 1000.0, True, "",
                )
            selected = max(faces, key=lambda face: float(face[-1]))
            x, y, w, h = (float(value) for value in selected[:4])
            right_eye_x, right_eye_y = (float(value) for value in selected[4:6])
            left_eye_x, left_eye_y = (float(value) for value in selected[6:8])
            raw_score = float(selected[-1])
            center_x = (x + w / 2.0) / float(width)
            center_y = (y + h / 2.0) / float(height)
            eye_midpoint_x = ((right_eye_x + left_eye_x) / 2.0) / float(width)
            eye_midpoint_y = ((right_eye_y + left_eye_y) / 2.0) / float(height)
            return FaceObservation(
                captured,
                captured_monotonic,
                True,
                count,
                center_x,
                center_y,
                face_center_to_heading(center_x),
                self._confidence(raw_score),
                raw_score,
                (time.perf_counter() - started) * 1000.0,
                True,
                "",
                eye_midpoint_x,
                eye_midpoint_y,
                int(source_width),
                int(source_height),
            )
        except Exception as exc:
            return FaceObservation(
                captured,
                captured_monotonic,
                False,
                0,
                None,
                None,
                None,
                0.0,
                None,
                (time.perf_counter() - started) * 1000.0,
                False,
                type(exc).__name__.upper()[:64],
            )
