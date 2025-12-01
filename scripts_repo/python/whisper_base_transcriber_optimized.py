#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Whisper Base模型音频转录脚本 - 优化版本
支持繁简体转换、多种输出格式、参数验证和错误处理
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
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union, Tuple, List, Type
import traceback
import gc

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

# 参数定义映射表
ARGS_MAP: Dict[str, Dict[str, Any]] = {
    # 必需参数
    "audio_file": {
        "flag": "--audio-file", 
        "type": "file", 
        "required": True, 
        "help": "音频文件路径（支持mp3, wav, m4a等格式）"
    },
    
    # 可选参数
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
    
    "convert_format": {
        "flag": "--convert-format", 
        "type": "choice", 
        "required": False, 
        "help": "繁简体转换格式", 
        "default": "none",
        "choices": ["none", "t2s", "s2t", "t2s_s2t"]
    },
    
    "output_format": {
        "flag": "--output-format", 
        "type": "choice", 
        "required": False, 
        "help": "输出格式", 
        "default": "json",
        "choices": ["json", "text", "srt", "vtt"]
    },
    
    
    
    "output_file": {
        "flag": "--output-file", 
        "type": "str", 
        "required": False, 
        "help": "输出文件名（不包含扩展名）", 
        "default": ""
    },
    
    "save_segments": {
        "flag": "--save-segments", 
        "type": "bool", 
        "required": False, 
        "help": "是否保存分段信息", 
        "default": False
    },
    
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
    
    "verbose": {
        "flag": "--verbose", 
        "type": "bool", 
        "required": False, 
        "help": "详细输出模式", 
        "default": False
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
    在标准验证之后执行，用于业务逻辑相关的验证
    
    Args:
        params: 参数字典
        
    Returns:
        tuple: (是否验证通过, 错误结果字典)
    """
    # 检查模型和设备的兼容性
    model = params.get('model')
    device = params.get('device')
    
    if model in ['large', 'medium'] and device == 'cpu' and params.get('fp16', True):
        return False, ValidationError(
            "CPU模式不支持FP16精度，请使用--fp16 False",
            parameter="fp16",
            value=params.get('fp16')
        ).to_dict()
    
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
    
    
    
    # 所有验证通过
    return True, None


# =============================================================================
# 转换器类
# =============================================================================

class TextConverter:
    """文本转换器 - 处理繁简体转换"""
    
    def __init__(self, format_type: str = "none") -> None:
        """
        初始化文本转换器
        
        Args:
            format_type: 转换格式，支持 none, t2s, s2t, t2s_s2t
        """
        self.format_type: str = format_type
        self.t2s_converter: Optional[Any] = None
        self.s2t_converter: Optional[Any] = None
        self._init_converters()
    
    def _init_converters(self) -> None:
        """初始化转换器"""
        if self.format_type == "none":
            logger.debug("文本转换器设置为none，不进行转换")
            return
        
        logger.debug(f"初始化文本转换器，格式: {self.format_type}")
        try:
            import opencc
            logger.debug("OpenCC库导入成功")
        except ImportError:
            logger.error(f"OpenCC未安装，无法进行{self.format_type}转换")
            raise ResourceError(
                f"OpenCC未安装，无法进行{self.format_type}转换。请运行: pip install opencc-python-reimplemented",
                resource_type="OpenCC"
            )
        
        if "t2s" in self.format_type:
            self.t2s_converter = opencc.OpenCC('t2s')
            logger.debug("繁体到简体转换器初始化成功")
        if "s2t" in self.format_type:
            self.s2t_converter = opencc.OpenCC('s2t')
            logger.debug("简体到繁体转换器初始化成功")
    
    def convert(self, text: str) -> str:
        """
        执行文本转换
        
        Args:
            text: 待转换的文本
            
        Returns:
            转换后的文本
        """
        if self.format_type == "none":
            return text
        
        logger.debug(f"开始文本转换，格式: {self.format_type}")
        result = text
        
        try:
            if self.t2s_converter:
                result = self.t2s_converter.convert(result)
                logger.debug("完成繁体到简体转换")
            
            if self.s2t_converter:
                result = self.s2t_converter.convert(result)
                logger.debug("完成简体到繁体转换")
            
            logger.debug("文本转换完成")
            return result
        except Exception as e:
            logger.error(f"文本转换失败: {str(e)}")
            return text  # 转换失败时返回原始文本


# =============================================================================
# 主要处理类
# =============================================================================

class WhisperTranscriber:
    """Whisper转录器"""
    
    def __init__(self, params: Dict[str, Any]) -> None:
        """
        初始化转录器
        
        Args:
            params: 参数字典
        """
        self.params: Dict[str, Any] = params
        self.audio_file: Path = Path(params['audio_file'])
        self.model_name: str = params['model']
        self.language: str = params['language']
        self.device: str = params['device']
        
        self.verbose: bool = params.get('verbose', False)
        self.debug: bool = params.get('debug', False)
        
        # 转录参数
        self.fp16: bool = params.get('fp16', True)
        self.save_segments: bool = params.get('save_segments', False)
        self.word_timestamps: bool = params.get('word_timestamps', False)
        
        # 转换器
        convert_format = params.get('convert_format', 'none')
        self.converter = TextConverter(convert_format)
        
        # 初始化模型
        self.model: Optional[Any] = None
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """设置日志 - 使用项目统一的日志系统"""
        # 使用项目统一的日志系统，不再单独设置
        pass
    
    def _check_cuda_available(self) -> bool:
        """检查CUDA是否可用"""
        try:
            import torch
            cuda_available = torch.cuda.is_available()
            logger.debug(f"CUDA可用性检查: {cuda_available}")
            if cuda_available:
                logger.debug(f"CUDA设备数量: {torch.cuda.device_count()}")
            return cuda_available
        except ImportError:
            logger.debug("PyTorch未安装，无法使用CUDA")
            return False
    
    def load_model(self) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        加载Whisper模型
        
        Returns:
            tuple: (是否成功, 错误信息字典)
        """
        try:
            import whisper
            
            logger.info(f"正在加载Whisper模型: {self.model_name}")
            start_time = time.time()
            
            # 确定设备
            device = "cuda" if self._check_cuda_available() and self.device != "cpu" else "cpu"
            logger.debug(f"使用设备: {device}")
            
            # 加载模型
            self.model = whisper.load_model(self.model_name, device=device)
            
            load_time = time.time() - start_time
            logger.info(f"模型加载完成，耗时: {load_time:.2f}秒")
            
            return True, None
            
        except ImportError:
            return False, ResourceError(
                "Whisper库未安装，请运行: pip install openai-whisper",
                resource_type="Whisper"
            ).to_dict()
        
        except Exception as e:
            logger.error(f"模型加载失败: {str(e)}")
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
            logger.info(f"开始转录音频: {self.audio_file.name}")
            logger.info(f"转录参数: 语言={self.language}, 设备={self.device}, FP16={self.fp16}")
            
            start_time = time.time()
            
            # 转录参数 - 修复fp16参数问题
            transcribe_kwargs: Dict[str, Any] = {
                "language": None if self.language == "auto" else self.language,
                "word_timestamps": self.word_timestamps,
                "verbose": self.verbose
            }
            
            # 只有在非CPU设备上才使用fp16
            if self.device != "cpu" and self.fp16:
                transcribe_kwargs["fp16"] = True
            
            logger.debug(f"转录参数详情: {transcribe_kwargs}")
            
            # 执行转录
            result = self.model.transcribe(str(self.audio_file), **transcribe_kwargs)
            
            transcribe_time = time.time() - start_time
            logger.info(f"转录完成，耗时: {transcribe_time:.2f}秒")
            logger.debug(f"检测到的语言: {result.get('language', '未知')}")
            
            return True, result
            
        except Exception as e:
            logger.error(f"转录失败: {str(e)}")
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
        logger.debug("开始处理转录结果")
        
        # 转换文本格式
        original_text = result.get('text', '')
        logger.debug(f"原始文本长度: {len(original_text)} 字符")
        
        converted_text = self.converter.convert(original_text)
        logger.debug(f"转换后文本长度: {len(converted_text)} 字符，转换格式: {self.converter.format_type}")
        
        processed_result = {
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
        
        # 添加分段信息
        if self.save_segments and 'segments' in result:
            processed_result["segments"] = result['segments']
            logger.debug(f"已保存分段信息，共 {len(result['segments'])} 个分段")
        
        logger.debug("转录结果处理完成")
        return processed_result
    
    def save_result(self, result: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        生成结果内容（不保存到文件，由系统统一管理）
        
        Args:
            result: 处理后的结果
            
        Returns:
            tuple: (是否成功, 结果内容)
        """
        try:
            output_format = self.params.get('output_format', 'json')
            logger.debug(f"准备生成结果，格式: {output_format}")
            
            # 根据格式生成内容
            if output_format == "json":
                content = json.dumps(result, ensure_ascii=False, indent=2)
                logger.debug("生成JSON格式结果")
            
            elif output_format == "text":
                content = result['transcription']['converted_text']
                logger.debug("生成文本格式结果")
            
            elif output_format in ["srt", "vtt"]:
                # 生成字幕内容到内存中的字符串
                content = self._generate_subtitle_content(result, output_format)
                logger.debug(f"生成字幕格式结果: {output_format}")
            
            else:
                content = json.dumps(result, ensure_ascii=False, indent=2)
                logger.debug("默认生成JSON格式结果")
            
            logger.info("结果内容生成完成")
            return True, content
            
        except Exception as e:
            logger.error(f"生成结果失败: {str(e)}")
            return False, None
    
    def _save_subtitle_file(self, result: Dict[str, Any], output_file: Path, format_type: str) -> None:
        """
        保存字幕文件
        
        Args:
            result: 处理后的结果
            output_file: 输出文件路径
            format_type: 字幕格式 (srt 或 vtt)
        """
        logger.debug(f"保存字幕文件，格式: {format_type}")
        try:
            if format_type == "srt":
                self._save_srt_file(result, output_file)
            elif format_type == "vtt":
                self._save_vtt_file(result, output_file)
            else:
                logger.warning(f"不支持的字幕格式: {format_type}")
        except Exception as e:
            logger.error(f"保存字幕文件失败: {str(e)}")
            raise
    
    def _generate_subtitle_content(self, result: Dict[str, Any], format_type: str) -> str:
        """
        生成字幕内容到字符串
        
        Args:
            result: 处理后的结果
            format_type: 字幕格式 (srt 或 vtt)
            
        Returns:
            str: 字幕内容
        """
        logger.debug(f"开始生成字幕内容，格式: {format_type}")
        try:
            content = []
            
            if format_type == "srt":
                content.append(f"// 转录结果: {self.audio_file.name}")
                content.append(f"// 模型: {self.model_name}")
                content.append(f"// 语言: {result['transcription']['language']}")
                content.append(f"// 转换格式: {self.converter.format_type}")
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
                content.append(f"// 转换格式: {self.converter.format_type}")
                content.append("")
                
                lines = result['transcription']['converted_text'].split('\n')
                for i, line in enumerate(lines, 1):
                    content.append(f"CUE {i}")
                    content.append(f"00:00:00.000 --> 00:00:05.000")
                    content.append(f"{line}")
                    content.append("")
            
            else:
                logger.warning(f"不支持的字幕格式: {format_type}")
                return ""
            
            logger.debug(f"{format_type.upper()}字幕内容生成成功")
            return "\n".join(content)
            
        except Exception as e:
            logger.error(f"生成字幕内容失败: {str(e)}")
            raise
    
    def _save_srt_file(self, result: Dict[str, Any], output_file: Path) -> None:
        """
        保存SRT字幕文件
        
        Args:
            result: 处理后的结果
            output_file: 输出文件路径
        """
        logger.debug(f"开始保存SRT字幕文件: {output_file}")
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"// 转录结果: {self.audio_file.name}\n")
                f.write(f"// 模型: {self.model_name}\n")
                f.write(f"// 语言: {result['transcription']['language']}\n")
                f.write(f"// 转换格式: {self.converter.format_type}\n\n")
                
                lines = result['transcription']['converted_text'].split('\n')
                for i, line in enumerate(lines, 1):
                    f.write(f"{i}\n")
                    f.write(f"00:00:00,000 --> 00:00:05,000\n")
                    f.write(f"{line}\n\n")
            logger.debug(f"SRT字幕文件保存成功: {output_file}")
        except Exception as e:
            logger.error(f"保存SRT字幕文件失败: {str(e)}")
            raise
    
    def _save_vtt_file(self, result: Dict[str, Any], output_file: Path) -> None:
        """
        保存VTT字幕文件
        
        Args:
            result: 处理后的结果
            output_file: 输出文件路径
        """
        logger.debug(f"开始保存VTT字幕文件: {output_file}")
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("WEBVTT\n\n")
                f.write(f"NOTE 转录结果: {self.audio_file.name}\n")
                f.write(f"NOTE 模型: {self.model_name}\n")
                f.write(f"NOTE 语言: {result['transcription']['language']}\n")
                f.write(f"NOTE 转换格式: {self.converter.format_type}\n\n")
                
                lines = result['transcription']['converted_text'].split('\n')
                for i, line in enumerate(lines):
                    f.write(f"CUE {i}\n")
                    f.write(f"00:00:00.000 --> 00:00:05.000\n")
                    f.write(f"{line}\n\n")
            logger.debug(f"VTT字幕文件保存成功: {output_file}")
        except Exception as e:
            logger.error(f"保存VTT字幕文件失败: {str(e)}")
            raise
    
    def transcribe(self) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        执行完整的转录流程
        
        Returns:
            tuple: (是否成功, 结果或错误信息字典)
        """
        logger.info("开始执行完整转录流程")
        try:
            # 1. 加载模型
            logger.debug("步骤1: 加载Whisper模型")
            is_valid, error_result = self.load_model()
            if not is_valid:
                logger.error(f"模型加载失败: {error_result.get('message', '未知错误')}")
                return False, error_result
            
            # 2. 转录音频
            logger.debug("步骤2: 执行音频转录")
            is_valid, result = self.transcribe_audio()
            if not is_valid:
                logger.error(f"音频转录失败: {result.get('message', '未知错误')}")
                return False, result
            
            # 3. 处理结果
            logger.debug("步骤3: 处理转录结果")
            processed_result = self.process_result(result)
            
            # 4. 生成结果内容
            logger.debug("步骤4: 生成转录结果内容")
            success, content = self.save_result(processed_result)
            
            # 5. 返回结果
            logger.info("转录流程执行完成")
            return success, {
                "success": success,
                "content": content,
                "result": processed_result
            }
            
        except Exception as e:
            logger.error(f"转录流程执行失败: {str(e)}")
            return False, ScriptError(
                f"转录流程执行失败: {str(e)}",
                error_type="TranscriptionFlow"
            ).to_dict()
        
        finally:
            # 清理资源
            if self.model:
                del self.model
                gc.collect()


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
    # 记录脚本开始执行
    logger.info(f"开始执行音频转录，参数: {json.dumps({k: v for k, v in params.items() if k != 'audio_file'}, ensure_ascii=False)}")
    
    # 1. 标准参数验证
    is_valid, error_result = validate_parameters(params, ARGS_MAP)
    if not is_valid:
        logger.error(f"参数验证失败: {error_result.get('message', '未知错误')}")
        return error_result
    
    # 2. 自定义参数验证
    is_valid, error_result = validate_custom_parameters(params)
    if not is_valid:
        logger.error(f"自定义参数验证失败: {error_result.get('message', '未知错误')}")
        return error_result
    
    # 3. 创建转录器并执行转录
    try:
        logger.info("开始音频转录流程")
        transcriber = WhisperTranscriber(params)
        success, result = transcriber.transcribe()
        
        if success:
            if result.get('content'):
                # 如果生成了内容，返回内容响应
                logger.info("转录完成，结果已生成")
                return create_content_response(
                    content=result['content'],
                    metadata={"message": "转录完成", "data": result['result']}
                )
            else:
                # 否则返回标准成功响应
                logger.info("转录完成")
                return create_success_response(
                    data=result['result'],
                    message="转录完成"
                )
        else:
            # 返回错误响应
            logger.error(f"转录失败: {result.get('message', '未知错误')}")
            return result
    
    except Exception as e:
        error_msg = f"转录处理失败: {str(e)}"
        logger.error(error_msg)
        
        if params.get('debug', False):
            logger.exception("转录处理异常详情")
        
        return ResourceError(
            message=error_msg,
            resource_type="transcription"
        ).to_dict()


# =============================================================================
# 入口函数
# =============================================================================

def main() -> None:
    """主函数 - 处理命令行参数并调用处理函数"""
    # 1. 创建参数解析器
    parser = argparse.ArgumentParser(
        description='Whisper Base模型音频转录脚本 - 支持繁简体转换和多种输出格式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 基本转录
  python whisper_base_transcriber_optimized.py --audio-file audio.mp3

  # 繁简体转换
  python whisper_base_transcriber_optimized.py --audio-file audio.mp3 --convert-format t2s

  # 保存为SRT字幕
  python whisper_base_transcriber_optimized.py --audio-file audio.mp3 --output-format srt

  # 详细输出
  python whisper_base_transcriber_optimized.py --audio-file audio.mp3 --verbose

  # 自定义输出文件和目录
  python whisper_base_transcriber_optimized.py --audio-file audio.mp3 --output-file my_transcript --output-dir ./results

  # 获取参数定义
  python whisper_base_transcriber_optimized.py --_sys_get_schema
        """
    )
    
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
    params: Dict[str, Any] = {}
    for key in ARGS_MAP.keys():
        value = getattr(args, key, None)
        if value is not None:
            params[key] = value
    
    # 6. 处理请求并打印结果
    result = process_request(params)
    print_json_response(result)


if __name__ == "__main__":
    main()