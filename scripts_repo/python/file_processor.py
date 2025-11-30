#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
文件处理脚本 - 支持文件上传、转换和下载
使用说明:
1. 支持多种文件格式输入和输出
2. 可以进行文件格式转换
3. 支持文件压缩和解压
4. 提供文件预览功能
"""

import argparse
import json
import sys
import os
from typing import Dict, Any, Optional, Union
from pathlib import Path
import traceback
import zipfile
import shutil
from datetime import datetime

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
    # 输入文件参数
    "input_file": {"flag": "--input-file", "type": "file", "required": True, "help": "输入文件路径"},
    
    # 输出目录参数
    "output_dir": {"flag": "--output-dir", "type": "str", "required": False, "help": "输出目录", "default": "./output"},
    
    # 操作类型
    "operation": {"flag": "--operation", "type": "choice", "required": False, "help": "操作类型", 
                  "choices": ["convert", "compress", "extract", "info", "preview"], "default": "info"},
    
    # 转换格式（当operation为convert时使用）
    "target_format": {"flag": "--target-format", "type": "choice", "required": False, "help": "目标格式", 
                     "choices": ["txt", "json", "csv", "xml"], "default": "txt"},
    
    # 压缩选项（当operation为compress时使用）
    "compression_type": {"flag": "--compression-type", "type": "choice", "required": False, "help": "压缩类型", 
                        "choices": ["zip", "tar", "gzip"], "default": "zip"},
    
    # 预览行数（当operation为preview时使用）
    "preview_lines": {"flag": "--preview-lines", "type": "int", "required": False, "help": "预览行数", "default": 10},
    
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
    验证文件操作相关的参数
    """
    input_file = params.get('input_file')
    if not input_file:
        return False, ValidationError(
            message="必须指定输入文件",
            parameter="input_file",
            value=input_file
        ).to_dict()
    
    if not os.path.exists(input_file):
        return False, ValidationError(
            message="输入文件不存在",
            parameter="input_file",
            value=input_file
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
    
    # 验证预览行数
    preview_lines = params.get('preview_lines', 10)
    if preview_lines <= 0:
        return False, ValidationError(
            message="预览行数必须大于0",
            parameter="preview_lines",
            value=preview_lines
        ).to_dict()
    
    return True, None


def get_file_info(file_path: str) -> Dict[str, Any]:
    """获取文件详细信息"""
    path = Path(file_path)
    stat = path.stat()
    
    return {
        "name": path.name,
        "size": stat.st_size,
        "size_human": _format_size(stat.st_size),
        "extension": path.suffix.lower(),
        "absolute_path": str(path.absolute()),
        "created_time": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "is_text": _is_text_file(path),
        "is_image": path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'],
        "is_archive": path.suffix.lower() in ['.zip', '.tar', '.gz', '.rar', '.7z']
    }


def _format_size(size_bytes: int) -> str:
    """格式化文件大小为人类可读格式"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _is_text_file(path: Path) -> bool:
    """判断是否为文本文件"""
    text_extensions = ['.txt', '.json', '.csv', '.xml', '.html', '.htm', '.py', '.js', '.css', '.md']
    return path.suffix.lower() in text_extensions


def preview_file(file_path: str, lines: int = 10) -> Dict[str, Any]:
    """预览文件内容"""
    path = Path(file_path)
    
    if not _is_text_file(path):
        return {
            "error": "无法预览非文本文件",
            "file_type": path.suffix
        }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content_lines = f.readlines()
            total_lines = len(content_lines)
            preview_lines = content_lines[:lines]
            
            return {
                "total_lines": total_lines,
                "preview_lines": len(preview_lines),
                "content": ''.join(preview_lines),
                "encoding": "utf-8"
            }
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='gbk') as f:
                content_lines = f.readlines()
                total_lines = len(content_lines)
                preview_lines = content_lines[:lines]
                
                return {
                    "total_lines": total_lines,
                    "preview_lines": len(preview_lines),
                    "content": ''.join(preview_lines),
                    "encoding": "gbk"
                }
        except Exception as e:
            return {
                "error": f"无法读取文件内容: {str(e)}",
                "file_type": path.suffix
            }
    except Exception as e:
        return {
            "error": f"读取文件时发生错误: {str(e)}",
            "file_type": path.suffix
        }


def convert_file(file_path: str, target_format: str, output_dir: str) -> Optional[str]:
    """转换文件格式"""
    path = Path(file_path)
    output_file = os.path.join(output_dir, f"{path.stem}.{target_format}")
    
    try:
        if target_format == "txt":
            # 转换为纯文本
            if _is_text_file(path):
                shutil.copy2(file_path, output_file)
            else:
                return None
        elif target_format == "json":
            # 转换为JSON格式
            file_info = get_file_info(file_path)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(file_info, f, ensure_ascii=False, indent=2)
        elif target_format == "csv":
            # 转换为CSV格式
            file_info = get_file_info(file_path)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("属性,值\n")
                for key, value in file_info.items():
                    f.write(f"{key},{value}\n")
        elif target_format == "xml":
            # 转换为XML格式
            file_info = get_file_info(file_path)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                f.write('<file>\n')
                for key, value in file_info.items():
                    f.write(f'  <{key}>{value}</{key}>\n')
                f.write('</file>\n')
        
        return output_file
    except Exception as e:
        return None


def compress_file(file_path: str, compression_type: str, output_dir: str) -> Optional[str]:
    """压缩文件"""
    path = Path(file_path)
    
    if compression_type == "zip":
        output_file = os.path.join(output_dir, f"{path.stem}.zip")
        try:
            with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(file_path, path.name)
            return output_file
        except Exception as e:
            return None
    else:
        # 其他压缩类型的实现可以在这里添加
        return None


def extract_file(file_path: str, output_dir: str) -> Optional[str]:
    """解压文件"""
    path = Path(file_path)
    
    if path.suffix.lower() == '.zip':
        extract_dir = os.path.join(output_dir, path.stem)
        try:
            with zipfile.ZipFile(file_path, 'r') as zipf:
                zipf.extractall(extract_dir)
            return extract_dir
        except Exception as e:
            return None
    else:
        # 其他压缩格式的解压实现可以在这里添加
        return None


def process_business_logic(params: Dict[str, Any]) -> Dict[str, Any]:
    """处理业务逻辑的核心函数"""
    input_file = params.get('input_file')
    output_dir = params.get('output_dir', './output')
    operation = params.get('operation', 'info')
    verbose = params.get('verbose', False)
    debug = params.get('debug', False)
    
    # 获取文件基本信息
    file_info = get_file_info(input_file)
    result_data = {
        "file_info": file_info,
        "operation": operation,
        "timestamp": datetime.now().isoformat()
    }
    
    # 根据操作类型执行不同的处理
    if operation == "info":
        # 只返回文件信息
        if verbose:
            result_data["message"] = "文件信息获取成功"
    
    elif operation == "preview":
        # 预览文件内容
        preview_lines = params.get('preview_lines', 10)
        preview_data = preview_file(input_file, preview_lines)
        result_data["preview"] = preview_data
        if verbose:
            result_data["message"] = f"文件预览成功，显示前{preview_lines}行"
    
    elif operation == "convert":
        # 转换文件格式
        target_format = params.get('target_format', 'txt')
        output_file = convert_file(input_file, target_format, output_dir)
        
        if output_file:
            result_data["conversion"] = {
                "success": True,
                "target_format": target_format,
                "output_file": output_file,
                "output_file_info": get_file_info(output_file)
            }
            if verbose:
                result_data["message"] = f"文件已转换为{target_format}格式"
        else:
            result_data["conversion"] = {
                "success": False,
                "target_format": target_format,
                "error": "文件转换失败"
            }
    
    elif operation == "compress":
        # 压缩文件
        compression_type = params.get('compression_type', 'zip')
        output_file = compress_file(input_file, compression_type, output_dir)
        
        if output_file:
            result_data["compression"] = {
                "success": True,
                "compression_type": compression_type,
                "output_file": output_file,
                "output_file_info": get_file_info(output_file)
            }
            if verbose:
                result_data["message"] = f"文件已压缩为{compression_type}格式"
        else:
            result_data["compression"] = {
                "success": False,
                "compression_type": compression_type,
                "error": "文件压缩失败"
            }
    
    elif operation == "extract":
        # 解压文件
        extract_dir = extract_file(input_file, output_dir)
        
        if extract_dir:
            result_data["extraction"] = {
                "success": True,
                "extract_dir": extract_dir,
                "extracted_files": []
            }
            
            # 列出解压后的文件
            try:
                for root, dirs, files in os.walk(extract_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        result_data["extraction"]["extracted_files"].append({
                            "name": file,
                            "path": file_path,
                            "size": os.path.getsize(file_path)
                        })
            except Exception as e:
                if debug:
                    result_data["extraction"]["list_error"] = str(e)
            
            if verbose:
                result_data["message"] = f"文件已解压到{extract_dir}"
        else:
            result_data["extraction"] = {
                "success": False,
                "error": "文件解压失败"
            }
    
    return result_data


def generate_output_file(params: Dict[str, Any], result_data: Dict[str, Any]) -> Optional[str]:
    """生成输出文件（可选）"""
    output_dir = params.get('output_dir', './output')
    operation = params.get('operation', 'info')
    
    # 对于某些操作，生成结果文件
    if operation in ["info", "preview"]:
        output_file = os.path.join(output_dir, 'file_operation_result.json')
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            return output_file
        except Exception as e:
            if params.get('debug', False):
                print(f"生成结果文件失败: {str(e)}", file=sys.stderr)
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
            resource_type="file_processing"
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
    parser = argparse.ArgumentParser(description='文件处理脚本 - 支持文件上传、转换和下载')
    
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