import os
import sys
import json
import subprocess
import shutil
import tempfile
from typing import Dict, Any, Optional, List
from pathlib import Path

from ..core.config import Config
from ..utils.deps import script_deps_manager


class ScriptEnvironmentManager:
    """脚本环境管理器，处理执行环境的创建和管理"""
    
    def __init__(self):
        self.temp_dir = os.path.join(Config.BASE_DIR, 'tmp', 'script_env')
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def create_execution_environment(self, script_path: str, script_id: int) -> Dict[str, Any]:
        """
        为脚本创建执行环境
        返回环境配置信息
        """
        env_info = {
            'script_path': script_path,
            'script_id': script_id,
            'working_dir': os.path.dirname(script_path),
            'env_vars': {},
            'python_path': sys.executable,
            'node_path': 'node',
            'deps_info': {},
            'isolation_dir': None
        }
        
        # 获取依赖信息
        deps_result = script_deps_manager.install_script_dependencies(script_path)
        env_info['deps_info'] = deps_result
        
        # 获取执行环境
        exec_env = script_deps_manager.get_execution_environment(script_path)
        
        # 设置环境变量
        base_env = os.environ.copy()
        
        # Python环境
        if exec_env['python_path']:
            python_path = exec_env['python_path']
            current_pythonpath = base_env.get('PYTHONPATH', '')
            if current_pythonpath:
                env_info['env_vars']['PYTHONPATH'] = f"{python_path}:{current_pythonpath}"
            else:
                env_info['env_vars']['PYTHONPATH'] = python_path
        
        # Node.js环境
        if exec_env['node_path']:
            node_path = exec_env['node_path']
            current_node_path = base_env.get('NODE_PATH', '')
            if current_node_path:
                env_info['env_vars']['NODE_PATH'] = f"{node_path}:{current_node_path}"
            else:
                env_info['env_vars']['NODE_PATH'] = node_path
        
        # 添加脚本相关环境变量
        env_info['env_vars'].update({
            'SCRIPT_PATH': script_path,
            'SCRIPT_ID': str(script_id),
            'SCRIPT_DIR': env_info['working_dir'],
            'BASE_DIR': Config.BASE_DIR
        })
        
        return env_info
    
    def execute_script_with_env(self, env_info: Dict[str, Any], args: List[str], 
                              timeout: int = None) -> Dict[str, Any]:
        """
        使用指定环境执行脚本
        """
        script_path = env_info['script_path']
        working_dir = env_info['working_dir']
        env_vars = env_info['env_vars']
        
        # 准备环境变量
        execution_env = os.environ.copy()
        execution_env.update(env_vars)
        
        # 确定执行命令
        if script_path.endswith('.py'):
            cmd = [env_info['python_path'], script_path] + args
        elif script_path.endswith('.js'):
            cmd = [env_info['node_path'], script_path] + args
        else:
            raise ValueError(f"不支持的脚本类型: {script_path}")
        
        try:
            # 执行脚本
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=working_dir,
                env=execution_env,
                text=False,
                bufsize=0
            )
            
            # 设置超时
            if timeout is None:
                timeout = Config.TIMEOUT_MIN * 60  # 转换为秒
            
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
                return_code = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                return_code = -1  # 超时标记
            
            return {
                'success': return_code == 0,
                'return_code': return_code,
                'stdout': stdout,
                'stderr': stderr,
                'timeout': return_code == -1,
                'command': cmd,
                'env_used': env_vars
            }
            
        except Exception as e:
            return {
                'success': False,
                'return_code': -2,
                'stdout': '',
                'stderr': str(e),
                'timeout': False,
                'command': cmd,
                'env_used': env_vars
            }
    
    def cleanup_environment(self, env_info: Dict[str, Any]):
        """清理执行环境"""
        # 目前主要是清理临时文件
        pass
    
    def validate_dependencies(self, script_path: str) -> Dict[str, Any]:
        """
        验证脚本的依赖是否正确安装
        """
        validation_result = {
            'script_path': script_path,
            'valid': True,
            'issues': [],
            'missing_deps': [],
            'conflicts': []
        }
        
        # 获取依赖信息
        deps_info = script_deps_manager.scan_script_dependencies(script_path)
        
        # 检查Python依赖
        if deps_info['python']:
            python_env = script_deps_manager.get_execution_environment(script_path)
            if not python_env['python_path']:
                validation_result['valid'] = False
                validation_result['issues'].append('Python依赖未正确安装')
                validation_result['missing_deps'].extend(deps_info['python'])
        
        # 检查Node.js依赖
        if deps_info['nodejs']:
            nodejs_env = script_deps_manager.get_execution_environment(script_path)
            if not nodejs_env['node_path']:
                validation_result['valid'] = False
                validation_result['issues'].append('Node.js依赖未正确安装')
                validation_result['missing_deps'].extend(deps_info['nodejs'])
        
        return validation_result
    
    def get_script_info(self, script_path: str) -> Dict[str, Any]:
        """
        获取脚本的详细信息，包括依赖状态
        """
        # 扫描依赖
        dependencies = script_deps_manager.scan_script_dependencies(script_path)
        
        # 获取执行环境
        env_info = script_deps_manager.get_execution_environment(script_path)
        
        # 验证依赖
        validation = self.validate_dependencies(script_path)
        
        return {
            'script_path': script_path,
            'script_type': 'python' if script_path.endswith('.py') else 'nodejs',
            'dependencies': dependencies,
            'environment': env_info,
            'validation': validation,
            'deps_files': script_deps_manager.get_script_deps_files(script_path)
        }
    
    def batch_install_dependencies(self, script_paths: List[str], 
                                force_reinstall: bool = False) -> Dict[str, Any]:
        """
        批量安装多个脚本的依赖
        """
        results = {
            'total': len(script_paths),
            'successful': 0,
            'failed': 0,
            'details': {}
        }
        
        for script_path in script_paths:
            try:
                install_result = script_deps_manager.install_script_dependencies(
                    script_path, force_reinstall
                )
                results['details'][script_path] = install_result
                
                # 检查是否所有依赖都安装成功
                all_success = (
                    (not install_result['dependencies']['python'] or install_result['installed']['python']) and
                    (not install_result['dependencies']['nodejs'] or install_result['installed']['nodejs'])
                )
                
                if all_success and not install_result['errors']:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                    
            except Exception as e:
                results['details'][script_path] = {
                    'error': str(e),
                    'installed': {'python': False, 'nodejs': False}
                }
                results['failed'] += 1
        
        return results


# 全局实例
script_env_manager = ScriptEnvironmentManager()
