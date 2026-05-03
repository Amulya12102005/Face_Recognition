import threading
from datetime import datetime
from typing import Dict, List, Optional

import cv2

from services.face_service import FaceRecognitionService
from services.firebase_service import FirebaseSyncService


class CameraManager:
    def __init__(
        self,
        face_service: FaceRecognitionService,
        firebase_service: Optional[FirebaseSyncService] = None,
    ) -> None:
        self.face_service = face_service
        self.firebase_service = firebase_service
        self._camera = None
        self._lock = threading.Lock()
        self._latest_matches: List[Dict] = []
        self._last_updated = None

    def _open_camera(self) -> cv2.VideoCapture:
        camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not camera.isOpened():
            camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            raise RuntimeError("Unable to open the default camera.")
        return camera

    def _ensure_camera(self) -> cv2.VideoCapture:
        with self._lock:
            if self._camera is None or not self._camera.isOpened():
                self._camera = self._open_camera()
            return self._camera

    def release(self) -> None:
        with self._lock:
            if self._camera is not None and self._camera.isOpened():
                self._camera.release()
            self._camera = None

    def restart(self) -> None:
        self.release()
        self._ensure_camera()

    def latest_status(self) -> Dict:
        return {
            "matches": self._latest_matches,
            "last_updated": self._last_updated,
        }

    def _annotate(self, frame, matches: List[Dict]):
        for match in matches:
            x, y, w, h = match["box"]
            known = match["name"] != "Unknown"
            color = (40, 180, 99) if known else (39, 65, 210)
            label = f'{match["name"]} ({match["score"]:.3f})'
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.rectangle(frame, (x, max(0, y - 28)), (x + w, y), color, -1)
            cv2.putText(
                frame,
                label,
                (x + 6, max(18, y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

        summary = "Detected" if any(item["name"] != "Unknown" for item in matches) else "Scanning"
        cv2.putText(
            frame,
            summary,
            (20, 34),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        return frame

    def mjpeg_stream(self):
        while True:
            camera = self._ensure_camera()
            ok, frame = camera.read()
            if not ok:
                self.release()
                continue

            matches = self.face_service.identify_faces(frame)
            self._latest_matches = matches
            self._last_updated = datetime.now().isoformat(timespec="seconds")
            if self.firebase_service is not None:
                self.firebase_service.sync_live_status(matches, self._last_updated)
                self.firebase_service.record_detections(matches, self._last_updated)

            annotated = self._annotate(frame, matches)
            ok, buffer = cv2.imencode(".jpg", annotated)
            if not ok:
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
            )
