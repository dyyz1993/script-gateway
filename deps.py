import re
import json
import subprocess
import sys
import os
from typing import List, Dict, Any, Tuple

from database import get_conn
from config import Config


def list_python_deps() -> List[Dict[str, str]]:
    try:
        proc = subprocess.Popen([sys.executable, '-m', 'pip', 'freeze'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, _ = proc.communicate(timeout=30)
        lines = out.decode('utf-8', errors='ignore').splitlines()
        deps = []
        for ln in lines:
            if '==' in ln:
                name, ver = ln.split('==', 1)
                deps.append({'name': name, 'version': ver})
        return deps
    except Exception:
        return []


def parse_requirements_text(text: str) -> List[Dict[str, str]]:
    deps = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith('#'):
            continue
        # simple parser: name==version or name>=version etc.
        m = re.match(r'^([A-Za-z0-9_.\-]+)([<>=!~]{1,2}[=]?)(.+)$', ln)
        if m:
            name = m.group(1)
            version = ln[len(name):].strip()
            deps.append({'name': name, 'version': version})
        else:
            deps.append({'name': ln, 'version': ''})
    return deps


def detect_conflicts(installed: List[Dict[str, str]], requested: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    inst_map = {d['name'].lower(): d['version'] for d in installed}
    conflicts = []
    for r in requested:
        name = r['name'].lower()
        target = r['version']
        cur = inst_map.get(name)
        if cur and target and ('==' in target and cur != target.replace('==','')):
            conflicts.append({'name': r['name'], 'current': cur, 'target': target})
    return conflicts


def update_requirements_txt(new_deps: List[Dict[str, str]]) -> None:
    """安装成功后，将新依赖添加到 requirements.txt（去重）"""
    req_file = os.path.join(Config.BASE_DIR, 'requirements.txt')
    
    # 读取现有依赖
    existing = {}
    if os.path.exists(req_file):
        with open(req_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '==' in line:
                        name, ver = line.split('==', 1)
                        existing[name.lower()] = line
                    else:
                        existing[line.lower()] = line
    
    # 合并新依赖
    for dep in new_deps:
        name = dep['name']
        version = dep['version']
        spec = name + (version if version else '')
        existing[name.lower()] = spec
    
    # 写回文件（按字母排序）
    with open(req_file, 'w', encoding='utf-8') as f:
        for dep_spec in sorted(existing.values()):
            f.write(dep_spec + '\n')


def install_python_deps(deps: List[Dict[str, str]]) -> Tuple[str, int]:
    # Build command: python -m pip install name==version or name{specifier}
    cmd = [sys.executable, '-m', 'pip', 'install']
    for d in deps:
        spec = d['name'] + (d['version'] if d['version'] else '')
        cmd.append(spec)
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out, _ = proc.communicate()
        log = out.decode('utf-8', errors='ignore')
        status = 1 if proc.returncode == 0 else 2
        
        # 安装成功后，同步更新 requirements.txt
        if status == 1:
            try:
                update_requirements_txt(deps)
            except Exception as e:
                log += f"\n\nWarning: Failed to update requirements.txt: {str(e)}"
        
        # persist install log
        conn = get_conn()
        conn.execute(
            "INSERT INTO install_logs(runtime, requested_list, conflict_list, log_text, status, created_at) VALUES(?,?,?,?,?,datetime('now'))",
            ('python', json.dumps(deps, ensure_ascii=False), json.dumps([], ensure_ascii=False), log, status)
        )
        conn.commit()
        return log, status
    except Exception as e:
        log = str(e)
        conn = get_conn()
        conn.execute(
            "INSERT INTO install_logs(runtime, requested_list, conflict_list, log_text, status, created_at) VALUES(?,?,?,?,?,datetime('now'))",
            ('python', json.dumps(deps, ensure_ascii=False), json.dumps([], ensure_ascii=False), log, 2)
        )
        conn.commit()
        return log, 2


# JavaScript/Node.js 依赖管理

def list_node_deps() -> List[Dict[str, str]]:
    """列出已安装的Node.js依赖（只返回真正安装在node_modules中的包）"""
    try:
        # 使用 npm list 获取已安装的包
        proc = subprocess.Popen(
            ['npm', 'list', '--depth=0', '--json', '--parseable=false'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=Config.BASE_DIR
        )
        out, err = proc.communicate(timeout=30)
        
        # npm list 在有未安装包时返回码非0，但仍会输出JSON
        try:
            data = json.loads(out.decode('utf-8', errors='ignore'))
        except json.JSONDecodeError:
            return []
        
        deps = []
        if 'dependencies' in data:
            for name, info in data['dependencies'].items():
                # 只添加真正安装的包（有version字段且不是"missing"）
                if isinstance(info, dict):
                    version = info.get('version')
                    # 检查是否缺失（npm会标记missing的包）
                    if version and not info.get('missing', False):
                        deps.append({'name': name, 'version': version})
        return deps
    except Exception:
        return []


def parse_package_json(text: str) -> List[Dict[str, str]]:
    """解析package.json内容"""
    try:
        data = json.loads(text)
        deps = []
        # 合并dependencies和devDependencies
        all_deps = {}
        if 'dependencies' in data:
            all_deps.update(data['dependencies'])
        if 'devDependencies' in data:
            all_deps.update(data['devDependencies'])
        
        for name, version in all_deps.items():
            deps.append({'name': name, 'version': version})
        return deps
    except Exception:
        # 如果不是JSON，尝试逐行解析
        deps = []
        for ln in text.splitlines():
            ln = ln.strip()
            if not ln or ln.startswith('#') or ln.startswith('//'):
                continue
            # 简单解析：package@version 或 package
            if '@' in ln and not ln.startswith('@'):
                parts = ln.rsplit('@', 1)
                deps.append({'name': parts[0], 'version': '@' + parts[1] if len(parts) > 1 else ''})
            else:
                deps.append({'name': ln, 'version': ''})
        return deps


def install_node_deps(deps: List[Dict[str, str]]) -> Tuple[str, int]:
    """安装Node.js依赖"""
    cmd = ['npm', 'install']
    for d in deps:
        name = d['name']
        version = d.get('version', '')
        
        # npm install 格式：package@version 或 package
        if version:
            # 如果版本号不以@开头，添加@符号
            if not version.startswith('@'):
                spec = f"{name}@{version}"
            else:
                # 如果已经有@（如 @latest），直接拼接
                spec = f"{name}{version}"
        else:
            spec = name
        
        cmd.append(spec)
    
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=Config.BASE_DIR)
        out, _ = proc.communicate(timeout=300)  # npm安装可能较慢
        log = out.decode('utf-8', errors='ignore')
        status = 1 if proc.returncode == 0 else 2
        
        # 持久化安装日志
        conn = get_conn()
        conn.execute(
            "INSERT INTO install_logs(runtime, requested_list, conflict_list, log_text, status, created_at) VALUES(?,?,?,?,?,datetime('now'))",
            ('javascript', json.dumps(deps, ensure_ascii=False), json.dumps([], ensure_ascii=False), log, status)
        )
        conn.commit()
        return log, status
    except Exception as e:
        log = str(e)
        conn = get_conn()
        conn.execute(
            "INSERT INTO install_logs(runtime, requested_list, conflict_list, log_text, status, created_at) VALUES(?,?,?,?,?,datetime('now'))",
            ('javascript', json.dumps(deps, ensure_ascii=False), json.dumps([], ensure_ascii=False), log, 2)
        )
        conn.commit()
        return log, 2
