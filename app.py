import os
import sys
import time
import base64
import cv2
import numpy as np
import platform
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    Response,
    send_from_directory,
    redirect,
    url_for
)

import database
from recognition import FaceService

# Initialize Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'smart-face-system-secure-key-2026')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

# Paths configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
THUMBNAIL_DIR = os.path.join(BASE_DIR, 'static', 'uploads', 'thumbnails')
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

# Initialize SQLite database
database.init_db()

# Initialize Face Recognition Service
face_service = FaceService()

# In-memory throttle for recognition event logging (identifier -> last_timestamp)
recognition_log_throttle = {}
THROTTLE_SECONDS = 8.0

# -------------------------------------------------------------------------
# Web Page Routes
# -------------------------------------------------------------------------

@app.route('/')
def index():
    """Dashboard Overview page."""
    stats = database.get_dashboard_stats()
    return render_template('index.html', active_page='dashboard', stats=stats)

@app.route('/register')
def register_page():
    """Face Registration page."""
    return render_template('register.html', active_page='register')

@app.route('/recognize')
def recognize_page():
    """Live Face Recognition page."""
    return render_template('recognize.html', active_page='recognize')

@app.route('/people')
def people_page():
    """Registered People Directory page."""
    return render_template('people.html', active_page='people')

@app.route('/settings')
def settings_page():
    """Settings & Diagnostics page."""
    settings = database.get_settings()
    return render_template(
        'settings.html',
        active_page='settings',
        settings=settings,
        db_path=database.DEFAULT_DB_PATH,
        cv2_version=cv2.__version__,
        flask_version='3.1.3',
        python_version=platform.python_version()
    )

# -------------------------------------------------------------------------
# API Endpoints
# -------------------------------------------------------------------------

@app.route('/api/register', methods=['POST'])
def api_register():
    """
    Registers a person's face from base64 image data.
    Validates face detection:
    - 0 faces: "No face detected. Please try again."
    - > 1 faces: "Multiple faces detected. Please capture only one person's face."
    - Duplicate checks: name and facial embedding.
    """
    try:
        data = request.get_json(silent=True) or {}
        name = data.get('name', '').strip()
        image_b64 = data.get('image', '')
        notes = data.get('notes', '').strip()

        # Validate name
        if not name or len(name) < 2:
            return jsonify({
                "success": False,
                "error": "Please provide a valid person's name (at least 2 characters)."
            }), 400

        # Validate image data
        if not image_b64:
            return jsonify({
                "success": False,
                "error": "No image data provided for registration."
            }), 400

        # Check for duplicate name
        existing_person = database.find_person_by_name(name)
        if existing_person:
            return jsonify({
                "success": False,
                "error": f"A person named '{existing_person['name']}' is already registered in the system."
            }), 409

        # Decode image
        try:
            image = face_service.decode_image_from_base64(image_b64)
            if image is None or image.size == 0:
                raise ValueError("Could not decode image")
        except Exception:
            return jsonify({
                "success": False,
                "error": "Invalid or corrupted image format. Please capture again."
            }), 400

        # Fetch current registered encodings for duplicate face checking
        registered_encodings = database.get_all_encodings()

        # Check system settings for duplicate face policy
        settings = database.get_settings()
        allow_duplicate = settings.get("prevent_duplicate_faces", {}).get("value", "true") != "true"

        # Process registration through FaceService
        proc_result = face_service.process_registration(
            image=image,
            person_name=name,
            registered_people_encodings=registered_encodings,
            allow_duplicate=allow_duplicate
        )

        if not proc_result.get("success"):
            return jsonify({
                "success": False,
                "error": proc_result.get("error", "Registration validation failed."),
                "face_count": proc_result.get("face_count", 0)
            }), 422

        # Generate unique thumbnail file
        import uuid
        thumb_filename = f"thumb_{uuid.uuid4().hex[:12]}.jpg"
        thumb_disk_path = os.path.join(THUMBNAIL_DIR, thumb_filename)
        
        with open(thumb_disk_path, "wb") as f:
            f.write(proc_result["thumbnail_bytes"])

        # URL path for browser
        web_thumb_path = f"/static/uploads/thumbnails/{thumb_filename}"

        # Save record in SQLite
        new_person = database.add_person(
            name=name,
            encoding=proc_result["encoding"],
            thumbnail_path=web_thumb_path,
            face_confidence=proc_result.get("face_confidence", 0.0),
            notes=notes
        )

        return jsonify({
            "success": True,
            "message": "Face Registered Successfully",
            "person": new_person
        }), 201

    except Exception as e:
        app.logger.error(f"Error in api_register: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Internal server error: {str(e)}"
        }), 500


@app.route('/api/recognize_frame', methods=['POST'])
def api_recognize_frame():
    """
    Processes a video frame from client webcam.
    Detects faces, generates embeddings, matches with database, and returns
    bounding boxes with GREEN (Recognized) or YELLOW (Unknown) designations.
    """
    try:
        data = request.get_json(silent=True) or {}
        frame_b64 = data.get('frame', '')
        client_threshold = data.get('similarity_threshold', None)

        if not frame_b64:
            return jsonify({"faces": [], "total_faces": 0}), 400

        # Decode image
        image = face_service.decode_image_from_base64(frame_b64)
        if image is None or image.size == 0:
            return jsonify({"faces": [], "total_faces": 0}), 400

        # Get all registered faces from DB
        registered_people = database.get_all_encodings()

        # Parse threshold
        sim_threshold = None
        if client_threshold is not None:
            try:
                sim_threshold = float(client_threshold)
            except (ValueError, TypeError):
                sim_threshold = None

        # Run detection and recognition
        result = face_service.process_frame(
            image=image,
            registered_people=registered_people,
            similarity_threshold=sim_threshold
        )

        # Log recognition events with throttling
        now = time.time()
        for face in result.get("faces", []):
            if face["status"] == "Recognized" and face.get("person_id"):
                pid = face["person_id"]
                last_time = recognition_log_throttle.get(f"pid_{pid}", 0)
                if now - last_time >= THROTTLE_SECONDS:
                    recognition_log_throttle[f"pid_{pid}"] = now
                    database.record_recognition(
                        person_id=pid,
                        detected_name=face["name"],
                        confidence=face["confidence"],
                        status="recognized"
                    )
            elif face["status"] == "Unknown":
                last_time = recognition_log_throttle.get("unknown", 0)
                if now - last_time >= THROTTLE_SECONDS:
                    recognition_log_throttle["unknown"] = now
                    database.record_recognition(
                        person_id=None,
                        detected_name="Unknown Person",
                        confidence=face["confidence"],
                        status="unknown"
                    )

        return jsonify(result), 200

    except Exception as e:
        app.logger.error(f"Error in api_recognize_frame: {e}", exc_info=True)
        return jsonify({"faces": [], "error": str(e)}), 500


@app.route('/api/people', methods=['GET'])
def api_get_people():
    """Returns list of registered people, optionally filtered by search query."""
    try:
        search_query = request.args.get('q', '').strip()
        people = database.get_all_people(search_query if search_query else None)
        return jsonify({
            "success": True,
            "people": people,
            "count": len(people)
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/people/<person_id>', methods=['DELETE'])
def api_delete_person(person_id):
    """
    Permanently deletes a registered person from SQLite and
    deletes their stored thumbnail and facial representation.
    """
    try:
        deleted = database.delete_person(person_id)
        if deleted:
            return jsonify({
                "success": True,
                "message": "Person and facial records deleted successfully."
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": "Person record not found."
            }), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/stats', methods=['GET'])
def api_stats():
    """Returns real-time dashboard statistics."""
    try:
        stats = database.get_dashboard_stats()
        return jsonify({"success": True, "stats": stats}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """Retrieves or updates system settings."""
    if request.method == 'GET':
        return jsonify({"success": True, "settings": database.get_settings()}), 200

    try:
        data = request.get_json(silent=True) or {}
        for k, v in data.items():
            database.update_setting(k, str(v))
        return jsonify({"success": True, "message": "Settings updated successfully."}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# -------------------------------------------------------------------------
# Server-side OpenCV MJPEG Camera Streaming Endpoint (Alternate Mode)
# -------------------------------------------------------------------------

def generate_opencv_stream():
    """
    Generator for MJPEG stream using direct OpenCV VideoCapture.
    Renders Green/Yellow bounding boxes directly onto video frames on server.
    """
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        # Fallback dummy frame if webcam is in use by browser or not found
        dummy = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(dummy, "Camera not accessible via OpenCV", (80, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        _, jpeg = cv2.imencode('.jpg', dummy)
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
        return

    try:
        while True:
            success, frame = cap.read()
            if not success:
                break

            registered_people = database.get_all_encodings()
            results = face_service.process_frame(frame, registered_people)

            # Draw boxes on frame
            for f in results.get("faces", []):
                box = f["box"]
                x, y, w, h = box["x"], box["y"], box["w"], box["h"]
                is_rec = f["status"] == "Recognized"
                color = (16, 185, 129) if is_rec else (11, 158, 245)  # BGR

                # Box
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                # Name tag
                label = f"{f['name']} ({f['status']})"
                cv2.putText(frame, label, (x, max(20, y - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
            time.sleep(0.04)
    finally:
        cap.release()

@app.route('/video_feed')
def video_feed():
    """Video streaming route for direct OpenCV webcam access."""
    return Response(
        generate_opencv_stream(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

# -------------------------------------------------------------------------
# Application Entry Point
# -------------------------------------------------------------------------

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '127.0.0.1')
    print("=" * 65)
    print(" Smart Face Detection and Recognition System")
    print(f" Server starting on http://{host}:{port}")
    print(" AI Engine: OpenCV YuNet (Detection) + SFace (128D Recognition)")
    print(" Storage: SQLite faces.db with WAL mode")
    print("=" * 65)
    app.run(host=host, port=port, debug=True)
