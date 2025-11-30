#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import os
import re
import uuid
import time
import requests
import tempfile
from pathlib import Path
from typing import Optional, Tuple, List
from urllib.parse import urlparse
from ..core.config import Config
from ..core.database import get_setting
from ..utils.file_access_checker import FileAccessChecker


class MediaProcessor:
    """媒体文件处理器，支持本地文件和远程URL的统一处理"""
    
    def __init__(self):
        # 创建临时目录
        self.temp_dir = os.path.join(Config.BASE_DIR, 'tmp', 'media')
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # 支持的媒体文件扩展名
        self.audio_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac', '.wma'}
        self.video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}
        self.media_extensions = self.audio_extensions | self.video_extensions
        
        # 初始化文件访问检查器
        self.file_access_checker = FileAccessChecker()
    
    def is_url(self, path: str) -> bool:
        """判断给定路径是否为URL"""
        try:
            result = urlparse(path)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    
    
    def is_path_allowed(self, file_path: str) -> Tuple[bool, str]:
        """检查文件路径是否在允许的范围内"""
        return self.file_access_checker.is_path_allowed(file_path)
    
    def download_from_url(self, url: str, timeout: int = 300) -> Tuple[bool, str, str]:
        """从URL下载文件到临时目录
        
        Args:
            url: 文件URL
            timeout: 下载超时时间（秒）
            
        Returns:
            Tuple[成功标志, 本地文件路径, 错误信息]
        """
        try:
            # 获取文件扩展名
            parsed_url = urlparse(url)
            path = parsed_url.path
            ext = os.path.splitext(path)[1].lower()
            
            # 如果无法从URL获取扩展名，尝试从Content-Type获取
            if not ext:
                response = requests.head(url, timeout=10)
                content_type = response.headers.get('content-type', '')
                if 'audio' in content_type:
                    ext = '.mp3'  # 默认音频扩展名
                elif 'video' in content_type:
                    ext = '.mp4'  # 默认视频扩展名
            
            # 生成临时文件名
            temp_filename = f"{uuid.uuid4().hex}{ext}"
            temp_path = os.path.join(self.temp_dir, temp_filename)
            
            # 下载文件
            response = requests.get(url, timeout=timeout, stream=True)
            response.raise_for_status()
            
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            return True, temp_path, ""
            
        except requests.exceptions.Timeout:
            return False, "", f"下载超时: {url}"
        except requests.exceptions.RequestException as e:
            return False, "", f"下载失败: {str(e)}"
        except Exception as e:
            return False, "", f"处理下载文件时出错: {str(e)}"
    
    def validate_media_file(self, file_path: str) -> Tuple[bool, str]:
        """验证文件是否为支持的媒体文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            Tuple[是否有效, 错误信息]
        """
        if not os.path.exists(file_path):
            return False, f"文件不存在: {file_path}"
        
        if not os.path.isfile(file_path):
            return False, f"路径不是文件: {file_path}"
        
        # 检查文件扩展名
        ext = Path(file_path).suffix.lower()
        if ext not in self.media_extensions:
            return False, f"不支持的媒体文件格式: {ext}，支持的格式: {', '.join(sorted(self.media_extensions))}"
        
        return True, ""
    
    def process_media_input(self, media_input: str, param_name: str = "media") -> Tuple[bool, str, str]:
        """处理媒体输入，支持本地文件路径和远程URL
        
        Args:
            media_input: 媒体输入（本地路径或URL）
            param_name: 参数名称（用于错误信息）
            
        Returns:
            Tuple[成功标志, 本地文件路径, 错误信息]
        """
        if not media_input:
            return False, "", f"参数 {param_name} 不能为空"
        
        # 如果是URL，先下载
        if self.is_url(media_input):
            success, local_path, error = self.download_from_url(media_input)
            if not success:
                return False, "", f"从URL下载媒体文件失败: {error}"
        else:
            # 本地文件，检查路径是否允许
            success, error = self.is_path_allowed(media_input)
            if not success:
                return False, "", error
            
            local_path = media_input
        
        # 验证媒体文件
        success, error = self.validate_media_file(local_path)
        if not success:
            return False, "", error
        
        return True, local_path, ""
    
    def get_file_type(self, file_path: str) -> str:
        """获取文件类型（audio/video）"""
        ext = Path(file_path).suffix.lower()
        if ext in self.audio_extensions:
            return "audio"
        elif ext in self.video_extensions:
            return "video"
        else:
            return "unknown"