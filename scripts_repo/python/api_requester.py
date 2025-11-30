#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API请求脚本 - 支持API请求和响应处理
使用说明:
1. 支持多种HTTP方法（GET, POST, PUT, DELETE等）
2. 支持请求头和请求体配置
3. 支持认证和授权
4. 支持响应数据处理和保存
"""

import argparse
import json
import sys
import os
from typing import Dict, Any, Optional, Union, List
from pathlib import Path
import traceback
import requests
from datetime import datetime
import base64

# 添加项目根目录到Python路径，以便导入error_handler模块
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.core.error_handler import (
    handle_script_errors, 
    ValidationError, 
    ResourceError, 
    ScriptError, 
    ErrorType,
    validate_parameters,
    create_success_response,
    create_file_response,
    print_json_response
)

# =============================================================================
# 参数定义区域
# =============================================================================

ARGS_MAP = {
    # API端点
    "url": {"flag": "--url", "type": "url", "required": True, "help": "API端点URL"},
    
    # HTTP方法
    "method": {"flag": "--method", "type": "choice", "required": False, "help": "HTTP方法", 
              "choices": ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"], "default": "GET"},
    
    # 请求头
    "headers": {"flag": "--headers", "type": "json", "required": False, "help": "请求头(JSON格式)", "default": "{}"},
    
    # 请求体
    "data": {"flag": "--data", "type": "json", "required": False, "help": "请求体数据(JSON格式)", "default": "{}"},
    
    # 查询参数
    "params": {"flag": "--params", "type": "json", "required": False, "help": "查询参数(JSON格式)", "default": "{}"},
    
    # 认证类型
    "auth_type": {"flag": "--auth-type", "type": "choice", "required": False, "help": "认证类型", 
                 "choices": ["none", "basic", "bearer", "api_key"], "default": "none"},
    
    # 认证信息
    "auth_info": {"flag": "--auth-info", "type": "json", "required": False, "help": "认证信息(JSON格式)", "default": "{}"},
    
    # 输出目录
    "output_dir": {"flag": "--output-dir", "type": "str", "required": False, "help": "输出目录", "default": "./output"},
    
    # 响应处理选项
    "save_response": {"flag": "--save-response", "type": "bool", "required": False, "help": "保存响应到文件", "default": False},
    "extract_data": {"flag": "--extract-data", "type": "str", "required": False, "help": "从响应中提取数据的JSON路径(如data.items)"},
    
    # 超时设置
    "timeout": {"flag": "--timeout", "type": "int", "required": False, "help": "请求超时时间(秒)", "default": 30},
    
    # 其他选项
    "verbose": {"flag": "--verbose", "type": "bool", "required": False, "help": "详细输出模式", "default": False},
    "debug": {"flag": "--debug", "type": "bool", "required": False, "help": "调试模式", "default": False},
}

# =============================================================================
# 辅助函数区域
# =============================================================================

def get_schema() -> str:
    """返回参数定义的JSON格式字符串"""
    return json.dumps(ARGS_MAP, ensure_ascii=False)


def validate_custom_parameters(params: Dict[str, Any]) -> tuple[bool, Optional[Dict[str, Any]]]:
    """
    自定义参数验证函数
    验证API请求相关的参数
    """
    url = params.get('url')
    if not url:
        return False, ValidationError(
            message="必须指定API端点URL",
            parameter="url",
            value=url
        ).to_dict()
    
    # 验证超时时间
    timeout = params.get('timeout', 30)
    if timeout <= 0:
        return False, ValidationError(
            message="超时时间必须大于0",
            parameter="timeout",
            value=timeout
        ).to_dict()
    
    # 验证认证信息
    auth_type = params.get('auth_type', 'none')
    auth_info = params.get('auth_info', {})
    
    if auth_type == "basic":
        if not auth_info.get('username') or not auth_info.get('password'):
            return False, ValidationError(
                message="Basic认证需要用户名和密码",
                parameter="auth_info",
                value=auth_info
            ).to_dict()
    
    elif auth_type == "bearer":
        if not auth_info.get('token'):
            return False, ValidationError(
                message="Bearer认证需要访问令牌",
                parameter="auth_info",
                value=auth_info
            ).to_dict()
    
    elif auth_type == "api_key":
        if not auth_info.get('key') or not auth_info.get('value'):
            return False, ValidationError(
                message="API Key认证需要键名和键值",
                parameter="auth_info",
                value=auth_info
            ).to_dict()
    
    # 验证输出目录，不存在则创建
    output_dir = params.get('output_dir', './output')
    output_path = Path(output_dir)
    if not output_path.exists():
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return False, ValidationError(
                message=f"无法创建输出目录: {str(e)}",
                parameter="output_dir",
                value=output_dir
            ).to_dict()
    
    return True, None


def setup_authentication(auth_type: str, auth_info: Dict[str, Any]) -> Optional[Union[requests.auth.HTTPBasicAuth, Dict[str, str]]]:
    """设置认证信息"""
    if auth_type == "none":
        return None
    elif auth_type == "basic":
        username = auth_info.get('username')
        password = auth_info.get('password')
        return requests.auth.HTTPBasicAuth(username, password)
    elif auth_type == "bearer":
        token = auth_info.get('token')
        return {"Authorization": f"Bearer {token}"}
    elif auth_type == "api_key":
        key = auth_info.get('key')
        value = auth_info.get('value')
        return {key: value}
    
    return None


def extract_data_from_response(response_data: Any, extract_path: str) -> Any:
    """从响应中提取指定路径的数据"""
    if not extract_path:
        return response_data
    
    try:
        # 分割路径
        path_parts = extract_path.split('.')
        current_data = response_data
        
        for part in path_parts:
            if isinstance(current_data, dict) and part in current_data:
                current_data = current_data[part]
            elif isinstance(current_data, list) and part.isdigit():
                index = int(part)
                if 0 <= index < len(current_data):
                    current_data = current_data[index]
                else:
                    return None
            else:
                return None
        
        return current_data
    except Exception:
        return None


def save_response_to_file(response: requests.Response, output_dir: str, url: str) -> Optional[str]:
    """保存响应到文件"""
    try:
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        url_hash = abs(hash(url)) % 10000  # 简单的URL哈希
        filename = f"api_response_{timestamp}_{url_hash}.json"
        output_file = os.path.join(output_dir, filename)
        
        # 准备保存的数据
        response_data = {
            "url": url,
            "method": response.request.method,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "timestamp": datetime.now().isoformat()
        }
        
        # 尝试解析响应体
        try:
            if response.headers.get('content-type', '').startswith('application/json'):
                response_data["body"] = response.json()
            else:
                # 对于非JSON响应，保存为base64编码的字符串
                response_data["body_base64"] = base64.b64encode(response.content).decode('utf-8')
                response_data["content_type"] = response.headers.get('content-type', '')
        except Exception:
            response_data["body_base64"] = base64.b64encode(response.content).decode('utf-8')
            response_data["content_type"] = response.headers.get('content-type', '')
        
        # 保存到文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(response_data, f, ensure_ascii=False, indent=2)
        
        return output_file
    except Exception as e:
        return None


def process_business_logic(params: Dict[str, Any]) -> Dict[str, Any]:
    """处理业务逻辑的核心函数"""
    url = params.get('url')
    method = params.get('method', 'GET')
    
    # 解析JSON参数
    headers = params.get('headers', '{}')
    if isinstance(headers, str):
        try:
            headers = json.loads(headers)
        except json.JSONDecodeError:
            headers = {}
    
    data = params.get('data', '{}')
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            data = {}
    
    query_params = params.get('params', '{}')
    if isinstance(query_params, str):
        try:
            query_params = json.loads(query_params)
        except json.JSONDecodeError:
            query_params = {}
    
    auth_type = params.get('auth_type', 'none')
    
    auth_info = params.get('auth_info', '{}')
    if isinstance(auth_info, str):
        try:
            auth_info = json.loads(auth_info)
        except json.JSONDecodeError:
            auth_info = {}
    output_dir = params.get('output_dir', './output')
    save_response = params.get('save_response', False)
    extract_data_path = params.get('extract_data', '')
    timeout = params.get('timeout', 30)
    verbose = params.get('verbose', False)
    debug = params.get('debug', False)
    
    # 设置认证
    auth = setup_authentication(auth_type, auth_info)
    
    # 如果认证返回的是字典（如Bearer或API Key），则添加到请求头
    if isinstance(auth, dict):
        headers.update(auth)
        auth = None  # 不再使用requests的auth参数
    
    # 准备请求参数
    request_params = {
        'method': method,
        'url': url,
        'headers': headers,
        'timeout': timeout
    }
    
    # 根据方法添加不同的参数
    if method.upper() in ['GET', 'DELETE', 'HEAD', 'OPTIONS']:
        if query_params:
            request_params['params'] = query_params
    elif method.upper() in ['POST', 'PUT', 'PATCH']:
        if data:
            request_params['json'] = data
        if query_params:
            request_params['params'] = query_params
    
    # 添加认证
    if auth:
        request_params['auth'] = auth
    
    # 记录请求信息
    request_info = {
        "method": method,
        "url": url,
        "headers": headers,
        "params": query_params,
        "data": data if method.upper() in ['POST', 'PUT', 'PATCH'] else None,
        "auth_type": auth_type,
        "timeout": timeout
    }
    
    result_data = {
        "request": request_info,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # 发送请求
        if verbose:
            print(f"发送{method}请求到: {url}")
        
        response = requests.request(**request_params)
        
        # 记录响应信息
        response_info = {
            "status_code": response.status_code,
            "status_text": f"{response.status_code} {response.reason}",
            "headers": dict(response.headers),
            "size": len(response.content),
            "elapsed": response.elapsed.total_seconds() if hasattr(response, 'elapsed') else None
        }
        
        result_data["response"] = response_info
        
        # 尝试解析响应体
        try:
            if response.headers.get('content-type', '').startswith('application/json'):
                response_data = response.json()
                result_data["response"]["data"] = response_data
                
                # 如果指定了提取路径，提取数据
                if extract_data_path:
                    extracted_data = extract_data_from_response(response_data, extract_data_path)
                    if extracted_data is not None:
                        result_data["extracted_data"] = extracted_data
                        result_data["extract_path"] = extract_data_path
                    else:
                        result_data["extract_error"] = f"无法从路径 '{extract_path}' 提取数据"
            else:
                # 对于非JSON响应，保存为base64编码的字符串
                result_data["response"]["body_base64"] = base64.b64encode(response.content).decode('utf-8')
                result_data["response"]["content_type"] = response.headers.get('content-type', '')
        except Exception as e:
            result_data["response"]["parse_error"] = str(e)
            result_data["response"]["body_base64"] = base64.b64encode(response.content).decode('utf-8')
        
        # 保存响应到文件（如果需要）
        if save_response:
            response_file = save_response_to_file(response, output_dir, url)
            if response_file:
                result_data["response_file"] = response_file
                if verbose:
                    result_data["message"] = f"请求完成，响应已保存到 {response_file}"
            else:
                result_data["save_error"] = "保存响应文件失败"
                if verbose:
                    result_data["message"] = "请求完成，但保存响应文件失败"
        else:
            if verbose:
                result_data["message"] = "请求完成"
        
        # 判断请求是否成功
        result_data["success"] = 200 <= response.status_code < 300
        
        return result_data
    
    except requests.exceptions.Timeout:
        error_info = {
            "type": "timeout",
            "message": f"请求超时 (超过 {timeout} 秒)"
        }
        result_data["error"] = error_info
        result_data["success"] = False
        return result_data
    
    except requests.exceptions.ConnectionError as e:
        error_info = {
            "type": "connection_error",
            "message": f"连接错误: {str(e)}"
        }
        result_data["error"] = error_info
        result_data["success"] = False
        return result_data
    
    except requests.exceptions.HTTPError as e:
        error_info = {
            "type": "http_error",
            "message": f"HTTP错误: {str(e)}"
        }
        result_data["error"] = error_info
        result_data["success"] = False
        return result_data
    
    except Exception as e:
        error_info = {
            "type": "unexpected_error",
            "message": f"意外错误: {str(e)}"
        }
        if debug:
            error_info["traceback"] = traceback.format_exc()
        
        result_data["error"] = error_info
        result_data["success"] = False
        return result_data


def generate_output_file(params: Dict[str, Any], result_data: Dict[str, Any]) -> Optional[str]:
    """生成输出文件（可选）"""
    output_dir = params.get('output_dir', './output')
    
    # 生成请求结果文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f'api_request_result_{timestamp}.json')
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        return output_file
    except Exception as e:
        if params.get('debug', False):
            print(f"生成结果文件失败: {str(e)}", file=sys.stderr)
        return None


# =============================================================================
# 主要处理函数
# =============================================================================

@handle_script_errors
def process_request(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理请求的主函数
    包含参数验证、业务逻辑处理和结果生成
    """
    # 1. 标准参数验证
    is_valid, error_result = validate_parameters(params, ARGS_MAP)
    if not is_valid:
        return error_result
    
    # 2. 自定义参数验证
    is_valid, error_result = validate_custom_parameters(params)
    if not is_valid:
        return error_result
    
    # 3. 处理业务逻辑
    try:
        result_data = process_business_logic(params)
    except Exception as e:
        if params.get('debug', False):
            print(f"业务逻辑处理失败: {str(e)}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
        
        return ResourceError(
            message=f"处理业务逻辑时发生错误: {str(e)}",
            resource_type="api_request"
        ).to_dict()
    
    # 4. 生成输出文件（如果需要）
    output_file = generate_output_file(params, result_data)
    
    # 5. 构建响应数据
    response_data = result_data
    if output_file:
        response_data["output_file"] = output_file
    
    # 返回成功响应
    return create_success_response(
        data=response_data
    )


# =============================================================================
# 入口函数
# =============================================================================

def main():
    """主函数 - 处理命令行参数并调用处理函数"""
    # 1. 创建参数解析器
    parser = argparse.ArgumentParser(description='API请求脚本 - 支持API请求和响应处理')
    
    # 2. 添加所有参数
    for key, cfg in ARGS_MAP.items():
        param_type = cfg.get("type", "str")
        required = cfg.get("required", False)
        default = cfg.get("default")
        help_text = cfg.get("help", "")
        
        # 根据参数类型添加不同的参数
        if param_type == "bool":
            # 布尔参数需要特殊处理
            parser.add_argument(
                cfg["flag"], 
                help=help_text,
                action='store_true',
                default=default
            )
        elif param_type == "choice" and "choices" in cfg:
            # 选择项参数
            parser.add_argument(
                cfg["flag"], 
                help=help_text,
                choices=cfg["choices"],
                default=default
            )
        else:
            # 其他类型参数
            parser.add_argument(
                cfg["flag"], 
                help=help_text,
                required=required,
                default=default
            )
    
    # 3. 处理特殊参数 --_sys_get_schema
    if len(sys.argv) > 1 and sys.argv[1] == "--_sys_get_schema":
        print(get_schema())
        sys.exit(0)
    
    # 4. 解析命令行参数
    args = parser.parse_args()
    
    # 5. 构建参数字典
    params = {}
    for key in ARGS_MAP.keys():
        value = getattr(args, key, None)
        if value is not None:
            params[key] = value
    
    # 6. 处理请求并打印结果
    result = process_request(params)
    print_json_response(result)


if __name__ == "__main__":
    main()