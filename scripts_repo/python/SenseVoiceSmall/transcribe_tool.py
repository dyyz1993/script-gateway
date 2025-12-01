#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import argparse
import json
import sys
import os
from pathlib import Path
import logging
import io

# 禁用funasr的日志输出
logging.getLogger("funasr").setLevel(logging.ERROR)
os.environ["FUNASR_CACHE_HOME"] = "/tmp/funasr_cache"

# 重定向标准输出，避免库的输出干扰JSON结果
class OutputCapture:
    def __init__(self):
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.captured_output = []
        
    def start_capture(self):
        sys.stdout = self
        sys.stderr = self
        
    def stop_capture(self):
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        return ''.join(self.captured_output)
        
    def write(self, text):
        self.captured_output.append(text)
        
    def flush(self):
        pass

# 创建全局输出捕获器
output_capture = OutputCapture()

# 添加项目根目录到Python路径，以便导入error_handler模块
# 从 /scripts_repo/python/SenseVoiceSmall/transcribe_tool.py 到项目根目录需要向上4级
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
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
from src.utils.logger import get_script_logger

# 初始化日志器
script_name = os.path.splitext(os.path.basename(__file__))[0]
logger = get_script_logger(script_name)

# 尝试导入SenseVoice相关依赖
try:
    from funasr import AutoModel
    from funasr.utils.postprocess_utils import rich_transcription_postprocess
    
    # 使用绝对路径导入model模块，解决打包后的导入问题
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    import sys
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    from model import SenseVoiceSmall
    FUNASR_AVAILABLE = True
except ImportError as e:
    FUNASR_AVAILABLE = False
    IMPORT_ERROR = f"缺少SenseVoice相关依赖: {str(e)}"

# 这是可编辑的 Python 模板示例
# 约定：提供 ARGS_MAP 并支持 --_sys_get_schema 输出参数定义

ARGS_MAP = {
    "audio": {
        "flag": "--audio", 
        "type": "file", 
        "required": True, 
        "help": "音频文件路径 (支持 .mp3, .wav, .m4a, .flac 等格式)"
    },
    "language": {
        "flag": "--language", 
        "type": "str", 
        "required": False, 
        "default": "auto",
        "help": "指定语言 (auto, zh, en, yue, ja, ko)，默认自动检测"
    },
    "use_itn": {
        "flag": "--use-itn", 
        "type": "bool", 
        "required": False, 
        "default": True,
        "help": "启用ITN（反文本标准化），包含标点和数字格式化"
    },
    "output_timestamp": {
        "flag": "--output-timestamp", 
        "type": "bool", 
        "required": False, 
        "default": False,
        "help": "输出词级别时间戳"
    },
    "output_file": {
        "flag": "--output-file", 
        "type": "str", 
        "required": False, 
        "help": "输出结果到文件路径"
    },
    "device": {
        "flag": "--device", 
        "type": "str", 
        "required": False, 
        "default": "cpu",
        "help": "计算设备 (cpu, cuda:0, cuda:1)"
    }
}


def get_schema():
    """返回参数定义的JSON格式"""
    return json.dumps(ARGS_MAP, ensure_ascii=False)


def validate_audio_file(audio_path):
    """验证音频文件是否存在且格式支持"""
    logger.debug(f"验证音频文件: {os.path.basename(audio_path)}")
    
    if not os.path.exists(audio_path):
        logger.error(f"音频文件不存在: {audio_path}")
        return False, ResourceError(
            message=f"音频文件不存在: {audio_path}",
            resource_type="file",
            resource_path=audio_path
        ).to_dict()
    
    supported_formats = ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac']
    file_ext = Path(audio_path).suffix.lower()
    
    if file_ext not in supported_formats:
        logger.error(f"不支持的音频格式: {file_ext}")
        return False, ValidationError(
            message=f"不支持的音频格式: {file_ext}，支持的格式: {', '.join(supported_formats)}",
            parameter="audio",
            value=audio_path
        ).to_dict()
    
    logger.debug(f"音频文件验证通过: {file_ext}")
    return True, None


@handle_script_errors
def transcribe_audio(audio_path, language="auto", use_itn=True, output_timestamp=False, device="cpu"):
    """使用SenseVoice进行音频转录"""
    
    logger.info(f"开始SenseVoice音频转录: {os.path.basename(audio_path)}")
    logger.info(f"转录参数: 语言={language}, ITN={use_itn}, 时间戳={output_timestamp}, 设备={device}")
    
    # 检查依赖是否可用
    if not FUNASR_AVAILABLE:
        logger.error(f"缺少必要依赖: {IMPORT_ERROR}")
        return ScriptError(
            message=f"缺少必要依赖: {IMPORT_ERROR}",
            error_type=ErrorType.RESOURCE,
            code=500
        ).to_dict()
    
    # 验证设备参数
    valid_devices = ["cpu", "cuda:0", "cuda:1"]
    if device not in valid_devices:
        return ValidationError(
            message=f"不支持的设备类型: {device}，支持的设备: {', '.join(valid_devices)}",
            parameter="device",
            value=device
        ).to_dict()
    
    # 验证语言参数
    valid_languages = ["auto", "zh", "en", "yue", "ja", "ko"]
    if language not in valid_languages:
        return ValidationError(
            message=f"不支持的语言: {language}，支持的语言: {', '.join(valid_languages)}",
            parameter="language",
            value=language
        ).to_dict()
    
    try:
        # 初始化模型
        model_dir = "iic/SenseVoiceSmall"
        logger.info(f"开始初始化SenseVoice模型: {model_dir}")
        
        # 尝试不同的初始化方式
        try:
            model = AutoModel(
                model=model_dir,
                trust_remote_code=True,
                remote_code="./model.py",
                vad_model="fsmn-vad",
                vad_kwargs={"max_single_segment_time": 30000},
                device=device,
            )
            logger.debug("模型初始化成功（方式1：使用remote_code）")
        except Exception as e:
            logger.debug(f"模型初始化方式1失败，尝试方式2: {str(e)}")
            try:
                model = AutoModel(
                    model=model_dir,
                    vad_model="fsmn-vad",
                    vad_kwargs={"max_single_segment_time": 30000},
                    device=device,
                )
                logger.debug("模型初始化成功（方式2：不使用remote_code）")
            except Exception as e2:
                logger.error(f"模型初始化失败: {str(e2)}")
                return ScriptError(
                    message=f"模型初始化失败: {str(e2)}",
                    error_type=ErrorType.RESOURCE,
                    code=500
                ).to_dict()
        
        # 尝试两种推理方法
        text = ""
        
        # 方法1: 使用AutoModel的generate方法
        try:
            res = model.generate(
                input=audio_path,
                cache={},
                language=language,
                use_itn=use_itn,
                batch_size_s=60,
                merge_vad=True,
                merge_length_s=15,
            )
            
            if res and len(res) > 0 and "text" in res[0] and res[0]["text"]:
                # 方法1成功
                raw_text = res[0]["text"]
                text = rich_transcription_postprocess(raw_text)
            else:
                raise Exception("方法1返回空结果")
                
        except Exception as e:
            # 方法2: 使用SenseVoiceSmall的直接推理
            try:
                # 使用绝对路径导入model模块，解决打包后的导入问题
                current_dir = os.path.dirname(os.path.abspath(__file__))
                if current_dir not in sys.path:
                    sys.path.insert(0, current_dir)
                
                from model import SenseVoiceSmall
                
                m, kwargs = SenseVoiceSmall.from_pretrained(model=model_dir, device=device)
                m.eval()
                
                inference_res = m.inference(
                    data_in=audio_path,
                    language=language,
                    use_itn=use_itn,
                    ban_emo_unk=False,
                    **kwargs,
                )
                
                if not inference_res or not inference_res[0] or not inference_res[0][0] or "text" not in inference_res[0][0]:
                    raise Exception("方法2也返回空结果")
                
                # 方法2成功
                raw_text = inference_res[0][0]["text"]
                
                # 处理特殊标记
                # 移除语言标记如<|zh|>, <|en|>等
                import re
                # 移除所有特殊标记，保留实际文本内容
                cleaned_text = re.sub(r'<\|[^|]+\|>', '', raw_text)
                # 移除多余的空白字符
                cleaned_text = re.sub(r'\s+', '', cleaned_text)
                # 如果处理后为空，使用原始的rich_transcription_postprocess
                if cleaned_text:
                    text = cleaned_text
                else:
                    text = rich_transcription_postprocess(raw_text)
                
            except Exception as e2:
                return ScriptError(
                    message=f"两种推理方法都失败: 方法1-{str(e)}, 方法2-{str(e2)}",
                    error_type=ErrorType.EXECUTION,
                    code=400
                ).to_dict()
        
        # 添加元数据
        metadata = {}
        if "language" in res[0]:
            metadata["detected_language"] = res[0]["language"]
        
        if "emo_result" in res[0]:
            metadata["emotion_analysis"] = res[0]["emo_result"]
            
        if "event_result" in res[0]:
            metadata["event_detection"] = res[0]["event_result"]
        
        # 文件信息
        metadata["file_size_mb"] = round(os.path.getsize(audio_path) / 1024 / 1024, 2)
        metadata["file_path"] = audio_path
        metadata["model"] = model_dir
        metadata["device"] = device
        
        # 时间戳信息
        timestamps = None
        if output_timestamp:
            try:
                # 使用直接模型推理获取时间戳
                m, kwargs = SenseVoiceSmall.from_pretrained(model=model_dir, device=device)
                m.eval()
                
                timestamp_res = m.inference(
                    data_in=audio_path,
                    language=language,
                    use_itn=use_itn,
                    ban_emo_unk=False,
                    output_timestamp=True,
                    **kwargs,
                )
                
                if timestamp_res and len(timestamp_res) > 0 and len(timestamp_res[0]) > 0:
                    timestamps = timestamp_res[0][0].get("timestamp", [])
                    
            except Exception as e:
                # 时间戳提取失败不影响主流程
                print(f"警告: 时间戳提取失败: {e}")
        
        # 构建结果数据
        result_data = {
            "text": text
        }
        
        if timestamps:
            result_data["timestamps"] = timestamps
        
        # 创建成功响应
        # 如果有文本内容，直接返回文本结果而不是JSON格式
        if text and text.strip():
            # 过滤掉只有标点符号的情况
            filtered_text = text.strip()
            # 如果文本只包含标点符号，认为没有有效转录内容
            if all(c in '，。！？；：""''（）【】《》' for c in filtered_text):
                return {
                    "success": True,
                    "text": "未检测到有效的语音内容，可能是音乐或噪音",
                    "metadata": metadata
                }
            else:
                return {
                    "success": True,
                    "text": filtered_text,
                    "metadata": metadata
                }
        else:
            return {
                "success": True,
                "text": "转录结果为空，请检查音频文件是否包含清晰的语音内容",
                "metadata": metadata
            }
        
    except Exception as e:
        return ScriptError(
            message=f"转录过程中出错: {str(e)}",
            error_type=ErrorType.EXECUTION,
            details={
                "audio_path": audio_path,
                "language": language,
                "device": device
            }
        ).to_dict()


@handle_script_errors
def process_transcription_request(params):
    """处理转录请求"""
    logger.info("开始处理转录请求")
    
    # 验证参数
    is_valid, error_result = validate_parameters(params, ARGS_MAP)
    if not is_valid:
        logger.error(f"参数验证失败: {error_result.get('error', '未知错误')}")
        return error_result
    
    # 获取参数
    audio_path = params.get('audio')
    language = params.get('language', 'auto')
    use_itn = params.get('use_itn', True)
    output_timestamp = params.get('output_timestamp', False)
    output_file = params.get('output_file', None)
    device = params.get('device', 'cpu')
    
    # 记录请求参数（不包含敏感的音频文件路径）
    logger.debug(f"转录参数 - 语言: {language}, 使用ITN: {use_itn}, 输出时间戳: {output_timestamp}, 设备: {device}")
    
    # 验证音频文件
    is_valid, error_result = validate_audio_file(audio_path)
    if not is_valid:
        logger.error(f"音频文件验证失败: {error_result.get('error', '未知错误')}")
        return error_result
    
    logger.info("开始执行音频转录")
    # 执行转录
    result = transcribe_audio(audio_path, language, use_itn, output_timestamp, device)
    
    # 只有明确指定输出文件路径时才生成文件
    if result.get("success") and output_file:
        logger.info(f"将转录结果写入文件: {os.path.basename(output_file)}")
        try:
            # 确保输出目录存在
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                logger.debug(f"创建输出目录: {output_dir}")
            
            # 写入文件
            with open(output_file, 'w', encoding='utf-8') as f:
                # 如果有文本内容，只写入文本
                if "text" in result and result["text"]:
                    f.write(result["text"])
                else:
                    # 兼容旧格式
                    text = result.get("data", {}).get("text", "")
                    f.write(text)
            
            # 添加文件信息到结果
            if "metadata" not in result:
                result["metadata"] = {}
            result["metadata"]["output_file"] = output_file
            result["metadata"]["output_file_size"] = os.path.getsize(output_file)
            
            logger.debug(f"结果文件写入成功，大小: {result['metadata']['output_file_size']} 字节")
            
        except Exception as e:
            # 文件写入失败不影响主流程
            logger.warning(f"结果文件写入失败: {e}")
    
    # 记录转录完成状态
    if result.get("success"):
        text_length = len(result.get("text", ""))
        logger.info(f"转录完成，文本长度: {text_length} 字符")
    else:
        logger.error(f"转录失败: {result.get('error', '未知错误')}")
    
    return result


def main():
    """主函数"""
    # logger.info("SenseVoice转录工具启动")
    
    parser = argparse.ArgumentParser(description="SenseVoice音频转录工具")
    
    for key, cfg in ARGS_MAP.items():
        arg_kwargs = {
            "required": cfg.get("required", False),
            "help": cfg.get("help", "")
        }
        
        # 处理布尔类型参数
        if cfg["type"] == "bool":
            # 使用简单的字符串参数，而不是布尔标志
            # 这样可以兼容executor.py中的参数处理方式
            flag = cfg["flag"]
            arg_kwargs["type"] = lambda x: x.lower() in ['true', '1', 'yes']
            arg_kwargs["dest"] = key.lstrip("-")  # 确保属性名正确
            arg_kwargs["default"] = cfg.get("default", False)
            
            parser.add_argument(flag, **arg_kwargs)
        else:
            parser.add_argument(cfg["flag"], **arg_kwargs)

    if len(sys.argv) > 1 and sys.argv[1] == "--_sys_get_schema":
        logger.debug("获取脚本模式定义")
        print(get_schema())
        sys.exit(0)

    args = parser.parse_args()
    
    # 构建参数字典
    params = {}
    for key in ARGS_MAP.keys():
        value = getattr(args, key, None)
        if value is not None:
            params[key] = value
    
    logger.debug(f"解析到参数: {len(params)} 个")
    
    # 开始捕获输出，避免库的输出干扰JSON结果
    output_capture.start_capture()
    
    try:
        # 处理请求
        result = process_transcription_request(params)
        
        # 停止捕获输出
        captured_output = output_capture.stop_capture()
        
        # 输出结果
        if result.get("success"):
            logger.info("转录请求处理成功")
            # 如果有文本内容，直接输出文本
            if "text" in result and result["text"]:
                # 输出JSON格式，这样executor.py会将其作为JSON处理而不是二进制文件
                json_output = {
                    "text": result["text"],
                    "metadata": result.get("metadata", {})
                }
                print(json.dumps(json_output, ensure_ascii=False))
            else:
                # 兼容旧格式
                text = result.get("data", {}).get("text", "")
                if text:
                    json_output = {
                        "text": text,
                        "metadata": result.get("metadata", {})
                    }
                    print(json.dumps(json_output, ensure_ascii=False))
                else:
                    logger.debug("转录结果为空")
                    json_output = {
                        "text": "转录结果为空",
                        "metadata": result.get("metadata", {})
                    }
                    print(json.dumps(json_output, ensure_ascii=False))
        else:
            logger.error(f"转录请求处理失败: {result.get('error', '未知错误')}")
            # 输出错误信息为JSON格式
            json_output = {
                "error": result.get('error', '未知错误'),
                "metadata": result.get("metadata", {})
            }
            print(json.dumps(json_output, ensure_ascii=False))
            
    except Exception as e:
        # 停止捕获输出
        captured_output = output_capture.stop_capture()
        
        logger.error(f"脚本执行异常: {str(e)}")
        # 输出错误信息为JSON格式
        json_output = {
            "error": f"脚本执行出错: {str(e)}",
            "metadata": {}
        }
        print(json.dumps(json_output, ensure_ascii=False))


if __name__ == "__main__":
    main()
