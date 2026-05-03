import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import firebase_admin
from firebase_admin import credentials, db

from services.storage import BASE_DIR, FaceRegistry


class FirebaseSyncService:
    def __init__(self, registry: FaceRegistry, key_path: Optional[Path] = None) -> None:
        self.registry = registry
        self.key_path = key_path or BASE_DIR / "key.json"
        self.enabled = False
        self.error = None
        self._lock = threading.Lock()

        self._initialize()

    # 🔥 INITIALIZE FIREBASE
    def _initialize(self) -> None:
        if not self.key_path.exists():
            self.error = f"Firebase key file not found: {self.key_path.name}"
            print(self.error)
            return

        try:
            database_url = "https://facerecognition-2005-default-rtdb.asia-southeast1.firebasedatabase.app/"

            if not firebase_admin._apps:
                cred = credentials.Certificate(str(self.key_path))
                firebase_admin.initialize_app(
                    cred,
                    {"databaseURL": database_url},
                )

            self.enabled = True
            print("✅ Firebase Connected Successfully")

        except Exception as exc:
            self.error = f"Firebase initialization failed: {exc}"
            print(self.error)

    # 🔥 STATUS
    @property
    def status(self) -> Dict:
        return {
            "enabled": self.enabled,
            "error": self.error,
        }

    # 🔥 SAVE USER
    def sync_user(self, user: Dict) -> None:
        if not self.enabled:
            return

        try:
            db.reference("users").child(user["name"]).set(user)
        except Exception as e:
            print("❌ User sync error:", e)

    # 🔥 DELETE USER
    def delete_user(self, name: str) -> None:
        if not self.enabled:
            return

        try:
            db.reference("users").child(name).delete()
        except Exception as e:
            print("❌ Delete error:", e)

    # 🔥 MAIN DOOR CONTROL (FIXED)
    def sync_live_status(self, matches: List[Dict], timestamp: Optional[str]) -> None:
        if not self.enabled:
            print("❌ Firebase not enabled")
            return

        try:
            door_ref = db.reference("DOORLOCK")

            # 🚫 NO FACE → CLOSE
            if not matches:
                print("🚫 No face → CLOSE")
                door_ref.set({"DOOR": "CLOSE"})
                return

            # Filter known faces
            known = [m for m in matches if m["name"] != "Unknown"]

            # 🔥 STRONG MATCH ONLY
            face_match = any(m["score"] > 0.65 for m in known)

            print("Detected Faces:", known)
            print("Door Decision:", "OPEN" if face_match else "CLOSE")

            if face_match:
                door_ref.set({"DOOR": "OPEN"})
            else:
                door_ref.set({"DOOR": "CLOSE"})

            print("✅ Firebase updated")

        except Exception as e:
            print("❌ Firebase write error:", e)

    # 🔥 STORE DETECTIONS
    def record_detections(self, matches: List[Dict], timestamp: Optional[str]) -> None:
        if not self.enabled:
            return

        try:
            detections_ref = db.reference("detections")

            for match in matches:
                if match["name"] == "Unknown":
                    continue

                data = {
                    "name": match["name"],
                    "score": match["score"],
                    "time": timestamp,
                }

                detections_ref.push(data)

            print("✅ Detection stored")

        except Exception as e:
            print("❌ Detection error:", e)