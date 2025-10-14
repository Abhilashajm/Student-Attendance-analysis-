let video = document.getElementById("video");
let startBtn = document.getElementById("startCapture");
let stopBtn = document.getElementById("stopCapture");
let takeBtn = document.getElementById("takeBtn");
let enrollBtn = document.getElementById("enrollBtn");
let countSpan = document.getElementById("countSpan");
let thumbs = document.getElementById("thumbs");
let stream;
let photos = []; // store base64 frames

// --------------------- START CAMERA ---------------------
startBtn.onclick = async (e) => {
  e.preventDefault();
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true });
    video.srcObject = stream;
    document.getElementById("cameraStatus").textContent = "Camera started";
    document.getElementById("cameraStatus").style.color = "green";
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
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
  video.srcObject = null;
  document.getElementById("cameraStatus").textContent = "Stopped";
  document.getElementById("cameraStatus").style.color = "red";
};

// --------------------- CAPTURE IMAGE ---------------------
takeBtn.onclick = (e) => {
  e.preventDefault();
  if (!stream) {
    return Swal.fire({
      icon: "warning",
      title: "Start camera first",
      position: "center",
      timer: 1500,
      showConfirmButton: false
    });
  }

  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0);
  const imgData = canvas.toDataURL("image/jpeg");
  photos.push(imgData);

  // thumbnail
  const img = document.createElement("img");
  img.src = imgData;
  img.className = "m-1 rounded border";
  img.style.width = "80px";
  thumbs.appendChild(img);
  countSpan.textContent = `${photos.length} images`;

  // 📸 mini popup for each capture
  Swal.fire({
    icon: "info",
    title: "📸 Captured successfully!",
    position: "center",
    timer: 800,
    showConfirmButton: false
  });
};

// --------------------- ENROLL BUTTON ---------------------
enrollBtn.onclick = async (e) => {
  e.preventDefault();

  const sid = document.getElementById("student_id").value.trim();
  const name = document.getElementById("name").value.trim();
  const course = document.getElementById("course").value.trim();
  const section = document.getElementById("section").value.trim();
  const room = document.getElementById("room").value.trim();

  if (!sid || !name) {
    return Swal.fire({
      icon: "error",
      title: "Please enter Student ID and Name",
      position: "center"
    });
  }
  if (photos.length < 3) {
    return Swal.fire({
      icon: "warning",
      title: "Capture at least 3 photos before enrolling",
      position: "center"
    });
  }

  Swal.fire({
    title: "Processing enrollment...",
    text: "Please wait while we save and verify faces",
    allowOutsideClick: false,
    didOpen: () => Swal.showLoading(),
  });

  try {
    const payload = { student_id: sid, name, course, section, room, images: photos };
    const res = await fetch("/api/enroll", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const j = await res.json();

    Swal.close();
    Swal.fire({
      icon: j.status === "ok" ? "success" : (j.status === "duplicate" ? "warning" : "error"),
      title:
        j.status === "ok"
          ? `✅ Student ${name} enrolled successfully!`
          : j.message || "Enrollment failed",
      position: "center",
      timer: 2500,
      showConfirmButton: false
    });

    if (j.status === "ok") {
      photos = [];
      thumbs.innerHTML = "";
      countSpan.textContent = "0 images";
      if (stream) {
        stream.getTracks().forEach((t) => t.stop());
        video.srcObject = null;
      }
      document.getElementById("cameraStatus").textContent = "Idle";
    }
  } catch (err) {
    Swal.close();
    Swal.fire({
      icon: "error",
      title: "Error during enrollment",
      text: err.message,
      position: "center"
    });
  }
};

// --------------------- FILE UPLOAD OPTION ---------------------
document.getElementById("enrollBtn").insertAdjacentHTML(
  "afterend",
  `
  <div class="mt-3">
    <label class="form-label fw-semibold">Or Upload Photos</label>
    <input type="file" id="uploadFiles" multiple accept="image/*" class="form-control">
    <button id="uploadBtn" class="btn btn-outline-secondary btn-sm mt-2">Upload & Enroll</button>
  </div>
  `
);

document.addEventListener("click", async (e) => {
  if (e.target && e.target.id === "uploadBtn") {
    const sid = document.getElementById("student_id").value.trim();
    const name = document.getElementById("name").value.trim();
    const course = document.getElementById("course").value.trim();
    const section = document.getElementById("section").value.trim();
    const room = document.getElementById("room").value.trim();
    const files = document.getElementById("uploadFiles").files;

    if (!sid || !name || files.length === 0) {
      return Swal.fire({
        icon: "error",
        title: "Enter ID, Name, and select at least one photo",
        position: "center"
      });
    }

    const fd = new FormData();
    fd.append("student_id", sid);
    fd.append("name", name);
    fd.append("course", course);
    fd.append("section", section);
    fd.append("room", room);
    for (const f of files) fd.append("files[]", f);

    Swal.fire({
      title: "Uploading photos...",
      allowOutsideClick: false,
      didOpen: () => Swal.showLoading(),
    });

    const res = await fetch("/api/enroll_files", { method: "POST", body: fd });
    const j = await res.json();

    Swal.close();
    Swal.fire({
      icon: j.status === "ok" ? "success" : (j.status === "duplicate" ? "warning" : "error"),
      title: j.message || "Upload completed",
      position: "center",
      timer: 2500,
      showConfirmButton: false
    });

    if (j.status === "ok") {
      document.getElementById("uploadFiles").value = "";
    }
  }
});
