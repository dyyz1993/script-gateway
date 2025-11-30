#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import os
import time
import threading
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timedelta
from ..core.config import Config
from ..core.database import get_setting, set_setting
from ..utils.logger import get_gateway_logger


class TempFileManager:
    """临时文件管理器，负责定期清理过期的临时文件"""
    
    def __init__(self, cleanup_interval_hours: float = None):
        """
        初始化临时文件管理器
        
        Args:
            cleanup_interval_hours: 清理间隔（小时），如果为None则使用配置中的默认值
        """
        self.logger = get_gateway_logger()
        self.cleanup_thread = None
        self.stop_event = threading.Event()
        
        # 设置清理间隔
        if cleanup_interval_hours is not None:
            self.cleanup_interval_hours = cleanup_interval_hours
        else:
            # 从配置获取默认值，如果没有配置则使用24小时
            self.cleanup_interval_hours = Config.get_temp_file_cleanup_interval()
        
        # 临时文件目录
        self.temp_dirs = {
            'upload': os.path.join(Config.BASE_DIR, 'tmp', 'upload'),
            'media': os.path.join(Config.BASE_DIR, 'tmp', 'media'),
            'output': os.path.join(Config.BASE_DIR, 'static', 'output')
        }
        
        # 确保目录存在
        for dir_path in self.temp_dirs.values():
            os.makedirs(dir_path, exist_ok=True)
    
    def get_cleanup_interval_hours(self) -> int:
        """获取清理间隔时间（小时）"""
        return int(Config.get_temp_file_cleanup_interval())
    
    def set_cleanup_interval_hours(self, hours: int):
        """设置清理间隔时间（小时）"""
        set_setting('temp_file_cleanup_interval_hours', str(hours))
        self.logger.info(f"临时文件清理间隔已设置为: {hours}小时")
    
    def get_file_max_age_hours(self, file_type: str = 'default') -> int:
        """获取文件最大保存时间（小时）"""
        age_str = get_setting(f'temp_file_max_age_hours_{file_type}') or get_setting('temp_file_max_age_hours_default') or '24'
        try:
            return int(age_str)
        except ValueError:
            return 24  # 默认24小时
    
    def set_file_max_age_hours(self, hours: int, file_type: str = 'default'):
        """设置文件最大保存时间（小时）"""
        set_setting(f'temp_file_max_age_hours_{file_type}', str(hours))
        self.logger.info(f"临时文件最大保存时间已设置为: {hours}小时 (类型: {file_type})")
    
    def is_file_expired(self, file_path: str, max_age_hours: int) -> bool:
        """检查文件是否过期"""
        try:
            file_mtime = os.path.getmtime(file_path)
            file_time = datetime.fromtimestamp(file_mtime)
            expire_time = datetime.now() - timedelta(hours=max_age_hours)
            return file_time < expire_time
        except Exception:
            return True  # 如果无法获取文件时间，视为过期
    
    def scan_expired_files(self, dir_path: str, max_age_hours: int) -> List[str]:
        """扫描目录中的过期文件"""
        expired_files = []
        
        if not os.path.isdir(dir_path):
            return expired_files
        
        try:
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if self.is_file_expired(file_path, max_age_hours):
                        expired_files.append(file_path)
        except Exception as e:
            self.logger.error(f"扫描过期文件时出错: {str(e)}")
        
        return expired_files
    
    def delete_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """删除文件列表"""
        results = {
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        for file_path in file_paths:
            try:
                os.remove(file_path)
                results['success'] += 1
                self.logger.debug(f"已删除过期文件: {file_path}")
            except Exception as e:
                results['failed'] += 1
                error_msg = f"删除文件失败 {file_path}: {str(e)}"
                results['errors'].append(error_msg)
                self.logger.error(error_msg)
        
        # 尝试删除空目录
        for file_path in file_paths:
            try:
                parent_dir = os.path.dirname(file_path)
                # 如果目录为空，则删除
                if os.path.isdir(parent_dir) and not os.listdir(parent_dir):
                    os.rmdir(parent_dir)
                    self.logger.debug(f"已删除空目录: {parent_dir}")
            except Exception:
                pass  # 忽略删除目录的错误
        
        return results
    
    def cleanup_once(self) -> Dict[str, Any]:
        """执行一次清理操作"""
        self.logger.info("开始清理临时文件...")
        
        total_results = {
            'success': 0,
            'failed': 0,
            'errors': [],
            'details': {}
        }
        
        # 清理不同类型的临时文件
        for file_type, dir_path in self.temp_dirs.items():
            max_age = self.get_file_max_age_hours(file_type)
            expired_files = self.scan_expired_files(dir_path, max_age)
            
            if expired_files:
                self.logger.info(f"发现 {len(expired_files)} 个过期的 {file_type} 文件")
                results = self.delete_files(expired_files)
                
                total_results['success'] += results['success']
                total_results['failed'] += results['failed']
                total_results['errors'].extend(results['errors'])
                total_results['details'][file_type] = results
            else:
                self.logger.info(f"没有发现过期的 {file_type} 文件")
        
        self.logger.info(f"临时文件清理完成: 成功 {total_results['success']} 个，失败 {total_results['failed']} 个")
        
        return total_results
    
    def cleanup_loop(self):
        """清理循环线程"""
        self.logger.info("临时文件清理线程已启动")
        
        while not self.stop_event.is_set():
            try:
                self.cleanup_once()
            except Exception as e:
                self.logger.error(f"清理过程中出错: {str(e)}")
            
            # 等待到下一次清理时间
            interval_hours = self.get_cleanup_interval_hours()
            interval_seconds = interval_hours * 3600
            
            # 使用wait而不是sleep，这样可以响应停止信号
            self.stop_event.wait(interval_seconds)
        
        self.logger.info("临时文件清理线程已停止")
    
    def start_cleanup_scheduler(self):
        """启动清理调度器"""
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.logger.warning("清理线程已在运行")
            return
        
        self.stop_event.clear()
        self.cleanup_thread = threading.Thread(target=self.cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        self.logger.info("临时文件清理调度器已启动")
    
    def stop_cleanup_scheduler(self):
        """停止清理调度器"""
        if not self.cleanup_thread or not self.cleanup_thread.is_alive():
            return
        
        self.stop_event.set()
        self.cleanup_thread.join(timeout=5)
        self.logger.info("临时文件清理调度器已停止")
    
    def get_cleanup_status(self) -> Dict[str, Any]:
        """获取清理状态"""
        return {
            'is_running': self.cleanup_thread and self.cleanup_thread.is_alive(),
            'cleanup_interval_hours': self.get_cleanup_interval_hours(),
            'max_age_hours': {
                'default': self.get_file_max_age_hours('default'),
                'upload': self.get_file_max_age_hours('upload'),
                'media': self.get_file_max_age_hours('media'),
                'output': self.get_file_max_age_hours('output')
            },
            'temp_dirs': self.temp_dirs
        }


# 全局实例
_temp_file_manager = None


def get_temp_file_manager() -> TempFileManager:
    """获取全局临时文件管理器实例"""
    global _temp_file_manager
    if _temp_file_manager is None:
        _temp_file_manager = TempFileManager()
    return _temp_file_manager


def start_temp_file_cleanup():
    """启动临时文件清理"""
    manager = get_temp_file_manager()
    manager.start_cleanup_scheduler()


def stop_temp_file_cleanup():
    """停止临时文件清理"""
    manager = get_temp_file_manager()
    manager.stop_cleanup_scheduler()