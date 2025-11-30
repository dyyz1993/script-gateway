#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import argparse
import json
import sys
import os
from pathlib import Path
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess
from model import SenseVoiceSmall
FUNASR_AVAILABLE = True
# 尝试导入SenseVoice相关依赖

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
    if not os.path.exists(audio_path):
        return False, f"音频文件不存在: {audio_path}"
    
    supported_formats = ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac']
    file_ext = Path(audio_path).suffix.lower()
    
    if file_ext not in supported_formats:
        return False, f"不支持的音频格式: {file_ext}，支持的格式: {', '.join(supported_formats)}"
    
    return True, ""


def transcribe_audio(audio_path, language="auto", use_itn=True, output_timestamp=False, device="cpu"):
    """使用SenseVoice进行音频转录"""
    
    # 检查依赖是否可用
    if not FUNASR_AVAILABLE:
        return {
            "success": False,
            "error": f"缺少必要依赖: {IMPORT_ERROR}",
            "code": 500
        }
    
    try:
        # 初始化模型
        model_dir = "iic/SenseVoiceSmall"
        model = AutoModel(
            model=model_dir,
            trust_remote_code=True,
            remote_code="./model.py",
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
            device=device,
        )
        
        # 进行语音识别
        res = model.generate(
            input=audio_path,
            cache={},
            language=language,
            use_itn=use_itn,
            batch_size_s=60,
            merge_vad=True,
            merge_length_s=15,
        )
        
        if not res or len(res) == 0:
            return {
                "success": False,
                "error": "转录失败或无结果",
                "code": 400
            }
        
        # 处理结果
        result_data = {
            "success": True,
            "text": rich_transcription_postprocess(res[0]["text"]),
            "code": 200
        }
        
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
        
        if metadata:
            result_data["metadata"] = metadata
        
        # 时间戳信息
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
                    result_data["timestamps"] = timestamp_res[0][0].get("timestamp", [])
                    
            except Exception as e:
                # 时间戳提取失败不影响主流程
                print(f"警告: 时间戳提取失败: {e}")
        
        return result_data
        
    except Exception as e:
        return {
            "success": False,
            "error": f"转录过程中出错: {str(e)}",
            "code": 500
        }


def main():
    parser = argparse.ArgumentParser(description="SenseVoice音频转录工具")
    
    for key, cfg in ARGS_MAP.items():
        arg_kwargs = {
            "required": cfg.get("required", False),
            "help": cfg.get("help", "")
        }
        
        # 处理布尔类型参数
        if cfg["type"] == "bool":
            if cfg.get("default", False):
                arg_kwargs["action"] = "store_false"
                # 将flag改为--no-flag格式
                flag = cfg["flag"].replace("--", "--no-")
            else:
                arg_kwargs["action"] = "store_true"
                flag = cfg["flag"]
            
            if cfg.get("default") is not None:
                arg_kwargs["default"] = cfg["default"]
            
            parser.add_argument(flag, **arg_kwargs)
        else:
            parser.add_argument(cfg["flag"], **arg_kwargs)

    if len(sys.argv) > 1 and sys.argv[1] == "--_sys_get_schema":
        print(get_schema())
        sys.exit(0)

    args = parser.parse_args()
    
    # 获取参数
    audio_path = getattr(args, 'audio')
    language = getattr(args, 'language', 'auto')
    use_itn = getattr(args, 'use_itn', True)
    output_timestamp = getattr(args, 'output_timestamp', False)
    output_file = getattr(args, 'output_file', None)
    device = getattr(args, 'device', 'cpu')
    
    # 验证音频文件
    is_valid, error_msg = validate_audio_file(audio_path)
    if not is_valid:
        result = {
            "success": False,
            "error": error_msg,
            "code": 400
        }
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    
    # 执行转录
    print(f"🎵 开始转录音频: {audio_path}")
    result = transcribe_audio(audio_path, language, use_itn, output_timestamp, device)
    
    # 输出结果
    if result.get("success"):
        print("✅ 转录成功！")
        
        # 输出到文件
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"📄 结果已保存到: {output_file}")
        
        # 控制台输出主要结果
        print("\n📝 转录结果:")
        print("=" * 60)
        print(result.get("text", ""))
        print("=" * 60)
        
        # 显示元数据
        if "metadata" in result:
            print("\n📊 元数据:")
            for key, value in result["metadata"].items():
                print(f"   {key}: {value}")
    
    else:
        print(f"❌ 转录失败: {result.get('error', '未知错误')}")
    
    # 输出完整JSON结果
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
