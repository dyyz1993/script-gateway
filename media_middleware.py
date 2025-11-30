#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import os
import json
from typing import Dict, Any, List, Tuple
from media_processor import MediaProcessor
from error_handler import ScriptError, ErrorType, handle_script_errors


class MediaProcessingMiddleware:
    """
    音视频处理中间件
    
    在脚本执行前处理音视频参数，支持本地文件和远程URL的统一处理
    """
    
    def __init__(self):
        self.media_processor = MediaProcessor()
    
    def process_script_params(self, script: Dict[str, Any], args_schema: Dict[str, Any], http_params: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        处理脚本参数，将音视频参数统一转换为本地文件路径
        
        Args:
            script: 脚本信息
            args_schema: 参数模式
            http_params: HTTP参数
            
        Returns:
            Tuple[处理后的参数, 处理信息]
        """
        processed_params = http_params.copy()
        processing_info = {
            "processed_media": [],
            "errors": []
        }
        
        # 遍历参数模式，查找音视频参数
        for param_name, param_meta in args_schema.items():
            param_type = param_meta.get('type', 'str')
            
            # 处理音视频参数
            if param_type in ['audio', 'video', 'media', 'file']:
                if param_name in processed_params:
                    param_value = processed_params[param_name]
                    
                    # 如果是数组，处理每个元素
                    if isinstance(param_value, list):
                        processed_files = []
                        for i, value in enumerate(param_value):
                            success, local_path, error = self._process_single_media_param(
                                value, f"{param_name}[{i}]", param_type
                            )
                            
                            if success:
                                processed_files.append(local_path)
                                processing_info["processed_media"].append({
                                    "param": f"{param_name}[{i}]",
                                    "original": value,
                                    "local_path": local_path,
                                    "type": self.media_processor.get_file_type(local_path)
                                })
                            else:
                                processing_info["errors"].append({
                                    "param": f"{param_name}[{i}]",
                                    "error": error
                                })
                                raise ScriptError(
                                    message=f"参数 {param_name}[{i}] 处理失败: {error}",
                                    error_type=ErrorType.VALIDATION
                                )
                        
                        processed_params[param_name] = processed_files
                    else:
                        # 处理单个值
                        success, local_path, error = self._process_single_media_param(
                            param_value, param_name, param_type
                        )
                        
                        if success:
                            processed_params[param_name] = local_path
                            processing_info["processed_media"].append({
                                "param": param_name,
                                "original": param_value,
                                "local_path": local_path,
                                "type": self.media_processor.get_file_type(local_path)
                            })
                        else:
                            processing_info["errors"].append({
                                "param": param_name,
                                "error": error
                            })
                            raise ScriptError(
                                message=f"参数 {param_name} 处理失败: {error}",
                                error_type=ErrorType.VALIDATION
                            )
        
        return processed_params, processing_info
    
    def _process_single_media_param(self, param_value: str, param_name: str, param_type: str) -> Tuple[bool, str, str]:
        """
        处理单个音视频参数
        
        Args:
            param_value: 参数值
            param_name: 参数名称
            param_type: 参数类型
            
        Returns:
            Tuple[成功标志, 本地文件路径, 错误信息]
        """
        if not param_value:
            return False, "", f"参数 {param_name} 不能为空"
        
        # 使用 MediaProcessor 处理媒体输入
        return self.media_processor.process_media_input(param_value, param_name)
    
    def wrap_script_execution(self, script: Dict[str, Any], args_schema: Dict[str, Any], http_params: Dict[str, Any], execute_func):
        """
        包装脚本执行，添加音视频处理逻辑
        
        Args:
            script: 脚本信息
            args_schema: 参数模式
            http_params: HTTP参数
            execute_func: 执行函数
            
        Returns:
            脚本执行结果
        """
        @handle_script_errors
        def wrapped_execution():
            # 处理音视频参数
            processed_params, processing_info = self.process_script_params(
                script, args_schema, http_params
            )
            
            # 执行脚本
            result = execute_func(script, args_schema, processed_params)
            
            # 添加处理信息到结果中
            if result.get("status") == "success" and processing_info["processed_media"]:
                result["media_processing"] = processing_info
            
            return result
        
        return wrapped_execution()


# 创建全局中间件实例
media_middleware = MediaProcessingMiddleware()