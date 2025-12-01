import re
import json
import subprocess
import sys
import os
import hashlib
import shutil
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

from ..core.database import get_conn
from ..core.config import Config


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


# ========== 脚本级依赖管理 ==========

class ScriptDepsManager:
    """脚本级依赖管理器"""
    
    def __init__(self):
        self.cache_base = os.path.join(Config.BASE_DIR, '.deps_cache')
        os.makedirs(self.cache_base, exist_ok=True)
    
    def get_script_deps_files(self, script_path: str) -> Dict[str, str]:
        """
        获取脚本相关的依赖文件路径
        返回: {'requirements': path, 'package': path}
        """
        script_dir = os.path.dirname(script_path)
        script_name = os.path.splitext(os.path.basename(script_path))[0]
        
        # 检查脚本同级目录
        deps_files = {}
        
        # Python requirements.txt（支持多种命名约定）
        req_patterns = ['requirements.txt', f'{script_name}_requirements.txt']
        for req_pattern in req_patterns:
            req_path = os.path.join(script_dir, req_pattern)
            if os.path.exists(req_path):
                deps_files['requirements'] = req_path
                break  # 找到第一个就停止
        
        # JavaScript package.json（支持多种命名约定）
        pkg_patterns = ['package.json', f'{script_name}_package.json']
        for pkg_pattern in pkg_patterns:
            pkg_path = os.path.join(script_dir, pkg_pattern)
            if os.path.exists(pkg_path):
                deps_files['package'] = pkg_path
                break  # 找到第一个就停止
        
        # 检查以脚本名命名的子目录
        script_subdir = os.path.join(script_dir, script_name)
        if os.path.isdir(script_subdir):
            req_sub = os.path.join(script_subdir, 'requirements.txt')
            pkg_sub = os.path.join(script_subdir, 'package.json')
            if os.path.exists(req_sub):
                deps_files['requirements'] = req_sub
            if os.path.exists(pkg_sub):
                deps_files['package'] = pkg_sub
        
        return deps_files
    
    def calculate_deps_hash(self, deps_list: List[Dict[str, str]]) -> str:
        """计算依赖列表的哈希值，用于缓存"""
        deps_str = json.dumps(sorted(deps_list, key=lambda x: x['name']), sort_keys=True)
        return hashlib.md5(deps_str.encode()).hexdigest()[:16]
    
    def get_cache_path(self, deps_hash: str, runtime: str) -> str:
        """获取缓存路径"""
        runtime_dir = 'python' if runtime == 'python' else 'nodejs'
        return os.path.join(self.cache_base, runtime_dir, deps_hash)
    
    def is_cache_valid(self, cache_path: str) -> bool:
        """检查缓存是否有效"""
        return os.path.exists(cache_path) and os.path.isdir(cache_path)
    
    def scan_script_dependencies(self, script_path: str) -> Dict[str, List[Dict[str, str]]]:
        """
        扫描脚本的依赖文件，返回依赖列表
        返回: {'python': [...], 'nodejs': [...]}
        """
        deps_files = self.get_script_deps_files(script_path)
        dependencies = {'python': [], 'nodejs': []}
        
        # Python 依赖
        if 'requirements' in deps_files:
            try:
                with open(deps_files['requirements'], 'r', encoding='utf-8') as f:
                    content = f.read()
                dependencies['python'] = parse_requirements_text(content)
            except Exception as e:
                print(f"解析requirements.txt失败: {e}")
        
        # Node.js 依赖
        if 'package' in deps_files:
            try:
                with open(deps_files['package'], 'r', encoding='utf-8') as f:
                    content = f.read()
                dependencies['nodejs'] = parse_package_json(content)
            except Exception as e:
                print(f"解析package.json失败: {e}")
        
        return dependencies
    
    def install_script_dependencies(self, script_path: str, force_reinstall: bool = False) -> Dict[str, Any]:
        """
        为脚本安装依赖
        返回安装结果和缓存信息
        """
        dependencies = self.scan_script_dependencies(script_path)
        result = {
            'script_path': script_path,
            'dependencies': dependencies,
            'installed': {'python': False, 'nodejs': False},
            'cache_info': {'python': None, 'nodejs': None},
            'errors': []
        }
        
        # 安装Python依赖
        if dependencies['python']:
            try:
                install_result = self._install_python_deps_with_cache(
                    dependencies['python'], force_reinstall
                )
                result['installed']['python'] = install_result['success']
                result['cache_info']['python'] = install_result.get('cache_path')
                if install_result.get('error'):
                    result['errors'].append(f"Python依赖安装失败: {install_result['error']}")
            except Exception as e:
                result['errors'].append(f"Python依赖安装异常: {str(e)}")
        
        # 安装Node.js依赖
        if dependencies['nodejs']:
            try:
                install_result = self._install_nodejs_deps_with_cache(
                    dependencies['nodejs'], force_reinstall
                )
                result['installed']['nodejs'] = install_result['success']
                result['cache_info']['nodejs'] = install_result.get('cache_path')
                if install_result.get('error'):
                    result['errors'].append(f"Node.js依赖安装失败: {install_result['error']}")
            except Exception as e:
                result['errors'].append(f"Node.js依赖安装异常: {str(e)}")
        
        return result
    
    def _install_python_deps_with_cache(self, deps: List[Dict[str, str]], force_reinstall: bool = False) -> Dict[str, Any]:
        """安装Python依赖并使用缓存"""
        deps_hash = self.calculate_deps_hash(deps)
        cache_path = self.get_cache_path(deps_hash, 'python')
        
        # 检查缓存
        if not force_reinstall and self.is_cache_valid(cache_path):
            return {'success': True, 'cache_path': cache_path, 'from_cache': True}
        
        try:
            # 创建缓存目录
            os.makedirs(cache_path, exist_ok=True)
            
            # 构建安装命令
            cmd = [sys.executable, '-m', 'pip', 'install', '--target', cache_path]
            for dep in deps:
                spec = dep['name'] + (dep['version'] if dep['version'] else '')
                cmd.append(spec)
            
            # 执行安装
            proc = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                env={**os.environ, 'PYTHONPATH': cache_path}
            )
            out, _ = proc.communicate(timeout=300)  # 5分钟超时
            
            if proc.returncode == 0:
                # 创建标记文件记录安装信息
                meta_file = os.path.join(cache_path, '.deps_meta.json')
                meta = {
                    'dependencies': deps,
                    'installed_at': str(os.path.getctime(cache_path)),
                    'install_log': out.decode('utf-8', errors='ignore')
                }
                with open(meta_file, 'w', encoding='utf-8') as f:
                    json.dump(meta, f, ensure_ascii=False, indent=2)
                
                return {'success': True, 'cache_path': cache_path, 'from_cache': False}
            else:
                # 安装失败，清理目录
                shutil.rmtree(cache_path, ignore_errors=True)
                return {'success': False, 'error': out.decode('utf-8', errors='ignore')}
                
        except subprocess.TimeoutExpired:
            shutil.rmtree(cache_path, ignore_errors=True)
            return {'success': False, 'error': '安装超时'}
        except Exception as e:
            shutil.rmtree(cache_path, ignore_errors=True)
            return {'success': False, 'error': str(e)}
    
    def _install_nodejs_deps_with_cache(self, deps: List[Dict[str, str]], force_reinstall: bool = False) -> Dict[str, Any]:
        """安装Node.js依赖并使用缓存"""
        deps_hash = self.calculate_deps_hash(deps)
        cache_path = self.get_cache_path(deps_hash, 'nodejs')
        
        # 检查缓存
        if not force_reinstall and self.is_cache_valid(cache_path):
            return {'success': True, 'cache_path': cache_path, 'from_cache': True}
        
        try:
            # 创建缓存目录
            os.makedirs(cache_path, exist_ok=True)
            
            # 构建package.json
            package_json = {
                'name': 'script-deps',
                'version': '1.0.0',
                'dependencies': {}
            }
            for dep in deps:
                package_json['dependencies'][dep['name']] = dep['version'] or 'latest'
            
            # 写入package.json
            pkg_file = os.path.join(cache_path, 'package.json')
            with open(pkg_file, 'w', encoding='utf-8') as f:
                json.dump(package_json, f, ensure_ascii=False, indent=2)
            
            # 执行npm install
            cmd = ['npm', 'install', '--prefix', cache_path]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=cache_path
            )
            out, _ = proc.communicate(timeout=300)
            
            if proc.returncode == 0:
                # 创建元数据文件
                meta_file = os.path.join(cache_path, '.deps_meta.json')
                meta = {
                    'dependencies': deps,
                    'installed_at': str(os.path.getctime(cache_path)),
                    'install_log': out.decode('utf-8', errors='ignore')
                }
                with open(meta_file, 'w', encoding='utf-8') as f:
                    json.dump(meta, f, ensure_ascii=False, indent=2)
                
                return {'success': True, 'cache_path': cache_path, 'from_cache': False}
            else:
                shutil.rmtree(cache_path, ignore_errors=True)
                return {'success': False, 'error': out.decode('utf-8', errors='ignore')}
                
        except subprocess.TimeoutExpired:
            shutil.rmtree(cache_path, ignore_errors=True)
            return {'success': False, 'error': '安装超时'}
        except Exception as e:
            shutil.rmtree(cache_path, ignore_errors=True)
            return {'success': False, 'error': str(e)}
    
    def get_execution_environment(self, script_path: str) -> Dict[str, Any]:
        """
        获取脚本执行环境信息
        返回包含Python路径和NODE_PATH等的环境变量
        """
        dependencies = self.scan_script_dependencies(script_path)
        env_info = {
            'python_path': None,
            'node_path': None,
            'extra_env': {}
        }
        
        # Python环境
        if dependencies['python']:
            deps_hash = self.calculate_deps_hash(dependencies['python'])
            cache_path = self.get_cache_path(deps_hash, 'python')
            if self.is_cache_valid(cache_path):
                env_info['python_path'] = cache_path
                env_info['extra_env']['PYTHONPATH'] = cache_path
        
        # Node.js环境
        if dependencies['nodejs']:
            deps_hash = self.calculate_deps_hash(dependencies['nodejs'])
            cache_path = self.get_cache_path(deps_hash, 'nodejs')
            if self.is_cache_valid(cache_path):
                node_modules = os.path.join(cache_path, 'node_modules')
                if os.path.exists(node_modules):
                    env_info['node_path'] = node_modules
                    env_info['extra_env']['NODE_PATH'] = node_modules
        
        return env_info
    
    def cleanup_cache(self, max_age_days: int = 30) -> Dict[str, Any]:
        """清理过期的依赖缓存"""
        import time
        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 3600
        
        cleaned = {'python': 0, 'nodejs': 0, 'total_size_mb': 0}
        
        for runtime in ['python', 'nodejs']:
            runtime_dir = os.path.join(self.cache_base, runtime)
            if not os.path.exists(runtime_dir):
                continue
                
            for cache_dir in os.listdir(runtime_dir):
                cache_path = os.path.join(runtime_dir, cache_dir)
                if not os.path.isdir(cache_path):
                    continue
                
                # 检查目录年龄
                try:
                    dir_age = current_time - os.path.getctime(cache_path)
                    if dir_age > max_age_seconds:
                        # 计算目录大小
                        dir_size = sum(
                            os.path.getsize(os.path.join(dirpath, filename))
                            for dirpath, _, filenames in os.walk(cache_path)
                            for filename in filenames
                            if os.path.isfile(os.path.join(dirpath, filename))
                        )
                        
                        shutil.rmtree(cache_path)
                        cleaned[runtime] += 1
                        cleaned['total_size_mb'] += dir_size / (1024 * 1024)
                except Exception:
                    continue
        
        return cleaned


# 全局实例
script_deps_manager = ScriptDepsManager()


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
