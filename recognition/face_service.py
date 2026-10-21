import os
import cv2
import base64
import numpy as np
import threading
import urllib.request
from PIL import Image
import io
import time

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models')
YUNET_MODEL_PATH = os.path.join(MODELS_DIR, 'face_detection_yunet.onnx')
SFACE_MODEL_PATH = os.path.join(MODELS_DIR, 'face_recognition_sface.onnx')

YUNET_URL = "https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx"
SFACE_URL = "https://huggingface.co/opencv/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx"

class FaceService:
    """
    High-performance Face Detection and Recognition engine powered by
    OpenCV's YuNet (Detection) and SFace (128-d Deep Metric Feature Recognition).
    """

    def __init__(self, score_threshold=0.55, nms_threshold=0.3, similarity_threshold=0.38):
        self.score_threshold = score_threshold
        self.nms_threshold = nms_threshold
        self.similarity_threshold = similarity_threshold
        self.lock = threading.Lock()
        
        self.detector = None
        self.recognizer = None
        
        self._ensure_models_exist()
        self._init_models()

    def _ensure_models_exist(self):
        """Checks and downloads model weights if not present."""
        os.makedirs(MODELS_DIR, exist_ok=True)
        
        # Download YuNet if missing
        if not os.path.exists(YUNET_MODEL_PATH) or os.path.getsize(YUNET_MODEL_PATH) < 10000:
            print("[FaceService] Downloading YuNet detection model from Hugging Face...")
            urllib.request.urlretrieve(YUNET_URL, YUNET_MODEL_PATH)
            print("[FaceService] YuNet downloaded successfully.")

        # Download SFace if missing
        if not os.path.exists(SFACE_MODEL_PATH) or os.path.getsize(SFACE_MODEL_PATH) < 1000000:
            print("[FaceService] Downloading SFace recognition model from Hugging Face...")
            urllib.request.urlretrieve(SFACE_URL, SFACE_MODEL_PATH)
            print("[FaceService] SFace downloaded successfully.")

    def _init_models(self):
        """Loads YuNet and SFace models into memory."""
        try:
            self.detector = cv2.FaceDetectorYN.create(
                YUNET_MODEL_PATH,
                "",
                (320, 320),
                self.score_threshold,
                self.nms_threshold,
                5000
            )
            self.recognizer = cv2.FaceRecognizerSF.create(
                SFACE_MODEL_PATH,
                ""
            )
            print("[FaceService] YuNet detector & SFace recognizer initialized successfully.")
        except Exception as e:
            print(f"[FaceService] Error initializing models: {e}")
            raise

    def decode_image_from_base64(self, b64_string: str) -> np.ndarray:
        """Decodes a base64 or DataURL image string to OpenCV BGR numpy array."""
        if "," in b64_string:
            b64_string = b64_string.split(",", 1)[1]
        img_bytes = base64.b64decode(b64_string)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img

    def decode_image_from_bytes(self, img_bytes: bytes) -> np.ndarray:
        """Decodes raw image bytes to OpenCV BGR numpy array."""
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img

    def detect_faces(self, image: np.ndarray, min_confidence: float = None):
        """
        Runs YuNet face detection on given image.
        Returns: list of face landmarks and bounding boxes.
        Each face is an array of 15 elements:
        [x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rcm, y_rcm, x_lcm, y_lcm, score]
        """
        if image is None or image.size == 0:
            return []

        h, w = image.shape[:2]
        threshold = min_confidence if min_confidence is not None else self.score_threshold

        with self.lock:
            self.detector.setInputSize((w, h))
            self.detector.setScoreThreshold(threshold)
            _, raw_faces = self.detector.detect(image)

        if raw_faces is None or len(raw_faces) == 0:
            return []

        # Filter and validate detected faces
        valid_faces = []
        for face in raw_faces:
            score = float(face[-1])
            if score >= threshold:
                valid_faces.append(face)

        return valid_faces

    def extract_feature(self, image: np.ndarray, face_data: np.ndarray) -> np.ndarray:
        """
        Aligns and crops the face using 5 facial landmarks,
        then extracts a 128-dimensional deep feature representation.
        """
        with self.lock:
            aligned_face = self.recognizer.alignCrop(image, face_data)
            feature = self.recognizer.feature(aligned_face)
            return feature

    def compute_similarity(self, feat1: np.ndarray, feat2: np.ndarray) -> float:
        """Computes cosine similarity between two face feature vectors."""
        with self.lock:
            # SFace cosine similarity output ranges roughly from -1 to 1 (practical 0 to 1)
            score = self.recognizer.match(feat1, feat2, cv2.FaceRecognizerSF_FR_COSINE)
            return float(score)

    def crop_face_thumbnail(self, image: np.ndarray, face_data: np.ndarray, output_size=(200, 200)) -> bytes:
        """
        Crops face region with comfortable margin for profile thumbnail.
        Returns JPEG bytes.
        """
        h, w = image.shape[:2]
        fx, fy, fw, fh = [int(v) for v in face_data[0:4]]

        # Add 25% padding around face
        pad_x = int(fw * 0.25)
        pad_y = int(fh * 0.25)

        x1 = max(0, fx - pad_x)
        y1 = max(0, fy - pad_y)
        x2 = min(w, fx + fw + pad_x)
        y2 = min(h, fy + fh + pad_y)

        cropped = image[y1:y2, x1:x2]
        if cropped.size == 0:
            cropped = image[max(0, fy):min(h, fy+fh), max(0, fx):min(w, fx+fw)]

        # Resize to standard thumbnail size
        resized = cv2.resize(cropped, output_size, interpolation=cv2.INTER_AREA)

        # Encode as JPEG
        _, buffer = cv2.imencode('.jpg', resized, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return buffer.tobytes()

    def process_registration(self, image: np.ndarray, person_name: str, registered_people_encodings: list = None, allow_duplicate: bool = False):
        """
        Validates registration image and generates facial feature representation.
        Enforces rules:
        - 0 faces: "No face detected. Please try again."
        - > 1 faces: "Multiple faces detected. Please capture only one person's face."
        - 1 face: Checks duplicate identity (if enabled), crops thumbnail, returns representation.
        """
        if image is None:
            return {"success": False, "error": "Invalid image data."}

        faces = self.detect_faces(image, min_confidence=0.55)
        face_count = len(faces)

        if face_count == 0:
            return {
                "success": False,
                "error": "No face detected. Please try again.",
                "face_count": 0
            }
        
        if face_count > 1:
            return {
                "success": False,
                "error": f"Multiple faces ({face_count}) detected. Please capture only one person's face.",
                "face_count": face_count
            }

        # Single face detected
        face = faces[0]
        face_confidence = float(face[-1])
        encoding = self.extract_feature(image, face)

        # Check for duplicate face against registered dataset
        if not allow_duplicate and registered_people_encodings:
            for person in registered_people_encodings:
                reg_feat = person.get("encoding")
                if reg_feat is not None:
                    sim = self.compute_similarity(encoding, reg_feat)
                    if sim >= self.similarity_threshold:
                        return {
                            "success": False,
                            "error": f"This face is already registered as '{person['name']}' (match: {sim*100:.1f}%).",
                            "face_count": 1,
                            "matched_person": person["name"],
                            "similarity": round(sim, 3)
                        }

        # Generate thumbnail
        thumb_bytes = self.crop_face_thumbnail(image, face)

        return {
            "success": True,
            "message": "Face detected and encoded successfully.",
            "face_count": 1,
            "encoding": encoding,
            "face_confidence": round(face_confidence, 3),
            "thumbnail_bytes": thumb_bytes
        }

    def process_frame(self, image: np.ndarray, registered_people: list, similarity_threshold: float = None):
        """
        Performs real-time face detection and recognition on a video frame.
        Identifies each detected face as either:
        - Recognized person (GREEN bounding box, person's name, Recognized status label)
        - Unknown person (YELLOW bounding box, "Unknown Person" label)
        """
        if image is None or image.size == 0:
            return {
                "faces": [],
                "total_faces": 0,
                "recognized_count": 0,
                "unknown_count": 0,
                "frame_size": [0, 0]
            }

        h, w = image.shape[:2]
        threshold = similarity_threshold if similarity_threshold is not None else self.similarity_threshold

        faces = self.detect_faces(image)
        results = []
        recognized_count = 0
        unknown_count = 0

        for face in faces:
            fx, fy, fw, fh = [int(v) for v in face[0:4]]
            detection_score = float(face[-1])

            # Extract 128D feature representation
            feat = self.extract_feature(image, face)

            # Compare against all registered people
            best_match = None
            highest_score = -1.0

            for person in registered_people:
                reg_feat = person.get("encoding")
                if reg_feat is not None:
                    score = self.compute_similarity(feat, reg_feat)
                    if score > highest_score:
                        highest_score = score
                        best_match = person

            # Clamp coordinates inside frame bounds
            x1 = max(0, fx)
            y1 = max(0, fy)
            w_clamped = min(w - x1, fw)
            h_clamped = min(h - y1, fh)

            if best_match and highest_score >= threshold:
                # Recognized person: GREEN box (#10b981)
                recognized_count += 1
                results.append({
                    "status": "Recognized",
                    "name": best_match["name"],
                    "uid": best_match["uid"],
                    "person_id": best_match["id"],
                    "color": "#10b981",          # Hex green
                    "border_color": "rgb(16, 185, 129)",
                    "box": {
                        "x": x1,
                        "y": y1,
                        "w": w_clamped,
                        "h": h_clamped
                    },
                    "norm_box": {
                        "x": round(x1 / w, 4),
                        "y": round(y1 / h, 4),
                        "w": round(w_clamped / w, 4),
                        "h": round(h_clamped / h, 4)
                    },
                    "confidence": round(highest_score, 3),
                    "detection_score": round(detection_score, 3)
                })
            else:
                # Unregistered person: YELLOW box (#f59e0b)
                unknown_count += 1
                results.append({
                    "status": "Unknown",
                    "name": "Unknown Person",
                    "uid": None,
                    "person_id": None,
                    "color": "#f59e0b",          # Hex yellow
                    "border_color": "rgb(245, 158, 11)",
                    "box": {
                        "x": x1,
                        "y": y1,
                        "w": w_clamped,
                        "h": h_clamped
                    },
                    "norm_box": {
                        "x": round(x1 / w, 4),
                        "y": round(y1 / h, 4),
                        "w": round(w_clamped / w, 4),
                        "h": round(h_clamped / h, 4)
                    },
                    "confidence": round(highest_score, 3) if highest_score > 0 else 0.0,
                    "detection_score": round(detection_score, 3)
                })

        return {
            "faces": results,
            "total_faces": len(results),
            "recognized_count": recognized_count,
            "unknown_count": unknown_count,
            "frame_size": [w, h],
            "timestamp": time.time()
        }
