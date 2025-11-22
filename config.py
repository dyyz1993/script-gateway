import os

class Config:
    # Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(BASE_DIR, "gateway.db")
    SCRIPTS_PY_DIR = os.path.join(BASE_DIR, "scripts_repo", "python")
    SCRIPTS_JS_DIR = os.path.join(BASE_DIR, "scripts_repo", "js")
    STATIC_DIR = os.path.join(BASE_DIR, "static")
    TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
    LOGS_DIR = os.path.join(BASE_DIR, "logs")
    SCRIPT_LOGS_DIR = os.path.join(LOGS_DIR, "script")
    GATEWAY_LOGS_DIR = os.path.join(LOGS_DIR, "gateway")

    # Scan & Exec
    SCAN_INTERVAL_SEC = int(os.environ.get("SCAN_INTERVAL_SEC", "5"))
    TIMEOUT_MIN = int(os.environ.get("TIMEOUT_MIN", "10"))
    OUTPUT_PATH_TEMPLATE = os.environ.get(
        "OUTPUT_PATH_TEMPLATE",
        "static/{script_name}/资源/{timestamp}"
    )

    # Notification
    DEFAULT_NOTIFY_URL = os.environ.get("NOTIFY_URL", "")


def ensure_dirs():
    for p in [
        Config.SCRIPTS_PY_DIR,
        Config.SCRIPTS_JS_DIR,
        Config.STATIC_DIR,
        os.path.join(Config.STATIC_DIR, "resources"),
        Config.TEMPLATES_DIR,
        Config.SCRIPT_LOGS_DIR,
        Config.GATEWAY_LOGS_DIR,
    ]:
        os.makedirs(p, exist_ok=True)
