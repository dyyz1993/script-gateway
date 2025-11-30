#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import threading
import time
from typing import Optional
from temp_file_manager import TempFileManager
from logger import get_gateway_logger


class TempFileService:
    """
    临时文件服务
    
    负责启动和管理临时文件清理系统
    """
    
    def __init__(self):
        self.temp_file_manager = TempFileManager()
        self.cleanup_thread: Optional[threading.Thread] = None
        self.logger = get_gateway_logger()
    
    def start_cleanup_service(self):
        """启动临时文件清理服务"""
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.logger.warning("临时文件清理服务已在运行中")
            return
        
        self.cleanup_thread = threading.Thread(
            target=self.temp_file_manager.cleanup_loop,
            daemon=True
        )
        self.cleanup_thread.start()
        self.logger.info("临时文件清理服务已启动")
    
    def stop_cleanup_service(self):
        """停止临时文件清理服务"""
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.temp_file_manager.stop_event.set()
            self.cleanup_thread.join(timeout=5)
            self.logger.info("临时文件清理服务已停止")
    
    def update_cleanup_interval(self, interval_hours: float):
        """更新清理间隔"""
        self.temp_file_manager.set_cleanup_interval_hours(interval_hours)
        self.logger.info(f"临时文件清理间隔已更新为 {interval_hours} 小时")
    
    def get_cleanup_status(self) -> dict:
        """获取清理状态"""
        return {
            "is_running": self.cleanup_thread and self.cleanup_thread.is_alive(),
            "cleanup_interval_hours": self.temp_file_manager.get_cleanup_interval_hours(),
            "temp_dirs": self.temp_file_manager.get_temp_directories()
        }
    
    def cleanup_once(self):
        """执行一次清理"""
        deleted_count = self.temp_file_manager.cleanup_once()
        self.logger.info(f"临时文件清理完成，删除了 {deleted_count} 个文件")
        return deleted_count


# 创建全局服务实例
temp_file_service = TempFileService()