import os
import cv2
import base64
import numpy as np
import pandas as pd
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_file
from deepface import DeepFace
from flask_cors import CORS

# ---------------- CONFIG ----------------
STUDENT_DB_DIR = "student_database"
ENROLL_CSV = "enrollment.csv"
ATTENDANCE_CSV = "attendance.csv"
EMBED_CSV = "embeddings.csv"
UPLOAD_TMP = "tmp_uploads"

MODEL_NAME = "Facenet512"   # smaller, faster model (~90MB)
MATCH_THRESHOLD = 0.6
CAPTURE_COUNT_MIN = 3
CAPTURE_COUNT_MAX = 10

os.makedirs(STUDENT_DB_DIR, exist_ok=True)
os.makedirs(UPLOAD_TMP, exist_ok=True)

app = Flask(__name__)
CORS(app)

active_sessions = {}

# ---------------- HELPERS ----------------
def get_embedding(img):
    """Generate normalized embedding vector from image"""
    rep = DeepFace.represent(img, model_name=MODEL_NAME, enforce_detection=True)[0]["embedding"]
    vec = np.array(rep, dtype=np.float32)
    vec = vec / np.linalg.norm(vec)
    return vec


def load_embeddings():
    """Load embeddings from CSV"""
    if not os.path.exists(EMBED_CSV):
        return {}
    df = pd.read_csv(EMBED_CSV)
    db = {}
    for _, row in df.iterrows():
        vec = np.fromstring(row["embedding"], sep=",")
        db[int(row["student_id"])] = {"name": row["name"], "embedding": vec}
    return db


def save_embedding(sid, name, vec):
    """Save new embedding to CSV"""
    df = pd.read_csv(EMBED_CSV) if os.path.exists(EMBED_CSV) else pd.DataFrame(columns=["student_id", "name", "embedding"])
    emb_str = ",".join(map(str, vec.tolist()))
    new_row = pd.DataFrame([{"student_id": sid, "name": name, "embedding": emb_str}])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(EMBED_CSV, index=False)


def find_best_match(vec, db):
    """Find closest match in database"""
    best_id, best_dist = None, 1e9
    for sid, info in db.items():
        dist = np.linalg.norm(vec - info["embedding"])
        if dist < best_dist:
            best_id, best_dist = sid, dist
    return best_id, best_dist


# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/enroll")
def enroll_page():
    return render_template("enroll.html")


@app.route("/registered")
def registered_page():
    if not os.path.exists(ENROLL_CSV):
        return render_template("registered.html", students=[])
    df = pd.read_csv(ENROLL_CSV).fillna("")
    students = df.to_dict(orient="records")
    return render_template("registered.html", students=students)


@app.route("/attendance")
def attendance_page():
    return render_template("attendance.html")


@app.route("/reports")
def reports_page():
    if not os.path.exists(ATTENDANCE_CSV):
        return render_template("reports.html", rows=[])
    df = pd.read_csv(ATTENDANCE_CSV).fillna("")
    return render_template("reports.html", rows=df.to_dict(orient="records"))


@app.route("/api/registered")
def api_registered():
    if not os.path.exists(ENROLL_CSV):
        return jsonify({"status": "ok", "registered": []})
    df = pd.read_csv(ENROLL_CSV).fillna("")
    return jsonify({"status": "ok", "registered": df.to_dict(orient="records")})

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard_page():
    total_registered = 0
    present_today = 0
    absent_today = 0
    last_attendance_time = "—"

    # Load registered students
    if os.path.exists(ENROLL_CSV):
        df_reg = pd.read_csv(ENROLL_CSV).fillna("")
        total_registered = len(df_reg)
    else:
        df_reg = pd.DataFrame(columns=["student_id"])

    # Load attendance records
    today_str = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(ATTENDANCE_CSV):
        df_att = pd.read_csv(ATTENDANCE_CSV).fillna("")
        today_records = df_att[df_att["login_date"] == today_str]
        present_today = len(today_records["student_id"].unique())
        if not today_records.empty:
            last_attendance_time = today_records["login_time"].iloc[-1]
    else:
        today_records = pd.DataFrame(columns=["student_id"])

    # Calculate absent
    all_ids = set(df_reg["student_id"].astype(str))
    present_ids = set(today_records["student_id"].astype(str))
    absent_today = max(0, len(all_ids - present_ids))

    return render_template(
        "dashboard.html",
        total_registered=total_registered,
        present_today=present_today,
        absent_today=absent_today,
        last_attendance_time=last_attendance_time,
    )

# ---------------- ENROLL (CAMERA) ----------------
@app.route("/api/enroll", methods=["POST"])
def api_enroll():
    data = request.get_json()
    sid = data.get("student_id")
    name = data.get("name")
    course = data.get("course", "")
    section = data.get("section", "")
    room = data.get("room", "")
    images = data.get("images", [])

    if not sid or not name or not images:
        return jsonify({"status": "error", "message": "Missing fields"}), 400

    embeddings_db = load_embeddings()
    rep_list = []

    for img_b64 in images:
        try:
            header, encoded = img_b64.split(",", 1)
            img_bytes = base64.b64decode(encoded)
            img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            vec = get_embedding(rgb)
            rep_list.append(vec)

            if embeddings_db:
                best_id, best_dist = find_best_match(vec, embeddings_db)
                if best_dist <= MATCH_THRESHOLD:
                    return jsonify({"status": "duplicate", "message": f"Already enrolled as {embeddings_db[best_id]['name']}"}), 200
        except Exception as e:
            print(f"[WARN] Face not detected in one image: {e}")
            continue

    if not rep_list:
        return jsonify({"status": "error", "message": "No valid face detected"}), 400

    # Save images locally
    folder = os.path.join(STUDENT_DB_DIR, f"{sid}_{name}")
    os.makedirs(folder, exist_ok=True)
    for i, img_b64 in enumerate(images):
        _, encoded = img_b64.split(",", 1)
        img = cv2.imdecode(np.frombuffer(base64.b64decode(encoded), np.uint8), cv2.IMREAD_COLOR)
        cv2.imwrite(os.path.join(folder, f"{name}_{i+1}.jpg"), img)

    # Save enrollment data
    df = pd.read_csv(ENROLL_CSV) if os.path.exists(ENROLL_CSV) else pd.DataFrame(columns=["student_id", "name", "course", "section", "room"])
    if not (df["student_id"] == int(sid)).any():
        df = pd.concat([df, pd.DataFrame([{
            "student_id": int(sid), "name": name, "course": course, "section": section, "room": room
        }])], ignore_index=True)
        df.to_csv(ENROLL_CSV, index=False)

    # Save embedding
    avg_vec = np.mean(np.stack(rep_list), axis=0)
    save_embedding(sid, name, avg_vec)
    return jsonify({"status": "ok", "message": "Enrolled successfully"})


# ---------------- ENROLL (UPLOAD FILES) ----------------
@app.route("/api/enroll_files", methods=["POST"])
def api_enroll_files():
    sid = request.form.get("student_id")
    name = request.form.get("name")
    course = request.form.get("course", "")
    section = request.form.get("section", "")
    room = request.form.get("room", "")

    if not sid or not name:
        return jsonify({"status": "error", "message": "Missing student_id or name"}), 400

    files = request.files.getlist("files[]")
    if not files:
        return jsonify({"status": "error", "message": "No files uploaded"}), 400

    images_b64 = []
    for f in files:
        data = f.read()
        if not data:
            continue
        images_b64.append("data:image/jpeg;base64," + base64.b64encode(data).decode("utf-8"))

    request.json = {
        "student_id": sid,
        "name": name,
        "course": course,
        "section": section,
        "room": room,
        "images": images_b64
    }
    return api_enroll()


# ---------------- ATTENDANCE LOGIN ----------------
@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    img_b64 = data.get("image")
    if not img_b64:
        return jsonify({"status": "error", "message": "No image"}), 400

    try:
        _, encoded = img_b64.split(",", 1)
        img = cv2.imdecode(np.frombuffer(base64.b64decode(encoded), np.uint8), cv2.IMREAD_COLOR)
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        vec = get_embedding(rgb)
    except Exception:
        return jsonify({"status": "error", "message": "No face detected"}), 200

    db = load_embeddings()
    if not db:
        return jsonify({"status": "error", "message": "No enrolled students"}), 400

    best_id, best_dist = find_best_match(vec, db)
    if best_dist > MATCH_THRESHOLD:
        return jsonify({"status": "unknown", "message": "No match found"}), 200

    sid = best_id
    name = db[sid]["name"]
    now = datetime.now()

    df = pd.read_csv(ATTENDANCE_CSV) if os.path.exists(ATTENDANCE_CSV) else pd.DataFrame(
        columns=["student_id", "name", "login_date", "login_time", "logout_date", "logout_time"]
    )

    df = pd.concat([df, pd.DataFrame([{
        "student_id": sid,
        "name": name,
        "login_date": now.strftime("%Y-%m-%d"),
        "login_time": now.strftime("%H:%M:%S"),
        "logout_date": "",
        "logout_time": ""
    }])], ignore_index=True)

    df.to_csv(ATTENDANCE_CSV, index=False)
    active_sessions[str(sid)] = {"logged_in": True, "name": name}
    return jsonify({"status": "ok", "student_id": sid, "name": name})


# ---------------- LOGOUT ----------------
@app.route("/api/logout", methods=["POST"])
def api_logout():
    data = request.get_json()
    sid = data.get("student_id")
    if not sid:
        return jsonify({"status": "error", "message": "student_id required"}), 400

    df = pd.read_csv(ATTENDANCE_CSV)
    if "logout_date" not in df.columns:
        df["logout_date"] = ""

    mask = (df["student_id"] == int(sid)) & (df["logout_date"].isnull() | (df["logout_date"] == ""))
    if mask.any():
        idx = df[mask].index[-1]
        df.at[idx, "logout_date"] = datetime.now().strftime("%Y-%m-%d")
        df.at[idx, "logout_time"] = datetime.now().strftime("%H:%M:%S")
        df.to_csv(ATTENDANCE_CSV, index=False)
        active_sessions.pop(str(sid), None)
        return jsonify({"status": "ok", "message": "Logout recorded"})
    else:
        return jsonify({"status": "error", "message": "No active session found"}), 200


# ---------------- EXPORT CSV ----------------
@app.route("/export_csv")
def export_csv():
    if not os.path.exists(ATTENDANCE_CSV):
        return "No records"
    return send_file(ATTENDANCE_CSV, as_attachment=True)


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
