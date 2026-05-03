# ONNX Face Recognition Flask App

This is a simple face recognition application built using ONNX models.

## Stack

- Flask for the web app
- OpenCV for camera access and ONNX inference wrappers
- YuNet ONNX model for face detection
- SFace ONNX model for face recognition

## Flow

1. Start the live camera in the browser.
2. Register a user using the live camera frame.
3. Start detection using the same live camera.
4. When a registered user is detected, the application shows that user as detected and stores the event in Firebase Realtime Database.

## Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` by default.

## Notes

- The application automatically downloads the required ONNX models into `models/` on first run.
- User embeddings are stored in `data/registry.json`.
- Registered snapshots are stored in `data/faces/`.
- Registration uses the live browser camera.
- Detection also uses the same live browser camera by sending frames to the Flask backend for ONNX inference.
- Put your Firebase service account in `key.json`. Registered users are written to Realtime Database `registered_users`, live state to `live_status/current`, and detections to `detections`.
