import os
import sqlite3
import json
import uuid
from datetime import datetime
import numpy as np

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'faces.db')

def get_db_connection(db_path=None):
    """Establishes a thread-safe connection to SQLite database."""
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for high concurrency and performance
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db(db_path=None):
    """Initializes database schema with required tables and default settings."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Table: registered people
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            name_normalized TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            encoding BLOB NOT NULL,
            thumbnail_path TEXT NOT NULL,
            face_confidence REAL DEFAULT 0.0,
            notes TEXT DEFAULT '',
            recognition_count INTEGER DEFAULT 0,
            last_seen_at TEXT DEFAULT NULL
        );
    """)

    # Table: recognition event log (for analytics & dashboard feed)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recognition_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER,
            detected_name TEXT NOT NULL,
            confidence REAL NOT NULL,
            status TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE SET NULL
        );
    """)

    # Table: system settings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT
        );
    """)

    # Insert default settings if not exists
    default_settings = [
        ("similarity_threshold", "0.38", "Cosine similarity threshold for recognizing a face (0.35-0.50)"),
        ("detection_confidence", "0.60", "YuNet face detection confidence threshold (0.40-0.90)"),
        ("prevent_duplicate_faces", "true", "Disallow registering a face that already matches a registered person"),
        ("auto_log_recognitions", "true", "Automatically log recognition events to activity history"),
        ("dark_mode", "true", "Dark modern navy theme enabled")
    ]

    for key, val, desc in default_settings:
        cursor.execute("""
            INSERT OR IGNORE INTO system_settings (key, value, description)
            VALUES (?, ?, ?);
        """, (key, val, desc))

    conn.commit()
    conn.close()

def encode_vector(vector: np.ndarray) -> bytes:
    """Converts numpy float32 embedding vector to raw binary bytes."""
    if isinstance(vector, np.ndarray):
        return vector.astype(np.float32).tobytes()
    elif isinstance(vector, list):
        return np.array(vector, dtype=np.float32).tobytes()
    return bytes(vector)

def decode_vector(blob: bytes) -> np.ndarray:
    """Converts binary bytes back into 1D/2D numpy float32 embedding vector."""
    arr = np.frombuffer(blob, dtype=np.float32)
    # Reshape to (1, 128) if length is 128
    if arr.size == 128:
        return arr.reshape((1, 128))
    return arr

def add_person(name: str, encoding: np.ndarray, thumbnail_path: str, face_confidence: float = 0.0, notes: str = "", db_path=None) -> dict:
    """
    Registers a new person in SQLite.
    Returns the newly created person dict.
    """
    clean_name = name.strip()
    norm_name = clean_name.lower()
    uid = f"UID-{uuid.uuid4().hex[:8].upper()}"
    now_iso = datetime.now().isoformat()

    blob = encode_vector(encoding)

    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO people (uid, name, name_normalized, created_at, updated_at, encoding, thumbnail_path, face_confidence, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (uid, clean_name, norm_name, now_iso, now_iso, blob, thumbnail_path, float(face_confidence), notes))
    
    person_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "id": person_id,
        "uid": uid,
        "name": clean_name,
        "created_at": now_iso,
        "thumbnail_path": thumbnail_path,
        "face_confidence": face_confidence
    }

def get_person_by_id(person_id: int, db_path=None):
    """Retrieves person by numeric ID."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM people WHERE id = ?", (person_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["encoding"] = decode_vector(d["encoding"])
        return d
    return None

def get_person_by_uid(uid: str, db_path=None):
    """Retrieves person by public UID."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM people WHERE uid = ?", (uid,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["encoding"] = decode_vector(d["encoding"])
        return d
    return None

def find_person_by_name(name: str, db_path=None):
    """Checks for existing person with same name (case-insensitive)."""
    norm_name = name.strip().lower()
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, uid, name FROM people WHERE name_normalized = ?", (norm_name,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_people(search_query: str = None, db_path=None) -> list:
    """Returns list of all registered people (without heavy raw encodings for fast payload)."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    if search_query:
        param = f"%{search_query.strip().lower()}%"
        cursor.execute("""
            SELECT id, uid, name, created_at, updated_at, thumbnail_path, face_confidence, notes, recognition_count, last_seen_at
            FROM people
            WHERE name_normalized LIKE ? OR uid LIKE ?
            ORDER BY created_at DESC
        """, (param, param))
    else:
        cursor.execute("""
            SELECT id, uid, name, created_at, updated_at, thumbnail_path, face_confidence, notes, recognition_count, last_seen_at
            FROM people
            ORDER BY created_at DESC
        """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_encodings(db_path=None) -> list:
    """
    Returns all registered face encodings with their IDs and names for matching.
    Each item: {"id": int, "uid": str, "name": str, "encoding": np.ndarray}
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, uid, name, encoding FROM people")
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "uid": r["uid"],
            "name": r["name"],
            "encoding": decode_vector(r["encoding"])
        })
    return result

def delete_person(person_id_or_uid, db_path=None) -> bool:
    """
    Deletes person record from SQLite and removes their thumbnail image from disk.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    if isinstance(person_id_or_uid, int) or (isinstance(person_id_or_uid, str) and person_id_or_uid.isdigit()):
        cursor.execute("SELECT id, thumbnail_path FROM people WHERE id = ?", (int(person_id_or_uid),))
    else:
        cursor.execute("SELECT id, thumbnail_path FROM people WHERE uid = ?", (str(person_id_or_uid),))
    
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    pid = row["id"]
    thumb_path = row["thumbnail_path"]

    # Delete from DB
    cursor.execute("DELETE FROM people WHERE id = ?", (pid,))
    conn.commit()
    conn.close()

    # Delete thumbnail on disk if exists
    if thumb_path and os.path.exists(thumb_path):
        try:
            os.remove(thumb_path)
        except OSError:
            pass

    return True

def record_recognition(person_id, detected_name: str, confidence: float, status: str, db_path=None):
    """Logs a recognition event and increments the person's count/last seen."""
    now_iso = datetime.now().isoformat()
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Insert log
    cursor.execute("""
        INSERT INTO recognition_logs (person_id, detected_name, confidence, status, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (person_id, detected_name, float(confidence), status, now_iso))

    # Update person stats if recognized
    if person_id is not None:
        cursor.execute("""
            UPDATE people
            SET recognition_count = recognition_count + 1,
                last_seen_at = ?
            WHERE id = ?
        """, (now_iso, person_id))

    conn.commit()
    conn.close()

def get_dashboard_stats(db_path=None) -> dict:
    """Computes summary metrics for Dashboard overview."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM people")
    total_people = cursor.fetchone()["total"]

    today_str = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT COUNT(*) AS today_count FROM people WHERE created_at LIKE ?", (f"{today_str}%",))
    registered_today = cursor.fetchone()["today_count"]

    cursor.execute("SELECT COUNT(*) AS recog_count FROM recognition_logs WHERE status = 'recognized'")
    total_recognized = cursor.fetchone()["recog_count"]

    cursor.execute("SELECT COUNT(*) AS unknown_count FROM recognition_logs WHERE status = 'unknown'")
    total_unknown = cursor.fetchone()["unknown_count"]

    # Recent activity logs (last 10)
    cursor.execute("""
        SELECT rl.id, rl.detected_name, rl.confidence, rl.status, rl.timestamp, p.thumbnail_path, p.uid
        FROM recognition_logs rl
        LEFT JOIN people p ON rl.person_id = p.id
        ORDER BY rl.timestamp DESC
        LIMIT 10
    """)
    recent_logs = [dict(r) for r in cursor.fetchall()]

    # Recently registered people (last 5)
    cursor.execute("""
        SELECT id, uid, name, created_at, thumbnail_path, recognition_count
        FROM people
        ORDER BY created_at DESC
        LIMIT 5
    """)
    recent_people = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "total_registered": total_people,
        "registered_today": registered_today,
        "total_recognized_events": total_recognized,
        "total_unknown_events": total_unknown,
        "recent_logs": recent_logs,
        "recent_people": recent_people
    }

def get_settings(db_path=None) -> dict:
    """Returns all system settings as a dictionary."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT key, value, description FROM system_settings")
    rows = cursor.fetchall()
    conn.close()
    return {r["key"]: {"value": r["value"], "description": r["description"]} for r in rows}

def update_setting(key: str, value: str, db_path=None) -> bool:
    """Updates an existing setting value."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE system_settings SET value = ? WHERE key = ?", (str(value), key))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated
