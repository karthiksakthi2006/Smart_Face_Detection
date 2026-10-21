# Database package
from .database import (
    DEFAULT_DB_PATH,
    init_db,
    add_person,
    get_person_by_id,
    get_person_by_uid,
    find_person_by_name,
    get_all_people,
    get_all_encodings,
    delete_person,
    record_recognition,
    get_dashboard_stats,
    get_settings,
    update_setting
)
