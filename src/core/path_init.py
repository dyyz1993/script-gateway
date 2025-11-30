"""
路径初始化模块

负责在应用启动时设置正确的Python路径，确保所有模块可以正确导入
"""

import os
import sys
from typing import Optional


def get_project_root() -> str:
    """
    获取项目根目录路径
    
    Returns:
        项目根目录的绝对路径
    """
    # 从当前文件位置向上三级目录获取项目根目录
    # src/core/path_init.py -> src -> server-auto-load
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def setup_python_path(custom_path: Optional[str] = None) -> None:
    """
    设置Python路径，确保项目模块可以正确导入
    
    Args:
        custom_path: 自定义要添加到Python路径的路径，如果为None则使用项目根目录
    """
    if custom_path is None:
        custom_path = get_project_root()
    
    # 确保路径是绝对路径
    abs_path = os.path.abspath(custom_path)
    
    # 检查路径是否已在Python路径中
    if abs_path not in sys.path:
        sys.path.insert(0, abs_path)


def setup_special_paths() -> None:
    """
    设置特殊模块需要的路径
    
    为一些需要特殊路径处理的模块设置额外的Python路径
    """
    project_root = get_project_root()
    
    # 为SenseVoiceSmall模块设置特殊路径
    sensevoice_path = os.path.join(project_root, "scripts_repo", "python", "SenseVoiceSmall")
    if os.path.exists(sensevoice_path) and sensevoice_path not in sys.path:
        sys.path.insert(0, sensevoice_path)


def initialize_paths() -> None:
    """
    初始化所有必要的路径设置
    
    在应用启动时调用此函数，确保所有模块可以正确导入
    """
    # 设置项目根目录到Python路径
    setup_python_path()
    
    # 设置特殊模块路径
    setup_special_paths()


def get_script_path(script_type: str, script_name: str) -> str:
    """
    获取脚本的完整路径
    
    Args:
        script_type: 脚本类型 ('python' 或 'js')
        script_name: 脚本文件名
        
    Returns:
        脚本的完整路径
    """
    project_root = get_project_root()
    
    if script_type == "python":
        return os.path.join(project_root, "scripts_repo", "python", script_name)
    elif script_type == "js":
        return os.path.join(project_root, "scripts_repo", "js", script_name)
    else:
        raise ValueError(f"不支持的脚本类型: {script_type}")


def ensure_path_importable(path: str) -> None:
    """
    确保指定路径可以导入
    
    如果路径不在Python路径中，则添加到Python路径
    
    Args:
        path: 要确保可导入的路径
    """
    abs_path = os.path.abspath(path)
    if os.path.exists(abs_path) and abs_path not in sys.path:
        sys.path.insert(0, abs_path)