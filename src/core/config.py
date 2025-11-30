import os

class Config:
    # Paths
    # 获取项目根目录（src/core 的上一级目录）
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
        "static/output/{script_name}/{timestamp}"
    )

    # Notification
    DEFAULT_NOTIFY_URL = os.environ.get("NOTIFY_URL", "")
    
    # File Access Restrictions
    # 本地文件访问限制，默认为空表示不限制
    # 示例: ["/tmp/**", "/var/tmp/**"] 表示只允许访问这些目录
    LOCAL_FILE_ACCESS_PATTERNS = os.environ.get("LOCAL_FILE_ACCESS_PATTERNS", "").split(",") if os.environ.get("LOCAL_FILE_ACCESS_PATTERNS") else []
    
    # 临时文件清理间隔（小时）
    TEMP_FILE_CLEANUP_INTERVAL_HOURS = float(os.environ.get("TEMP_FILE_CLEANUP_INTERVAL_HOURS", "24"))

    @staticmethod
    def get_setting(key: str, default_value=None):
        """
        获取配置值，优先从数据库读取，如果没有则使用环境变量或默认值
        
        Args:
            key: 配置键名
            default_value: 默认值
            
        Returns:
            配置值
        """
        try:
            from .database import get_setting
            db_value = get_setting(key)
            if db_value is not None:
                return db_value
        except:
            # 如果数据库不可用，继续使用环境变量或默认值
            pass
        
        # 如果数据库中没有值，尝试从环境变量获取
        env_key = key.upper()
        env_value = os.environ.get(env_key)
        if env_value is not None:
            return env_value
            
        # 最后返回默认值
        return default_value
    
    @staticmethod
    def get_temp_file_cleanup_interval():
        """获取临时文件清理间隔（小时）"""
        value = Config.get_setting("temp_file_cleanup_interval_hours", "24")
        try:
            return float(value)
        except:
            return 24.0
    
    @staticmethod
    def get_local_file_access_patterns():
        """获取本地文件访问限制模式"""
        value = Config.get_setting("local_file_access_patterns", "")
        if value:
            # 支持逗号和换行符作为分隔符
            patterns = []
            for pattern in value.replace("\n", ",").split(","):
                pattern = pattern.strip()
                if pattern:
                    patterns.append(pattern)
            return patterns
        return []


def ensure_dirs():
    for p in [
        Config.SCRIPTS_PY_DIR,
        Config.SCRIPTS_JS_DIR,
        Config.STATIC_DIR,
        os.path.join(Config.STATIC_DIR, "resources"),
        os.path.join(Config.STATIC_DIR, "output"),
        Config.TEMPLATES_DIR,
        Config.SCRIPT_LOGS_DIR,
        Config.GATEWAY_LOGS_DIR,
    ]:
        os.makedirs(p, exist_ok=True)
