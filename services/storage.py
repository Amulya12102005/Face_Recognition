import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import cv2


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FACES_DIR = DATA_DIR / "faces"
REGISTRY_FILE = DATA_DIR / "registry.json"


@dataclass
class RegisteredFace:
    name: str
    embedding: List[float]
    image_path: str
    created_at: str


class FaceRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        FACES_DIR.mkdir(parents=True, exist_ok=True)
        if not REGISTRY_FILE.exists():
            REGISTRY_FILE.write_text("[]", encoding="utf-8")

    def _load(self) -> List[Dict]:
        with self._lock:
            return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))

    def _save(self, payload: List[Dict]) -> None:
        with self._lock:
            REGISTRY_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list_users(self) -> List[Dict]:
        users = self._load()
        return [
            {
                "name": item["name"],
                "created_at": item["created_at"],
                "image_path": item["image_path"],
            }
            for item in users
        ]

    def get_user(self, name: str) -> Optional[Dict]:
        for item in self._load():
            if item["name"].lower() == name.lower():
                return {
                    "name": item["name"],
                    "created_at": item["created_at"],
                    "image_path": item["image_path"],
                }
        return None

    def embeddings(self) -> List[RegisteredFace]:
        return [RegisteredFace(**item) for item in self._load()]

    def delete_user(self, name: str) -> Optional[Dict]:
        users = self._load()
        kept = []
        removed = None

        for item in users:
            if item["name"].lower() == name.lower() and removed is None:
                removed = {
                    "name": item["name"],
                    "created_at": item["created_at"],
                    "image_path": item["image_path"],
                }
                image_file = BASE_DIR / item["image_path"]
                if image_file.exists():
                    image_file.unlink()
                continue
            kept.append(item)

        if removed is None:
            return None

        self._save(kept)
        return removed

    def upsert(self, name: str, embedding: List[float], frame) -> Dict:
        timestamp = datetime.now(timezone.utc).isoformat()
        safe_name = "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_")
        filename = f"{safe_name or 'user'}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        image_path = FACES_DIR / filename
        cv2.imwrite(str(image_path), frame)

        users = self._load()
        updated = False
        for item in users:
            if item["name"].lower() == name.lower():
                item["embedding"] = embedding
                item["image_path"] = str(image_path.relative_to(BASE_DIR)).replace("\\", "/")
                item["created_at"] = timestamp
                updated = True
                break

        if not updated:
            users.append(
                {
                    "name": name,
                    "embedding": embedding,
                    "image_path": str(image_path.relative_to(BASE_DIR)).replace("\\", "/"),
                    "created_at": timestamp,
                }
            )

        self._save(users)
        return {
            "name": name,
            "created_at": timestamp,
            "image_path": str(image_path.relative_to(BASE_DIR)).replace("\\", "/"),
        }
