import os
import re
import json
import hashlib
import subprocess
import time
import fnmatch
from threading import Thread, Event
from typing import Optional

from ..core.config import Config, ensure_dirs
from ..core.database import upsert_script, init_db, get_setting

STOP_EVENT = Event()


def md5_file(path: str) -> str:
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def run_get_schema(cmd: list[str]) -> tuple[bool, Optional[str], Optional[str]]:
    try:
        # 设置环境变量，确保PYTHONPATH包含项目根目录和SenseVoiceSmall路径
        env = os.environ.copy()
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        sensevoice_path = os.path.join(project_root, 'scripts_repo', 'python', 'SenseVoiceSmall')
        
        # 确保PYTHONPATH包含必要的路径
        python_path = env.get('PYTHONPATH', '')
        paths_to_add = [project_root, sensevoice_path]
        
        # 将新路径添加到PYTHONPATH
        for path in paths_to_add:
            if path not in python_path:
                if python_path:
                    python_path += os.pathsep + path
                else:
                    python_path = path
        
        env['PYTHONPATH'] = python_path
        
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        out, err = proc.communicate(timeout=30)
        if proc.returncode == 0:
            text = out.decode('utf-8', errors='ignore')
            return True, text, None
        else:
            return False, None, err.decode('utf-8', errors='ignore')
    except Exception as e:
        return False, None, str(e)


def detect_script_type(path: str) -> Optional[str]:
    if path.endswith('.py'):
        return 'python'
    if path.endswith('.js'):
        return 'js'
    return None


def mapjson_sidecar_path(path: str) -> str:
    base = os.path.basename(path)
    name, _ = os.path.splitext(base)
    return os.path.join(os.path.dirname(path), f"{name}._map.json")


def has_entrypoint(path: str, stype: str) -> bool:
    """根据文档要求检查入口标识：
    - Python: 包含 if __name__ == "__main__"
    - JS: 包含 module.exports 或 export default
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
        if stype == 'python':
            return bool(re.search(r"if\s+__name__\s*==\s*[\"']__main__[\"']\s*:", text))
        if stype == 'js':
            return ('module.exports' in text) or ('export default' in text)
        return False
    except Exception:
        return False


def parse_and_register(path: str):
    stype = detect_script_type(path)
    if not stype:
        return

    # 计算相对于脚本仓库根目录的相对路径
    if stype == 'python':
        relative_path = os.path.relpath(path, Config.SCRIPTS_PY_DIR)
    else:
        relative_path = os.path.relpath(path, Config.SCRIPTS_JS_DIR)

    # 入口标识检查：不满足时直接跳过（不标记失败）
    if not has_entrypoint(path, stype):
        return

    file_hash = md5_file(path)
    cmd = []
    if stype == 'python':
        cmd = ['python3', path, '--_sys_get_schema']
    else:
        cmd = ['node', path, '--_sys_get_schema']

    ok, schema_text, err = run_get_schema(cmd)
    status_load = 1 if ok else 0
    load_error_msg = None if ok else (err or 'unknown error')
    args_schema = None

    if ok:
        # Validate JSON
        try:
            obj = json.loads(schema_text)
            args_schema = json.dumps(obj, ensure_ascii=False)
            # write sidecar
            sidecar = mapjson_sidecar_path(path)
            with open(sidecar, 'w', encoding='utf-8') as f:
                f.write(args_schema)
        except Exception as e:
            status_load = 0
            # 提供更详细的错误信息，包括原始输出内容
            # 如果输出过长，只显示前500个字符
            preview = schema_text[:500] + "..." if len(schema_text) > 500 else schema_text
            load_error_msg = f"Invalid schema JSON: {e}\n原始输出内容:\n{preview}"

    upsert_script(
        filename=relative_path,
        script_type=stype,
        file_hash=file_hash,
        status_load=status_load,
        load_error_msg=load_error_msg,
        args_schema=args_schema,
    )


def should_ignore(path: str, ignore_patterns: list[str]) -> bool:
    """检查路径是否应该被忽略"""
    # 获取相对路径部分
    path_parts = path.split(os.sep)
    
    for pattern in ignore_patterns:
        pattern = pattern.strip()
        if not pattern or pattern.startswith('#'):
            continue
        
        # 检查路径中的任何部分是否匹配模式
        for part in path_parts:
            if fnmatch.fnmatch(part, pattern):
                return True
        
        # 也检查完整路径
        if fnmatch.fnmatch(path, pattern):
            return True
    
    return False


def get_ignore_patterns() -> list[str]:
    """从数据库获取忽略模式"""
    patterns_str = get_setting('scan_ignore_patterns')
    if not patterns_str:
        # 默认忽略模式
        return ['node_modules', '__pycache__', '.git', '.venv', '*.pyc', '.*']
    return [p.strip() for p in patterns_str.split('\n') if p.strip()]


def scan_once():
    ignore_patterns = get_ignore_patterns()
    
    for root in [Config.SCRIPTS_PY_DIR, Config.SCRIPTS_JS_DIR]:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            # 过滤要忽略的目录（就地修改dirnames可以阻止os.walk进入这些目录）
            dirnames[:] = [d for d in dirnames if not should_ignore(d, ignore_patterns)]
            
            for fn in filenames:
                if not (fn.endswith('.py') or fn.endswith('.js')):
                    continue
                
                path = os.path.join(dirpath, fn)
                
                # 检查文件是否应该被忽略
                if should_ignore(path, ignore_patterns):
                    continue
                
                parse_and_register(path)


def scanner_loop():
    ensure_dirs()
    init_db()
    while not STOP_EVENT.is_set():
        try:
            scan_once()
        except Exception as e:
            # simple stderr print; could be improved to gateway logs
            print(f"[scanner] error: {e}")
        time.sleep(Config.SCAN_INTERVAL_SEC)


def start_scanner() -> Thread:
    t = Thread(target=scanner_loop, daemon=True)
    t.start()
    return t


def stop_scanner():
    STOP_EVENT.set()
