#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import os
import sys
import json
import traceback
from typing import Dict, Any, Optional, Callable, Tuple
from functools import wraps
from enum import Enum

class ErrorType(Enum):
    """错误类型枚举"""
    VALIDATION = "validation"      # 参数验证错误
    EXECUTION = "execution"        # 执行错误
    TIMEOUT = "timeout"            # 超时错误
    RESOURCE = "resource"          # 资源错误（文件不存在等）
    PERMISSION = "permission"      # 权限错误
    SYSTEM = "system"              # 系统错误
    CUSTOM = "custom"              # 自定义错误


class ScriptError(Exception):
    """脚本执行错误基类"""
    
    def __init__(self, message: str, error_type: ErrorType = ErrorType.CUSTOM, code: int = 500, details: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.code = code
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "success": False,
            "error": self.message,
            "error_type": self.error_type.value,
            "code": self.code,
            "details": self.details
        }


class ValidationError(ScriptError):
    """参数验证错误"""
    
    def __init__(self, message: str, parameter: str = None, value: Any = None):
        details = {}
        if parameter:
            details["parameter"] = parameter
        if value is not None:
            details["value"] = str(value)
        
        super().__init__(
            message=message,
            error_type=ErrorType.VALIDATION,
            code=400,
            details=details
        )


class ExecutionError(ScriptError):
    """执行错误"""
    
    def __init__(self, message: str, command: str = None, exit_code: int = None):
        details = {}
        if command:
            details["command"] = command
        if exit_code is not None:
            details["exit_code"] = exit_code
        
        super().__init__(
            message=message,
            error_type=ErrorType.EXECUTION,
            code=500,
            details=details
        )


class ResourceError(ScriptError):
    """资源错误"""
    
    def __init__(self, message: str, resource_type: str = None, resource_path: str = None):
        details = {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_path:
            details["resource_path"] = resource_path
        
        super().__init__(
            message=message,
            error_type=ErrorType.RESOURCE,
            code=404,
            details=details
        )


class TimeoutError(ScriptError):
    """超时错误"""
    
    def __init__(self, message: str, timeout_seconds: int = None):
        details = {}
        if timeout_seconds is not None:
            details["timeout_seconds"] = timeout_seconds
        
        super().__init__(
            message=message,
            error_type=ErrorType.TIMEOUT,
            code=504,
            details=details
        )


class PermissionError(ScriptError):
    """权限错误"""
    
    def __init__(self, message: str, required_permission: str = None):
        details = {}
        if required_permission:
            details["required_permission"] = required_permission
        
        super().__init__(
            message=message,
            error_type=ErrorType.PERMISSION,
            code=403,
            details=details
        )


def handle_script_errors(func: Callable) -> Callable:
    """脚本错误处理装饰器
    
    捕获函数中的所有异常，转换为标准错误格式
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ScriptError as e:
            # 已经是标准错误格式，直接返回
            return e.to_dict()
        except KeyboardInterrupt:
            # 用户中断
            return ScriptError(
                message="脚本被用户中断",
                error_type=ErrorType.EXECUTION,
                code=130
            ).to_dict()
        except Exception as e:
            # 捕获所有其他异常
            error_msg = str(e)
            error_traceback = traceback.format_exc()
            
            return ScriptError(
                message=f"脚本执行出错: {error_msg}",
                error_type=ErrorType.SYSTEM,
                code=500,
                details={
                    "exception_type": type(e).__name__,
                    "traceback": error_traceback
                }
            ).to_dict()
    
    return wrapper


def validate_parameters(params: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """验证参数
    
    Args:
        params: 参数字典
        schema: 参数模式
        
    Returns:
        Tuple[是否有效, 错误信息]
    """
    for name, meta in schema.items():
        param_type = meta.get('type', 'str')
        required = meta.get('required', False)
        value = params.get(name)
        
        # 检查必需参数
        if required and (value is None or value == ''):
            return False, ValidationError(
                message=f"缺少必需参数: {name}",
                parameter=name
            ).to_dict()
        
        # 如果参数不存在且不是必需的，跳过验证
        if value is None or value == '':
            continue
        
        # 类型验证
        try:
            if param_type == 'int':
                params[name] = int(value)
            elif param_type == 'float':
                params[name] = float(value)
            elif param_type == 'bool':
                if isinstance(value, str):
                    params[name] = value.lower() in ['true', '1', 'yes', 'on']
                else:
                    params[name] = bool(value)
            # 文件类型和其他类型保持原样
        except ValueError:
            return False, ValidationError(
                message=f"参数 {name} 类型错误，期望 {param_type}",
                parameter=name,
                value=value
            ).to_dict()
    
    return True, None


def create_success_response(data: Any, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """创建成功响应"""
    response = {
        "success": True,
        "data": data
    }
    
    if metadata:
        response["metadata"] = metadata
    
    return response


def create_file_response(file_path: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """创建文件响应"""
    if not os.path.exists(file_path):
        return ResourceError(
            message="结果文件不存在",
            resource_path=file_path
        ).to_dict()
    
    try:
        file_size = os.path.getsize(file_path)
        file_url = convert_to_url(file_path)
        
        response = {
            "success": True,
            "type": "file",
            "url": file_url,
            "filename": os.path.basename(file_path),
            "size": file_size
        }
        
        if metadata:
            response["metadata"] = metadata
        
        return response
    except Exception as e:
        return ScriptError(
            message=f"处理文件响应时出错: {str(e)}",
            error_type=ErrorType.SYSTEM
        ).to_dict()


def convert_to_url(file_path: str) -> str:
    """将文件路径转换为URL"""
    from config import Config
    
    try:
        # 获取相对于BASE_DIR的路径
        abs_path = os.path.abspath(file_path)
        base_dir = os.path.abspath(Config.BASE_DIR)
        
        if not abs_path.startswith(base_dir):
            raise ValueError(f"文件路径不在项目目录内: {file_path}")
        
        rel_path = os.path.relpath(abs_path, base_dir)
        url = "/" + rel_path.replace(os.sep, "/")
        
        # 如果配置了base_url，则生成完整URL
        from .database import get_setting
        base_url = get_setting('base_url')
        if base_url:
            base_url = base_url.rstrip('/')
            url = base_url + url
        
        return url
    except Exception as e:
        raise ValueError(f"转换文件路径为URL失败: {str(e)}")


def print_json_response(response: Dict[str, Any]):
    """打印JSON响应到标准输出"""
    print(json.dumps(response, ensure_ascii=False, indent=2))
    if not response.get("success", False):
        sys.exit(1)