import os
import logging
from datetime import datetime, timedelta
from config import Config

# 脚本日志配置
def get_script_logger(script_name: str):
    logger = logging.getLogger(f'script_{script_name}')
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    date = datetime.now().strftime('%Y-%m-%d')
    log_file = os.path.join(Config.SCRIPT_LOGS_DIR, f"{script_name}_{date}.log")
    
    handler = logging.FileHandler(log_file, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger


# 网关日志配置
def get_gateway_logger():
    logger = logging.getLogger('gateway')
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    date = datetime.now().strftime('%Y-%m-%d')
    log_file = os.path.join(Config.GATEWAY_LOGS_DIR, f"gateway_{date}.log")
    
    handler = logging.FileHandler(log_file, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger


# 读取脚本日志
def read_script_logs(script_name: str, lines: int = 100):
    logs = []
    date = datetime.now().strftime('%Y-%m-%d')
    log_file = os.path.join(Config.SCRIPT_LOGS_DIR, f"{script_name}_{date}.log")
    
    if os.path.isfile(log_file):
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            logs = all_lines[-lines:] if len(all_lines) > lines else all_lines
    
    return ''.join(logs)


# 读取网关日志
def read_gateway_logs(date: str = None, lines: int = 100):
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')
    log_file = os.path.join(Config.GATEWAY_LOGS_DIR, f"gateway_{date}.log")
    
    logs = []
    if os.path.isfile(log_file):
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            logs = all_lines[-lines:] if len(all_lines) > lines else all_lines
    
    return ''.join(logs)


# 列出脚本日志文件
def list_script_log_files(script_name: str):
    files = []
    for fname in os.listdir(Config.SCRIPT_LOGS_DIR):
        if fname.startswith(f"{script_name}_") and fname.endswith('.log'):
            path = os.path.join(Config.SCRIPT_LOGS_DIR, fname)
            size = os.path.getsize(path)
            mtime = os.path.getmtime(path)
            files.append({
                'name': fname,
                'size': size,
                'modified': datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            })
    return sorted(files, key=lambda x: x['modified'], reverse=True)


# 读取指定的脚本日志文件
def read_script_log_file(filename: str, lines: int = 1000) -> str:
    """读取指定的脚本日志文件内容"""
    log_file = os.path.join(Config.SCRIPT_LOGS_DIR, filename)
    
    if not os.path.isfile(log_file):
        return ''
    
    # 安全检查：确保文件在日志目录内
    real_path = os.path.realpath(log_file)
    real_dir = os.path.realpath(Config.SCRIPT_LOGS_DIR)
    if not real_path.startswith(real_dir):
        return ''
    
    logs = []
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            logs = all_lines[-lines:] if len(all_lines) > lines else all_lines
    except Exception:
        return ''
    
    return ''.join(logs)


# 清理过期日志
def cleanup_expired_logs(script_retention_days: int, gateway_retention_days: int):
    now = datetime.now()
    cleaned = {'script': 0, 'gateway': 0}
    
    # 清理脚本日志
    for fname in os.listdir(Config.SCRIPT_LOGS_DIR):
        if fname.endswith('.log'):
            path = os.path.join(Config.SCRIPT_LOGS_DIR, fname)
            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            if (now - mtime).days > script_retention_days:
                os.remove(path)
                cleaned['script'] += 1
    
    # 清理网关日志
    for fname in os.listdir(Config.GATEWAY_LOGS_DIR):
        if fname.endswith('.log'):
            path = os.path.join(Config.GATEWAY_LOGS_DIR, fname)
            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            if (now - mtime).days > gateway_retention_days:
                os.remove(path)
                cleaned['gateway'] += 1
    
    return cleaned
