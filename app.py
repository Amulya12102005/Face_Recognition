import os
from datetime import datetime

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from services.face_service import FaceRecognitionService
from services.firebase_service import FirebaseSyncService
from services.storage import FaceRegistry


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["PROPAGATE_EXCEPTIONS"] = False

    registry = FaceRegistry()
    firebase_service = FirebaseSyncService(registry)
    face_service = FaceRecognitionService(registry)

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "message": exc.description}), exc.code
        return exc

    @app.errorhandler(Exception)
    def handle_unexpected_exception(exc: Exception):
        if request.path.startswith("/api/"):
            app.logger.exception("Unhandled API error", exc_info=exc)
            return jsonify({"success": False, "message": "Internal server error."}), 500
        raise exc

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/users")
    def users():
        return jsonify({"users": registry.list_users()})

    @app.delete("/api/users/<path:name>")
    def delete_user(name: str):
        removed = registry.delete_user(name)
        if removed is None:
            return jsonify({"success": False, "message": "User not found."}), 404

        firebase_service.delete_user(removed["name"])
        return jsonify({"success": True, "message": f'{removed["name"]} deleted successfully.'})

    @app.get("/api/status")
    def status():
        return jsonify(
            {
                "matches": [],
                "last_updated": None,
                "firebase": firebase_service.status,
            }
        )

    @app.post("/api/register")
    def register():
        payload = request.get_json(silent=True) or {}
        name = (payload.get("name") or "").strip()
        image_data = payload.get("image")
        image_frames = payload.get("images") or []

        if not name:
            return jsonify({"success": False, "message": "Name is required."}), 400
        if not image_data and not image_frames:
            return jsonify({"success": False, "message": "Face image is required."}), 400

        try:
            if image_frames:
                result = face_service.register_user_from_frames(name, image_frames)
            else:
                result = face_service.register_user(name, image_data)
        except ValueError as exc:
            return jsonify({"success": False, "message": str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({"success": False, "message": str(exc)}), 500

        firebase_service.sync_user(result["user"])

        return jsonify({"success": True, **result})

    @app.post("/api/detect")
    def detect():
        payload = request.get_json(silent=True) or {}
        image_data = payload.get("image")
        if not image_data:
            return jsonify({"success": False, "message": "Live camera frame is required."}), 400

        try:
            matches = face_service.identify_from_image(image_data)
            detected_users = []
            for match in matches:
                if match["name"] == "Unknown":
                    continue
                detected_users.append(
                    {
                        **match,
                        "status": "Detected",
                        "user": registry.get_user(match["name"]),
                    }
                )
        except ValueError as exc:
            return jsonify({"success": False, "message": str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({"success": False, "message": str(exc)}), 500

        timestamp = datetime.now().isoformat(timespec="seconds")
        firebase_service.sync_live_status(matches, timestamp)
        firebase_service.record_detections(matches, timestamp)

        return jsonify(
            {
                "success": True,
                "matches": matches,
                "detected_users": detected_users,
                "last_updated": timestamp,
                "firebase": firebase_service.status,
            }
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",   # 🔥 IMPORTANT
        port=5000,
        debug=False,
        ssl_context="adhoc"
    )
