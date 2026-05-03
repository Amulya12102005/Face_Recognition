console.log("JS LOADED ✅");
const registerVideo = document.getElementById("camera-video");
const canvas = document.getElementById("snapshot-canvas");
const message = document.getElementById("message");
const registerStatus = document.getElementById("register-status");
const detectedUsers = document.getElementById("detected-users");
const userList = document.getElementById("user-list");
const userCount = document.getElementById("user-count");
const firebaseState = document.getElementById("firebase-state");

let browserStream = null;
let detectionTimer = null;

// 🔔 MESSAGE
function setMessage(text, type = "") {
  message.textContent = text;
  message.className = `message ${type}`;
}

// 🔗 API
async function apiRequest(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json();
  if (!res.ok) throw new Error(data.message || "Error");
  return data;
}

// 🎥 CAMERA
async function startCamera() {
  if (browserStream) return;

  browserStream = await navigator.mediaDevices.getUserMedia({
    video: true,
    audio: false,
  });

  registerVideo.srcObject = browserStream;
  await registerVideo.play();
  registerStatus.textContent = "Camera ON";
}

function stopCamera() {
  if (detectionTimer) clearInterval(detectionTimer);

  if (browserStream) {
    browserStream.getTracks().forEach((t) => t.stop());
    browserStream = null;
  }

  registerVideo.srcObject = null;
  registerStatus.textContent = "Stopped";
}

// 📸 SNAPSHOT
function snapshot() {
  const w = registerVideo.videoWidth;
  const h = registerVideo.videoHeight;

  if (!w || !h) {
    throw new Error("Camera not ready");
  }

  canvas.width = w;
  canvas.height = h;

  const ctx = canvas.getContext("2d");
  ctx.drawImage(registerVideo, 0, 0, w, h);

  const image = canvas.toDataURL("image/jpeg");

  if (!image || image.length < 100) {
    throw new Error("Empty image captured");
  }

  return image;
}

// 👤 REGISTER USER (FINAL FIXED)
async function registerUser() {
  try {
    const input = document.getElementById("name");
    const name = input.value.trim();

    if (!name) {
      setMessage("Enter name", "error");
      return;
    }

    await startCamera();

    const image = snapshot();

    await apiRequest("/api/register", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ name, image })
    });

    setMessage(`User "${name}" Registered ✅`, "success");

    // 🔥 CLEAR INPUT AFTER SUCCESS
    input.value = "";

    loadUsers();

  } catch (err) {
    setMessage(err.message, "error");
  }
}

// 🔍 DETECTION
async function detectFrame() {
  try {
    const image = snapshot();

    const result = await apiRequest("/api/detect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image }),
    });

    renderDetection(result);

  } catch (err) {
    console.log("⚠️ Skipped frame:", err.message);
  }
}

// 📊 DETECTION UI
function renderDetection(result) {
  const detected = result.detected_users || [];

  firebaseState.textContent = result.firebase?.enabled
    ? "Firebase active"
    : "Firebase error";

  if (!result.matches || !result.matches.length) {
    detectedUsers.textContent = "No face detected";
    return;
  }

  if (!detected.length) {
    detectedUsers.textContent = "Face not registered";
    return;
  }

  detectedUsers.innerHTML = detected.map(u => `
    <div>
      <b>${u.name}</b><br/>
      Score: ${u.score}
    </div>
  `).join("<hr>");
}

// ▶ START DETECTION
async function startDetection() {
  await startCamera();

  if (detectionTimer) clearInterval(detectionTimer);

  detectionTimer = setInterval(detectFrame, 500);
}

// 👥 LOAD USERS
async function loadUsers() {
  const result = await apiRequest("/api/users");
  const users = result.users || [];

  userCount.textContent = `${users.length} users`;

  if (!users.length) {
    userList.innerHTML = "<p>No users</p>";
    return;
  }

  userList.innerHTML = users.map(u => `
    <div><b>${u.name}</b></div>
  `).join("");
}

// 🔄 FIREBASE STATUS
async function refreshStatus() {
  try {
    const res = await apiRequest("/api/status");
    firebaseState.textContent = res.firebase?.enabled
      ? "Firebase active"
      : "Firebase error";
  } catch {
    firebaseState.textContent = "Error";
  }
}

// 🎯 BUTTONS
window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("start-camera").addEventListener("click", startCamera);
  document.getElementById("stop-camera").addEventListener("click", stopCamera);
  document.getElementById("start-detection").addEventListener("click", startDetection);
  document.getElementById("register-user").addEventListener("click", registerUser);
});

// INIT
loadUsers();
refreshStatus();
setInterval(refreshStatus, 5000);

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/static/sw.js")
    .then(() => console.log("SW registered"))
    .catch(err => console.log("SW error:", err));
}