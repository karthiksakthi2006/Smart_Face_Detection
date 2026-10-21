# Smart Face Detection and Recognition System

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/framework-Flask%203.x-green.svg)](https://flask.palletsprojects.com/)
[![OpenCV](https://img.shields.io/badge/computer%20vision-OpenCV%20DNN-red.svg)](https://opencv.org/)
[![Database](https://img.shields.io/badge/database-SQLite%20WAL-lightgrey.svg)](https://www.sqlite.org/)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)

An enterprise-grade, privacy-focused, real-time facial detection and biometric recognition web application built with **Python**, **Flask**, **OpenCV**, and a responsive **Dark Navy** modern dashboard.

---

## 🌟 Highlights & Key Features

* **High-Accuracy Deep Metric Biometrics**: Powered by OpenCV's state-of-the-art **YuNet** (ultra-fast ONNX face detector) and **SFace** (128-dimensional deep feature representation model). Runs at 30+ FPS on standard CPUs without requiring C++ build tools or heavy GPU runtimes.
* **Real-time Live Webcam Recognition**:
  * **GREEN Bounding Box (`#10b981`)**: Drawn around registered faces with their name and a green status pill: `Recognized • 95% match`.
  * **YELLOW Bounding Box (`#f59e0b`)**: Drawn around unregistered or unknown faces with the label `Unknown Person`.
  * **Multi-person Tracking**: Detects and identifies multiple individuals in the webcam frame independently in real time.
* **Face Registration & Validation**:
  * Enforces the single-face rule: displays `"No face detected. Please try again."` if zero faces appear, and prompts to capture only one person if multiple faces appear.
  * Prevents duplicate name registrations and flags duplicate faces against stored facial vectors.
  * Generates a 128D facial representation, extracts an avatar thumbnail, and assigns a unique `UID-XXXXXXXX`.
  * Supports both live webcam capture and portrait photo file upload.
* **Registered People Directory**:
  * Browse registered profiles in Card Grid or Detailed Table view.
  * Instant live search by name or unique ID.
  * Deletion with confirmation modal: completely purges the person's SQLite record, their 128D facial representation, and their thumbnail on disk.
* **100% On-Device Privacy & Security**:
  * Facial vectors and images are processed strictly on your computer and stored inside your private local SQLite database (`instance/faces.db`).
  * Zero cloud uploads, zero external API dependencies, and no public exposure of biometric vectors.
* **Interactive HUD & Modern Dark UI**:
  * Built with a dark navy glassmorphic theme, real-time FPS counter, active faces count, live activity feed, and optional audio chime feedback upon recognition.

---

## 🛠️ Technology Stack

| Layer | Technology | Details |
| :--- | :--- | :--- |
| **Backend** | Python 3.10+ / 3.13, Flask 3.1 | Modular REST API & web server |
| **Face Detection** | OpenCV `cv2.FaceDetectorYN` (YuNet) | Lightweight, high-speed ONNX face detector |
| **Face Recognition**| OpenCV `cv2.FaceRecognizerSF` (SFace) | 128-dimensional deep metric embeddings |
| **Database** | SQLite 3 with WAL Mode | Persistent relational storage for profiles & embeddings |
| **Frontend** | HTML5, Vanilla CSS, JS, Bootstrap 5 | Modern dark navy theme, glassmorphism, responsive |
| **Camera Access** | HTML5 `navigator.mediaDevices` & Canvas | Low-latency client camera with OpenCV MJPEG fallback |

---

## 📁 Project Structure

```text
face/
├── app.py                      # Flask application entrypoint & API routes
├── requirements.txt            # Python dependencies
├── README.md                   # System documentation & setup guide
├── test_app.py                 # Automated unit and integration test suite
├── database/
│   ├── __init__.py             # Database exports
│   └── database.py             # SQLite manager, schema, CRUD, WAL concurrency
├── recognition/
│   ├── __init__.py             # Recognition engine exports
│   └── face_service.py         # YuNet detection + SFace 128D recognition engine
├── models/
│   ├── face_detection_yunet.onnx   # Auto-downloaded YuNet detector (232 KB)
│   └── face_recognition_sface.onnx # Auto-downloaded SFace recognizer (38.6 MB)
├── templates/
│   ├── base.html               # Master layout, navigation, status indicator
│   ├── index.html              # System Dashboard Overview & telemetry
│   ├── register.html           # Face Registration page (Webcam + Upload)
│   ├── recognize.html          # Live Face Recognition page (HUD + Boxes)
│   ├── people.html             # Registered People Directory & deletion
│   └── settings.html           # Sensitivity thresholds & diagnostics
├── static/
│   ├── css/
│   │   └── style.css           # Custom dark navy theme with green/yellow highlights
│   ├── js/
│   │   ├── app.js              # Toasts, Web Audio synthesizer chime, helpers
│   │   ├── register.js         # Webcam capture, validation, success modal
│   │   ├── recognize.js        # Real-time recognition loop, canvas overlay
│   │   └── people.js           # Directory management, search, deletion modal
│   └── uploads/
│       └── thumbnails/         # Stored cropped profile avatar images
└── instance/
    └── faces.db                # SQLite database storing identities & embeddings
```

---

## 🚀 Quick Start Guide (Windows)

### 1. Prerequisites
Ensure you have Python installed. On Windows, check using PowerShell or Command Prompt:
```powershell
py --version
# or
python --version
```
*(Python 3.10, 3.11, 3.12, or 3.13 are supported).*

### 2. Navigate to the Project Directory
```powershell
cd c:\Users\kisho\OneDrive\Documents\face
```

### 3. Install Dependencies
Install all required libraries using `pip`:
```powershell
py -m pip install -r requirements.txt
# or
pip install -r requirements.txt
```

### 4. Run the Application
Launch the Flask server:
```powershell
py app.py
```
You will see output similar to:
```text
=================================================================
 Smart Face Detection and Recognition System
 Server starting on http://127.0.0.1:5000
 AI Engine: OpenCV YuNet (Detection) + SFace (128D Recognition)
 Storage: SQLite faces.db with WAL mode
=================================================================
 * Running on http://127.0.0.1:5000
```

### 5. Open in Web Browser
Open your browser (Chrome, Edge, Firefox, or Safari) and navigate to:
**[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 📖 Application Workflow

### Step 1: Open the Application
Navigate to `http://127.0.0.1:5000` to view the **System Dashboard**. You will see real-time metrics (Total Registered Faces, Recognitions Count, Unknown Encounters).

### Step 2: Register a New Face
1. Click **Register Face** in the top navigation or dashboard button (`http://127.0.0.1:5000/register`).
2. Type the person's name in the input field, for example: `Kishore`.
3. Click **Start Camera** and grant browser webcam permission when prompted.
4. Position your face in the camera frame.
5. Click **Capture Face**:
   * If zero faces are visible: displays `"No face detected. Please try again."`
   * If multiple people appear: prompts you to ensure only one person is in the frame.
   * If valid: extracts the 128D embedding, saves a profile thumbnail, and displays **"Face Registered Successfully"** with a confirmation modal showing Kishore's details and ID.

### Step 3: Run Live Face Recognition
1. Click **Live Recognition** in the navigation bar (`http://127.0.0.1:5000/recognize`).
2. Click **Start Camera**.
3. When **Kishore** appears in the camera:
   * A **GREEN bounding box** is drawn around his face.
   * His name **"Kishore"** is displayed above the box.
   * A status pill shows **"Recognized (95% match)"**.
   * A subtle audio chime plays.
4. When an unregistered person appears in the camera:
   * A **YELLOW bounding box** is drawn around their face.
   * The label **"Unknown Person"** is displayed above the box.
5. As people move or turn, the bounding boxes dynamically follow them in real time.

### Step 4: Manage Registered People
1. Click **Registered People** (`http://127.0.0.1:5000/people`).
2. Filter instantly by typing in the search box (e.g. `Kishore` or UID).
3. Toggle between Card view and Table view.
4. To delete a person, click **Delete**, confirm the prompt, and their biometric embedding and thumbnail will be completely erased from disk and SQLite.

### Step 5: Adjust Sensitivity & Diagnostics
1. Click **Settings** (`http://127.0.0.1:5000/settings`).
2. Tune the **Cosine Similarity Threshold** (default: `0.38`).
3. Toggle **Enforce Biometric Uniqueness** to prevent duplicate registrations.
4. Inspect model telemetry and database storage metrics.

---

## 🧪 Automated Testing

An automated test suite is provided in `test_app.py`. It executes 12 end-to-end tests covering all routes, validations, recognition matching, and deletion:

To run tests:
```powershell
py test_app.py
```

Expected output:
```text
Ran 12 tests in ~0.6s
OK
```

---

## 📡 API Reference

### 1. Register Face
`POST /api/register`
* **Request JSON:**
  ```json
  {
    "name": "Kishore",
    "image": "data:image/jpeg;base64,...",
    "notes": "Lead Architect"
  }
  ```
* **Response (201 Created):**
  ```json
  {
    "success": true,
    "message": "Face Registered Successfully",
    "person": {
      "id": 1,
      "uid": "UID-D453E108",
      "name": "Kishore",
      "created_at": "2026-10-21T23:18:47",
      "thumbnail_path": "/static/uploads/thumbnails/thumb_xyz.jpg"
    }
  }
  ```

### 2. Recognize Frame
`POST /api/recognize_frame`
* **Request JSON:**
  ```json
  {
    "frame": "data:image/jpeg;base64,...",
    "similarity_threshold": 0.38
  }
  ```
* **Response (200 OK):**
  ```json
  {
    "faces": [
      {
        "status": "Recognized",
        "name": "Kishore",
        "color": "#10b981",
        "uid": "UID-D453E108",
        "confidence": 0.94,
        "box": { "x": 180, "y": 110, "w": 140, "h": 190 }
      }
    ],
    "recognized_count": 1,
    "unknown_count": 0,
    "total_faces": 1
  }
  ```

### 3. List Registered People
`GET /api/people?q=Kishore`
* **Response (200 OK):**
  ```json
  {
    "success": true,
    "people": [ ... ],
    "count": 1
  }
  ```

### 4. Delete Person
`DELETE /api/people/<person_id>`
* **Response (200 OK):**
  ```json
  {
    "success": true,
    "message": "Person and facial records deleted successfully."
  }
  ```

---

## 🔒 Privacy & Security Design

1. **Explicit Consent**: Consent confirmation is presented prior to registering any facial data.
2. **Local Processing**: Video feeds are processed entirely on localhost. No video or biometric representations are transmitted over external networks.
3. **Data Erasure**: Deleting a profile completely purges their biometric representation and avatar image permanently.
4. **No External Profiling**: Facial vectors are only matched against the user's private local SQLite database.

---

## 🔧 Troubleshooting

| Issue | Resolution |
| :--- | :--- |
| **"Could not access webcam"** | In your browser address bar, click the camera icon and select **"Always allow http://127.0.0.1:5000 to access your camera"**. |
| **Camera occupied by another program** | Close apps using the camera (Zoom, Teams, Skype, Windows Camera app) and refresh the page. |
| **"No face detected" error** | Ensure the room is well-lit and face directly toward the camera without excessive backlight. |
| **Port 5000 in use** | Run on another port using: `$env:PORT=5001; py app.py`. |

---

## 📄 License
This project is open-source under the MIT License.
