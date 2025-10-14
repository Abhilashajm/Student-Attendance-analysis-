let video = document.getElementById("video");
let startBtn = document.getElementById("startBtn");
let stopBtn = document.getElementById("stopBtn");
let logoutBtn = document.getElementById("logoutBtn");
let recognizedEl = document.getElementById("recognized");
let confBar = document.getElementById("confidenceBar");
let infoBox = document.getElementById("info");

let stream;
let interval;
let activeStudent = null;

// --------------------- START CAMERA ---------------------
startBtn.onclick = async (e) => {
  e.preventDefault();
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true });
    video.srcObject = stream;
    infoBox.textContent = "Camera started. Detecting faces...";
    captureLoop();
  } catch (err) {
    Swal.fire({
      icon: "error",
      title: "Unable to access camera",
      text: err.message,
      position: "center"
    });
  }
};

// --------------------- STOP CAMERA ---------------------
stopBtn.onclick = (e) => {
  e.preventDefault();
  stopCamera();
  Swal.fire({
    icon: "info",
    title: "Camera stopped",
    timer: 1000,
    position: "center",
    showConfirmButton: false
  });
};

function stopCamera() {
  if (interval) clearInterval(interval);
  if (stream) stream.getTracks().forEach(t => t.stop());
  stream = null;
  video.srcObject = null;
  infoBox.textContent = "Camera stopped";
}

// --------------------- CAPTURE LOOP ---------------------
function captureLoop() {
  interval = setInterval(async () => {
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    const imgData = canvas.toDataURL("image/jpeg");

    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: imgData })
      });

      const j = await res.json();
      handleResult(j);
    } catch (err) {
      console.error("Recognition error:", err);
    }
  }, 4000); // every 4 seconds
}

// --------------------- HANDLE RESPONSE ---------------------
function handleResult(j) {
  if (j.status === "ok") {
    const name = j.name;
    recognizedEl.textContent = name;
    confBar.style.width = "100%";
    confBar.textContent = "Matched";
    confBar.classList.add("bg-success");
    infoBox.textContent = `Attendance marked for ${name} at ${new Date().toLocaleTimeString()}`;

    if (!activeStudent || activeStudent !== j.student_id) {
      activeStudent = j.student_id;
      logoutBtn.disabled = false;

      Swal.fire({
        icon: "success",
        title: `✅ Attendance marked for ${name}`,
        position: "center",
        timer: 2000,
        showConfirmButton: false
      });
    }

  } else if (j.status === "unknown") {
    recognizedEl.textContent = "Unknown";
    confBar.style.width = "50%";
    confBar.textContent = "Unknown";
    confBar.classList.remove("bg-success");
    confBar.classList.add("bg-danger");
    infoBox.textContent = "⚠️ Unknown person detected";

    Swal.fire({
      icon: "error",
      title: "❌ Unknown person detected!",
      position: "center",
      timer: 1500,
      showConfirmButton: false
    });

  } else if (j.status === "error") {
    infoBox.textContent = j.message || "No face detected";
    confBar.style.width = "20%";
    confBar.textContent = "No face";
    confBar.classList.remove("bg-success");
    confBar.classList.add("bg-warning");
  }
}

// --------------------- MANUAL LOGOUT ---------------------
logoutBtn.onclick = async () => {
  if (!activeStudent) {
    return Swal.fire({
      icon: "info",
      title: "No active student",
      position: "center"
    });
  }

  const res = await fetch("/api/logout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ student_id: activeStudent })
  });

  const j = await res.json();
  if (j.status === "ok") {
    Swal.fire({
      icon: "success",
      title: "✅ Logout recorded",
      position: "center",
      timer: 1500,
      showConfirmButton: false
    });
  } else {
    Swal.fire({
      icon: "error",
      title: j.message || "Logout error",
      position: "center"
    });
  }

  activeStudent = null;
  logoutBtn.disabled = true;
  recognizedEl.textContent = "None";
  confBar.style.width = "0%";
  confBar.textContent = "0%";
  confBar.classList.remove("bg-success", "bg-danger", "bg-warning");
  infoBox.textContent = "Waiting for recognition...";
};
