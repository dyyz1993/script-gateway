#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Python 脚本模板 - 支持参数验证、错误处理和多种响应格式
使用说明:
1. 定义 ARGS_MAP 字典来描述命令行参数
2. 实现 process_request 函数处理业务逻辑
3. 使用 handle_script_errors 装饰器自动处理异常
4. 支持 --_sys_get_schema 参数输出 JSON 格式的参数定义
"""

import argparse
import json
import sys
import os
from typing import Dict, Any, Optional, Union
from pathlib import Path
import traceback

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
    create_binary_response,
    print_json_response
)

# =============================================================================
# 参数定义区域
# =============================================================================

# 参数定义映射表
# 支持的参数类型: str, int, float, bool, file, url, json
# 
# 示例参数类型:
# 1. 基本类型: str, int, float, bool
#    "name": {"flag": "--name", "type": "str", "required": True, "help": "姓名"}
#    "age": {"flag": "--age", "type": "int", "required": False, "help": "年龄", "default": 18}
#    "height": {"flag": "--height", "type": "float", "required": False, "help": "身高", "default": 170.5}
#    "enabled": {"flag": "--enabled", "type": "bool", "required": False, "help": "是否启用", "default": False}
#
# 2. 文件路径: file
#    "image": {"flag": "--image", "type": "file", "required": True, "help": "图片文件路径"}
#    "config": {"flag": "--config", "type": "file", "required": False, "help": "配置文件路径", "default": "config.json"}
#
# 3. URL: url
#    "api_url": {"flag": "--api-url", "type": "url", "required": True, "help": "API接口地址"}
#
# 4. JSON: json
#    "data": {"flag": "--data", "type": "json", "required": False, "help": "JSON格式数据", "default": "{}"}
#
# 5. 选择项: choice (需要指定 choices 列表)
#    "format": {"flag": "--format", "type": "choice", "required": False, "help": "输出格式", 
#               "choices": ["json", "xml", "csv"], "default": "json"}

ARGS_MAP = {
    # 基本参数示例
    "name": {"flag": "--name", "type": "str", "required": True, "help": "姓名，不能为空"},
    "age": {"flag": "--age", "type": "int", "required": False, "help": "年龄，必须大于0", "default": 18},
    "email": {"flag": "--email", "type": "str", "required": False, "help": "电子邮箱地址"},
    
    # 文件参数示例
    "input_file": {"flag": "--input-file", "type": "file", "required": False, "help": "输入文件路径"},
    "output_dir": {"flag": "--output-dir", "type": "str", "required": False, "help": "输出目录", "default": "./output"},
    
    # URL 参数示例
    "api_url": {"flag": "--api-url", "type": "url", "required": False, "help": "API接口地址"},
    
    # JSON 参数示例
    "metadata": {"flag": "--metadata", "type": "json", "required": False, "help": "元数据(JSON格式)", "default": "{}"},
    
    # 布尔参数示例
    "verbose": {"flag": "--verbose", "type": "bool", "required": False, "help": "详细输出模式", "default": False},
    "debug": {"flag": "--debug", "type": "bool", "required": False, "help": "调试模式", "default": False},
    
    # 选择项示例
    "format": {"flag": "--format", "type": "choice", "required": False, "help": "输出格式", 
               "choices": ["json", "xml", "csv"], "default": "json"},
}

# =============================================================================
# 辅助函数区域
# =============================================================================

def get_schema() -> str:
    """
    返回参数定义的JSON格式字符串
    用于系统自动获取参数定义
    """
    return json.dumps(ARGS_MAP, ensure_ascii=False)


def validate_custom_parameters(params: Dict[str, Any]) -> tuple[bool, Optional[Dict[str, Any]]]:
    """
    自定义参数验证函数
    在标准验证之后执行，用于业务逻辑相关的验证
    
    Args:
        params: 参数字典
        
    Returns:
        tuple: (是否验证通过, 错误结果字典)
    """
    # 示例1: 验证姓名不为空且长度合理
    name = params.get('name')
    if not name or not name.strip():
        return False, ValidationError(
            message="姓名不能为空",
            parameter="name",
            value=name
        ).to_dict()
    
    if len(name) > 100:
        return False, ValidationError(
            message="姓名长度不能超过100个字符",
            parameter="name",
            value=name
        ).to_dict()
    
    # 示例2: 验证年龄范围
    age = params.get('age')
    if age is not None and (age < 0 or age > 150):
        return False, ValidationError(
            message="年龄必须在0-150之间",
            parameter="age",
            value=age
        ).to_dict()
    
    # 示例3: 验证邮箱格式
    email = params.get('email')
    if email and '@' not in email:
        return False, ValidationError(
            message="邮箱格式不正确",
            parameter="email",
            value=email
        ).to_dict()
    
    # 示例4: 验证输入文件是否存在
    input_file = params.get('input_file')
    if input_file and not os.path.exists(input_file):
        return False, ValidationError(
            message="输入文件不存在",
            parameter="input_file",
            value=input_file
        ).to_dict()
    
    # 示例5: 验证输出目录是否存在，不存在则创建
    output_dir = params.get('output_dir')
    if output_dir:
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
    
    # 示例6: 验证URL格式
    api_url = params.get('api_url')
    if api_url and not (api_url.startswith('http://') or api_url.startswith('https://')):
        return False, ValidationError(
            message="URL必须以http://或https://开头",
            parameter="api_url",
            value=api_url
        ).to_dict()
    
    # 所有验证通过
    return True, None


def process_business_logic(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理业务逻辑的核心函数
    
    Args:
        params: 验证后的参数字典
        
    Returns:
        Dict: 业务处理结果数据
    """
    # 示例1: 基本数据处理
    name = params.get('name', '').strip()
    age = params.get('age', 18)
    email = params.get('email', '')
    verbose = params.get('verbose', False)
    debug = params.get('debug', False)
    format_type = params.get('format', 'json')
    
    # 示例2: 文件处理
    input_file = params.get('input_file')
    file_info = None
    if input_file:
        file_path = Path(input_file)
        if file_path.exists():
            file_info = {
                "name": file_path.name,
                "size": file_path.stat().st_size,
                "extension": file_path.suffix,
                "absolute_path": str(file_path.absolute())
            }
    
    # 示例3: 元数据处理
    metadata = params.get('metadata', {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    
    # 示例4: 构建响应数据
    result_data = {
        "user_info": {
            "name": name,
            "age": age,
            "email": email
        },
        "processing_info": {
            "format": format_type,
            "verbose": verbose,
            "debug": debug
        }
    }
    
    # 添加文件信息（如果有）
    if file_info:
        result_data["file_info"] = file_info
    
    # 添加元数据（如果有）
    if metadata:
        result_data["metadata"] = metadata
    
    # 示例5: 根据不同格式返回不同结果
    if format_type == "json":
        return result_data
    elif format_type == "xml":
        # 这里可以转换为XML格式
        result_data["xml_output"] = "<user><name>{}</name><age>{}</age></user>".format(name, age)
        return result_data
    elif format_type == "csv":
        # 这里可以转换为CSV格式
        result_data["csv_output"] = "name,age,email\n{},{},{}".format(name, age, email)
        return result_data
    
    return result_data


def generate_output_file(params: Dict[str, Any], result_data: Dict[str, Any]) -> Optional[str]:
    """
    生成输出文件（可选）
    
    Args:
        params: 参数字典
        result_data: 处理结果数据
        
    Returns:
        Optional[str]: 生成的文件路径，如果没有生成文件则返回None
    """
    output_dir = params.get('output_dir', './output')
    format_type = params.get('format', 'json')
    
    # 示例1: 生成JSON文件
    if format_type == 'json':
        output_file = os.path.join(output_dir, 'result.json')
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            return output_file
        except Exception as e:
            if params.get('debug', False):
                print(f"生成JSON文件失败: {str(e)}", file=sys.stderr)
            return None
    
    # 示例2: 生成CSV文件
    elif format_type == 'csv':
        output_file = os.path.join(output_dir, 'result.csv')
        try:
            user_info = result_data.get('user_info', {})
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("name,age,email\n")
                f.write("{},{},{}\n".format(
                    user_info.get('name', ''),
                    user_info.get('age', ''),
                    user_info.get('email', '')
                ))
            return output_file
        except Exception as e:
            if params.get('debug', False):
                print(f"生成CSV文件失败: {str(e)}", file=sys.stderr)
            return None
    
    return None


# =============================================================================
# 主要处理函数
# =============================================================================

@handle_script_errors
def process_request(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理请求的主函数
    包含参数验证、业务逻辑处理和结果生成
    
    Args:
        params: 参数字典
        
    Returns:
        Dict: 处理结果，可能是成功响应、错误响应或文件响应
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
            resource_type="business_logic"
        ).to_dict()
    
    # 4. 生成输出文件（如果需要）
    output_file = generate_output_file(params, result_data)
    
    # 5. 根据不同情况返回不同类型的响应
    if output_file:
        # 如果生成了文件，返回文件响应
        return create_file_response(
            data=result_data,
            file_path=output_file,
            message="处理成功，结果已保存到文件"
        )
    else:
        # 否则返回标准成功响应
        return create_success_response(
            data=result_data,
            message="处理成功"
        )


# =============================================================================
# 入口函数
# =============================================================================

def main():
    """主函数 - 处理命令行参数并调用处理函数"""
    # 1. 创建参数解析器
    parser = argparse.ArgumentParser(description='Python脚本模板示例')
    
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