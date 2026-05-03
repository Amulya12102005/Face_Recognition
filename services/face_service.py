import base64
import binascii
import urllib.request
import time
from typing import Dict, List, Tuple

import cv2
import numpy as np

from services.storage import BASE_DIR, FaceRegistry


MODEL_DIR = BASE_DIR / "models"
DETECTOR_PATH = MODEL_DIR / "face_detection_yunet_2023mar.onnx"
RECOGNIZER_PATH = MODEL_DIR / "face_recognition_sface_2021dec.onnx"

MODEL_URLS = {
    DETECTOR_PATH: "https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx?download=true",
    RECOGNIZER_PATH: "https://huggingface.co/opencv/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx?download=true",
}


class FaceRecognitionService:
    COSINE_THRESHOLD = 0.42
    DETECTION_SCORE_THRESHOLD = 0.6

    def __init__(self, registry: FaceRegistry) -> None:
        self.registry = registry
        self._ensure_models()

        self.detector = cv2.FaceDetectorYN.create(
            str(DETECTOR_PATH),
            "",
            (320, 320),
            self.DETECTION_SCORE_THRESHOLD,
            0.3,
            5000,
        )

        self.recognizer = cv2.FaceRecognizerSF.create(str(RECOGNIZER_PATH), "")

    # 🔥 Download models if missing
    def _ensure_models(self) -> None:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)

        for path, url in MODEL_URLS.items():
            if path.exists() and path.stat().st_size > 1024:
                continue
            try:
                urllib.request.urlretrieve(url, str(path))
            except Exception as exc:
                raise RuntimeError(f"Failed to download model {path.name}") from exc

    # 🔥 SAFE IMAGE DECODE
    def _decode_base64_image(self, image_data: str) -> np.ndarray:
        if not image_data:
            raise ValueError("Empty image received")

        if "," in image_data:
            image_data = image_data.split(",", 1)[1]

        try:
            raw = base64.b64decode(image_data)
        except (binascii.Error, ValueError):
            raise ValueError("Invalid base64 image")

        np_arr = np.frombuffer(raw, np.uint8)

        if np_arr.size == 0:
            raise ValueError("Empty decoded image")

        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if frame is None:
            raise ValueError("Failed to decode image")

        return frame

    # 🔍 Detector
    def _run_detector(self, frame: np.ndarray):
        h, w = frame.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(frame)

        return faces if faces is not None else []

    def _detect_faces(self, frame: np.ndarray):
        faces = self._run_detector(frame)

        if len(faces) == 0:
            h, w = frame.shape[:2]
            resized = cv2.resize(frame, (int(w * 0.5), int(h * 0.5)))
            faces = self._run_detector(resized)

        return faces if faces is not None else []

    # 🔥 Embedding
    def _embedding_from_face(self, frame: np.ndarray, face) -> np.ndarray:
        aligned = self.recognizer.alignCrop(frame, face)
        feature = self.recognizer.feature(aligned).astype(np.float32)
        return cv2.normalize(feature, None)

    def _extract_primary_embedding(self, frame: np.ndarray) -> np.ndarray:
        faces = self._detect_faces(frame)

        if len(faces) == 0:
            raise ValueError("No face detected")

        face = faces[0]

        if float(face[2] * face[3]) < 2500:
            raise ValueError("Move closer to camera")

        return self._embedding_from_face(frame, face)

    # 👤 REGISTER USER (🔥 FIXED UNIQUE NAME)
    def register_user(self, name: str, image_data: str) -> Dict:
        frame = self._decode_base64_image(image_data)
        embedding = self._extract_primary_embedding(frame)

        embedding = embedding.flatten().astype(float).tolist()

        # 🔥 IMPORTANT FIX (NO OVERWRITE)
        unique_name = f"{name}_{int(time.time())}"

        user = self.registry.upsert(unique_name, embedding, frame)

        return {
            "message": f"{unique_name} registered successfully.",
            "user": user,
        }

    # 👤 MULTI-FRAME REGISTER
    def register_user_from_frames(self, name: str, image_data_list: List[str]) -> Dict:
        embeddings = []
        final_frame = None

        for image_data in image_data_list:
            try:
                frame = self._decode_base64_image(image_data)
                emb = self._extract_primary_embedding(frame)
                embeddings.append(emb)
                final_frame = frame
            except:
                continue

        if not embeddings:
            raise ValueError("No valid face frames")

        embedding = np.mean(np.vstack(embeddings), axis=0)
        embedding = cv2.normalize(embedding.reshape(1, -1), None)

        embedding = embedding.flatten().astype(float).tolist()

        unique_name = f"{name}_{int(time.time())}"

        user = self.registry.upsert(unique_name, embedding, final_frame)

        return {
            "message": f"{unique_name} registered successfully",
            "user": user,
        }

    # 🔍 IDENTIFY
    def identify_from_image(self, image_data: str) -> List[Dict]:
        frame = self._decode_base64_image(image_data)
        return self.identify_faces(frame)

    def _best_match(self, embedding: np.ndarray) -> Tuple[str, float]:
        best_name = "Unknown"
        best_score = -1.0

        for user in self.registry.embeddings():
            stored = np.asarray(user.embedding, dtype=np.float32).reshape(1, -1)
            stored = cv2.normalize(stored, None)

            score = float(
                self.recognizer.match(
                    embedding,
                    stored,
                    cv2.FaceRecognizerSF_FR_COSINE,
                )
            )

            if score > best_score:
                best_score = score
                best_name = user.name

        if best_score < self.COSINE_THRESHOLD:
            return "Unknown", best_score

        return best_name, best_score

    def identify_faces(self, frame: np.ndarray) -> List[Dict]:
        matches = []

        for face in self._detect_faces(frame):
            embedding = self._embedding_from_face(frame, face)
            name, score = self._best_match(embedding)

            x, y, w, h = [int(v) for v in face[:4]]

            matches.append({
                "name": name,
                "score": round(score, 3),
                "box": [x, y, w, h],
            })

        return matches