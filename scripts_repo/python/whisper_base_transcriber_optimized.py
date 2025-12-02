#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Whisper音频转录脚本 - 简化版本
支持多种参数格式、繁简体转换和多种输出格式
"""

import argparse
import json
import sys
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.core.error_handler import (
    handle_script_errors, 
    ValidationError, 
    ResourceError, 
    validate_parameters,
    create_success_response,
    create_content_response,
    print_json_response
)
from src.utils.logger import get_script_logger

# 获取日志记录器
script_name = os.path.splitext(os.path.basename(__file__))[0]
logger = get_script_logger(script_name)

# =============================================================================
# 参数定义区域
# =============================================================================

# 简化的参数定义映射表
ARGS_MAP: Dict[str, Dict[str, Any]] = {
    # 必需参数
    "audio_file": {
        "flag": "--audio", 
        "type": "file", 
        "required": True, 
        "help": "音频文件路径（支持mp3, wav, m4a等格式）"
    },
    
    # 核心可选参数
    "model": {
        "flag": "--model", 
        "type": "choice", 
        "required": False, 
        "help": "Whisper模型大小", 
        "default": "base",
        "choices": ["tiny", "base", "small", "medium", "large"]
    },
    
    "language": {
        "flag": "--language", 
        "type": "str", 
        "required": False, 
        "help": "指定语言代码（如zh表示中文，auto表示自动检测）", 
        "default": "auto"
    },
    
    "device": {
        "flag": "--device", 
        "type": "choice", 
        "required": False, 
        "help": "计算设备", 
        "default": "cpu",
        "choices": ["cpu", "cuda", "mps"]
    },
    
    # 输出格式参数
    "output_format": {
        "flag": "--output-format", 
        "type": "choice", 
        "required": False, 
        "help": "输出格式", 
        "default": "json",
        "choices": ["json", "text", "srt", "vtt"]
    },
    
    # 转换参数
    "convert_format": {
        "flag": "--convert-format", 
        "type": "choice", 
        "required": False, 
        "help": "繁简体转换格式", 
        "default": "none",
        "choices": ["none", "t2s", "s2t", "t2s_s2t"]
    },
    
    # 高级参数
    "word_timestamps": {
        "flag": "--word-timestamps", 
        "type": "bool", 
        "required": False, 
        "help": "是否包含单词级时间戳", 
        "default": False
    },
    
    "fp16": {
        "flag": "--fp16", 
        "type": "bool", 
        "required": False, 
        "help": "是否使用FP16精度（GPU推荐）", 
        "default": True
    },
    
    "debug": {
        "flag": "--debug", 
        "type": "bool", 
        "required": False, 
        "help": "调试模式", 
        "default": False
    }
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


def validate_custom_parameters(params: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    自定义参数验证函数
    
    Args:
        params: 参数字典
        
    Returns:
        tuple: (是否验证通过, 错误结果字典)
    """
    # 检查音频文件是否存在
    audio_file = params.get('audio_file')
    if audio_file and not os.path.exists(audio_file):
        return False, ValidationError(
            "音频文件不存在",
            parameter="audio_file",
            value=audio_file
        ).to_dict()
    
    # 检查音频文件格式
    if audio_file:
        supported_formats = ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.webm']
        file_ext = Path(audio_file).suffix.lower()
        if file_ext not in supported_formats:
            return False, ValidationError(
                f"不支持的音频格式: {file_ext}。支持的格式: {', '.join(supported_formats)}",
                parameter="audio_file",
                value=audio_file
            ).to_dict()
    
    # 检查模型和设备的兼容性
    device = params.get('device', 'cpu')
    if device == 'cpu' and params.get('fp16', True):
        logger.warning("CPU模式不支持FP16精度，将使用FP32")
    
    return True, None


def parse_key_value_args(argv: List[str]) -> Dict[str, Any]:
    """
    解析键值对形式的参数
    
    Args:
        argv: 命令行参数列表
        
    Returns:
        Dict: 解析后的参数字典
    """
    params = {}
    i = 0
    
    while i < len(argv):
        arg = argv[i]
        
        # 跳过脚本名
        if i == 0:
            i += 1
            continue
            
        # 处理键值对
        if not arg.startswith("-"):
            # 这是一个键
            key = arg
            # 查找对应的参数定义
            param_def = None
            for param_name, param_config in ARGS_MAP.items():
                if param_name == key:
                    param_def = param_config
                    break
            
            if param_def:
                # 获取值
                if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                    # 有值
                    value = argv[i + 1]
                    i += 2
                    
                    # 处理布尔值
                    if param_def.get("type") == "bool":
                        if value.lower() in ['true', '1', 'yes', 'on']:
                            value = True
                        elif value.lower() in ['false', '0', 'no', 'off']:
                            value = False
                        else:
                            # 如果是布尔参数但没有提供值，默认为True
                            value = True
                else:
                    # 没有值，对于布尔参数默认为True
                    if param_def.get("type") == "bool":
                        value = True
                        i += 1
                    else:
                        # 非布尔参数必须有值
                        logger.error(f"参数 {key} 缺少值")
                        i += 1
                        continue
                
                params[key] = value
            else:
                # 未知参数，跳过
                logger.warning(f"未知参数: {key}")
                i += 1
        else:
            # 跳过标准参数
            i += 1
    
    # 应用默认值
    for key, config in ARGS_MAP.items():
        if key not in params and "default" in config:
            params[key] = config["default"]
    
    return params


def process_business_logic(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理音频转录业务逻辑
    
    Args:
        params: 验证后的参数字典
        
    Returns:
        Dict: 转录结果数据
    """
    # 初始化转录器
    transcriber = WhisperTranscriber(params)
    
    # 加载模型
    success, error = transcriber.load_model()
    if not success:
        raise ResourceError(error.get('message', '模型加载失败'))
    
    # 执行转录
    success, result = transcriber.transcribe_audio()
    if not success:
        raise ResourceError(error.get('message', '音频转录失败'))
    
    # 处理结果
    processed_result = transcriber.process_result(result)
    
    # 生成输出内容
    success, content = transcriber.save_result(processed_result)
    if not success:
        raise ResourceError("生成输出内容失败")
    
    return {
        "content": content,
        "metadata": processed_result.get("metadata", {}),
        "transcription": processed_result.get("transcription", {})
    }


# =============================================================================
# 转换器类
# =============================================================================

class TextConverter:
    """简化的文本转换器"""
    
    def __init__(self, format_type: str = "none") -> None:
        """
        初始化文本转换器
        
        Args:
            format_type: 转换格式，支持 none, t2s, s2t, t2s_s2t
        """
        self.format_type = format_type
        self.t2s_converter = None
        self.s2t_converter = None
        self._init_converters()
    
    def _init_converters(self) -> None:
        """初始化转换器"""
        if self.format_type == "none":
            return
        
        try:
            import opencc
        except ImportError:
            logger.warning(f"OpenCC未安装，无法进行{self.format_type}转换")
            return
        
        if "t2s" in self.format_type:
            self.t2s_converter = opencc.OpenCC('t2s')
        if "s2t" in self.format_type:
            self.s2t_converter = opencc.OpenCC('s2t')
    
    def convert(self, text: str) -> str:
        """
        执行文本转换
        
        Args:
            text: 待转换的文本
            
        Returns:
            转换后的文本
        """
        if self.format_type == "none" or not text:
            return text
        
        result = text
        
        try:
            if self.t2s_converter:
                result = self.t2s_converter.convert(result)
            
            if self.s2t_converter:
                result = self.s2t_converter.convert(result)
            
            return result
        except Exception as e:
            logger.error(f"文本转换失败: {str(e)}")
            return text


# =============================================================================
# 转录器类
# =============================================================================

class WhisperTranscriber:
    """简化的Whisper转录器"""
    
    def __init__(self, params: Dict[str, Any]) -> None:
        """
        初始化转录器
        
        Args:
            params: 参数字典
        """
        self.params = params
        self.audio_file = Path(params['audio_file'])
        self.model_name = params['model']
        self.language = params['language']
        self.device = params['device']
        
        # 转录参数
        self.fp16 = params.get('fp16', True)
        self.word_timestamps = params.get('word_timestamps', False)
        
        # 转换器
        convert_format = params.get('convert_format', 'none')
        self.converter = TextConverter(convert_format)
        
        # 初始化模型
        self.model = None
    
    def _check_cuda_available(self) -> bool:
        """检查CUDA是否可用"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False
    
    def load_model(self) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        加载Whisper模型
        
        Returns:
            tuple: (是否成功, 错误信息字典)
        """
        try:
            import whisper
            
            # 确定设备
            device = "cuda" if self._check_cuda_available() and self.device != "cpu" else "cpu"
            
            # 加载模型
            self.model = whisper.load_model(self.model_name, device=device)
            
            return True, None
            
        except ImportError:
            return False, ResourceError(
                "Whisper库未安装，请运行: pip install openai-whisper",
                resource_type="Whisper"
            ).to_dict()
        
        except Exception as e:
            return False, ResourceError(
                f"模型加载失败: {str(e)}",
                resource_type="WhisperModel"
            ).to_dict()
    
    def transcribe_audio(self) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        转录音频
        
        Returns:
            tuple: (是否成功, 转录结果或错误信息字典)
        """
        try:
            # 转录参数
            transcribe_kwargs = {
                "language": None if self.language == "auto" else self.language,
                "word_timestamps": self.word_timestamps,
                "verbose": False
            }
            
            # 只有在非CPU设备上才使用fp16
            if self.device != "cpu" and self.fp16:
                transcribe_kwargs["fp16"] = True
            
            # 执行转录
            result = self.model.transcribe(str(self.audio_file), **transcribe_kwargs)
            
            return True, result
            
        except Exception as e:
            return False, ResourceError(
                f"转录失败: {str(e)}",
                resource_type="AudioTranscription"
            ).to_dict()
    
    def process_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理转录结果
        
        Args:
            result: 原始转录结果
            
        Returns:
            处理后的结果字典
        """
        # 转换文本格式
        original_text = result.get('text', '')
        converted_text = self.converter.convert(original_text)
        
        return {
            "transcription": {
                "original_text": original_text,
                "converted_text": converted_text,
                "language": result.get('language', 'unknown'),
                "duration": result.get('duration', 0)
            },
            "metadata": {
                "model": self.model_name,
                "device": self.device,
                "convert_format": self.converter.format_type,
                "audio_file": str(self.audio_file),
                "audio_size": self.audio_file.stat().st_size,
                "processed_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }
    
    def save_result(self, result: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        生成结果内容
        
        Args:
            result: 处理后的结果
            
        Returns:
            tuple: (是否成功, 结果内容)
        """
        try:
            output_format = self.params.get('output_format', 'json')
            
            # 根据格式生成内容
            if output_format == "json":
                content = json.dumps(result, ensure_ascii=False, indent=2)
            elif output_format == "text":
                content = result['transcription']['converted_text']
            elif output_format in ["srt", "vtt"]:
                content = self._generate_subtitle_content(result, output_format)
            else:
                content = json.dumps(result, ensure_ascii=False, indent=2)
            
            return True, content
            
        except Exception as e:
            logger.error(f"生成结果失败: {str(e)}")
            return False, None
    
    def _generate_subtitle_content(self, result: Dict[str, Any], format_type: str) -> str:
        """
        生成字幕内容
        
        Args:
            result: 处理后的结果
            format_type: 字幕格式 (srt 或 vtt)
            
        Returns:
            str: 字幕内容
        """
        content = []
        
        if format_type == "srt":
            content.append(f"// 转录结果: {self.audio_file.name}")
            content.append(f"// 模型: {self.model_name}")
            content.append(f"// 语言: {result['transcription']['language']}")
            content.append("")
            
            lines = result['transcription']['converted_text'].split('\n')
            for i, line in enumerate(lines, 1):
                content.append(f"{i}")
                content.append(f"00:00:00,000 --> 00:00:05,000")
                content.append(f"{line}")
                content.append("")
                
        elif format_type == "vtt":
            content.append("WEBVTT")
            content.append("")
            content.append(f"// 转录结果: {self.audio_file.name}")
            content.append(f"// 模型: {self.model_name}")
            content.append(f"// 语言: {result['transcription']['language']}")
            content.append("")
            
            lines = result['transcription']['converted_text'].split('\n')
            for i, line in enumerate(lines, 1):
                content.append(f"CUE {i}")
                content.append(f"00:00:00.000 --> 00:00:05.000")
                content.append(f"{line}")
                content.append("")
        
        return "\n".join(content)


# =============================================================================
# 主要处理函数
# =============================================================================

@handle_script_errors
def process_request(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理请求的主函数
    
    Args:
        params: 参数字典
        
    Returns:
        Dict: 处理结果
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
    result_data = process_business_logic(params)
    
    # 4. 返回内容响应
    return create_content_response(
        content=result_data["content"],
        metadata={
            "message": "转录完成",
            "transcription": result_data["transcription"],
            "metadata": result_data["metadata"]
        }
    )


# =============================================================================
# 入口函数
# =============================================================================

def main():
    """主函数 - 处理命令行参数并调用处理函数"""
    # 处理特殊参数 --_sys_get_schema
    if len(sys.argv) > 1 and sys.argv[1] == "--_sys_get_schema":
        print(get_schema())
        sys.exit(0)
    
    # 检查参数格式
    use_key_value_parser = False
    if len(sys.argv) > 2:
        # 检查是否是键值对格式
        i = 1
        while i < len(sys.argv):
            arg = sys.argv[i]
            if not arg.startswith("-") and i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("-"):
                # 这看起来像键值对格式
                use_key_value_parser = True
                break
            i += 1
    
    if use_key_value_parser:
        # 使用键值对解析器
        params = parse_key_value_args(sys.argv)
    else:
        # 使用标准argparse解析器
        parser = argparse.ArgumentParser(description='Whisper音频转录脚本')
        
        # 添加所有参数
        for key, cfg in ARGS_MAP.items():
            param_type = cfg.get("type", "str")
            required = cfg.get("required", False)
            default = cfg.get("default")
            help_text = cfg.get("help", "")
            
            if param_type == "bool":
                parser.add_argument(
                    cfg["flag"], 
                    help=help_text,
                    type=lambda x: x.lower() in ['true', '1', 'yes', 'on'] if x.lower() not in ['false', '0', 'no', 'off'] else False,
                    default=default,
                    nargs='?' if default else None
                )
            elif param_type == "choice" and "choices" in cfg:
                parser.add_argument(
                    cfg["flag"], 
                    help=help_text,
                    choices=cfg["choices"],
                    default=default
                )
            else:
                parser.add_argument(
                    cfg["flag"], 
                    help=help_text,
                    required=required,
                    default=default
                )
        
        # 解析命令行参数
        args = parser.parse_args()
        
        # 构建参数字典
        params = {}
        for key in ARGS_MAP.keys():
            # 从flag中提取参数名
            flag = ARGS_MAP[key]["flag"]
            arg_name = flag.lstrip('-').replace('-', '_')
            value = getattr(args, arg_name, None)
            if value is not None:
                params[key] = value
    
    # 处理请求并打印结果
    result = process_request(params)
    print_json_response(result)


if __name__ == "__main__":
    main()