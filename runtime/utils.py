import os
import sys


APP_DIR_NAME = "AktuBot"
APP_HOME_ENV_VAR = "AKTUBOT_HTTP_HOME"


def is_frozen_app():
    return bool(getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS"))


def get_resource_path(relative_path):
    """
    Get the absolute path to a bundled resource.
    Works in development and in PyInstaller builds.
    """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    return os.path.join(base_path, relative_path)


def _get_home_dir():
    return os.path.expanduser("~")


def _get_app_home_override():
    override = os.environ.get(APP_HOME_ENV_VAR, "").strip()
    if not override:
        return None

    path = os.path.abspath(os.path.expanduser(override))
    os.makedirs(path, exist_ok=True)
    return path


def get_user_documents_dir():
    """
    User-visible folder. Only final exported files should go here.
    """
    path = os.path.join(_get_home_dir(), "Documents", APP_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def get_app_data_dir():
    """
    Hidden writable application data directory for logs, checkpoints, and sessions.
    """
    override = _get_app_home_override()
    if override:
        return override

    if sys.platform == "darwin":
        path = os.path.join(_get_home_dir(), "Library", "Application Support", APP_DIR_NAME)
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA") or os.path.join(_get_home_dir(), "AppData", "Roaming")
        path = os.path.join(appdata, APP_DIR_NAME)
    else:
        path = os.path.join(_get_home_dir(), ".local", "share", APP_DIR_NAME)

    os.makedirs(path, exist_ok=True)
    return path


def get_output_dir():
    path = os.path.join(get_user_documents_dir(), "output")
    os.makedirs(path, exist_ok=True)
    return path


def get_logs_dir():
    path = os.path.join(get_app_data_dir(), "logs")
    os.makedirs(path, exist_ok=True)
    return path


def get_checkpoint_db_path():
    return os.path.join(get_app_data_dir(), "run_state.sqlite")


def get_seed_session_dir():
    """
    Bundled seed session directory. In development this lives in the repo.
    """
    path = get_resource_path("session_caches")
    if not is_frozen_app():
        os.makedirs(path, exist_ok=True)
    return path


def get_runtime_session_dir():
    path = os.path.join(get_app_data_dir(), "sessions")
    os.makedirs(path, exist_ok=True)
    return path


def get_session_store_write_path():
    return os.path.join(get_runtime_session_dir(), "session_store.json")


def get_session_store_read_paths():
    runtime_path = get_session_store_write_path()
    seed_path = os.path.join(get_seed_session_dir(), "session_store.json")

    paths = [runtime_path]
    if os.path.abspath(seed_path) != os.path.abspath(runtime_path):
        paths.append(seed_path)
    return paths


def get_legacy_session_cache_filename(slot_id):
    if slot_id == 0:
        return "session_cookie_cache.json"
    return f"session_cookie_cache_{slot_id + 1}.json"


def get_legacy_session_cache_paths(slot_id):
    filename = get_legacy_session_cache_filename(slot_id)
    candidates = [
        os.path.join(get_runtime_session_dir(), filename),
        os.path.join(get_app_data_dir(), filename),
        os.path.join(get_user_documents_dir(), filename),
        os.path.join(get_seed_session_dir(), filename),
    ]

    unique_candidates = []
    seen = set()
    for candidate in candidates:
        normalized = os.path.abspath(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_candidates.append(candidate)
    return unique_candidates
