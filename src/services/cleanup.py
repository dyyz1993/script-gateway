import threading
import time
import schedule
from ..core.database import get_setting
from ..utils.logger import cleanup_expired_logs, get_gateway_logger


def cleanup_task():
    """定时清理过期日志任务"""
    logger = get_gateway_logger()
    try:
        script_days = int(get_setting('script_log_retention_days') or '7')
        gateway_days = int(get_setting('gateway_log_retention_days') or '7')
        
        logger.info(f"开始清理过期日志，脚本日志保留{script_days}天，网关日志保留{gateway_days}天")
        result = cleanup_expired_logs(script_days, gateway_days)
        logger.info(f"日志清理完成，脚本日志清理{result['script']}个文件，网关日志清理{result['gateway']}个文件")
    except Exception as e:
        logger.error(f"日志清理失败: {str(e)}")


def run_scheduler():
    """调度器运行线程"""
    # 每天凌晨2点执行清理
    schedule.every().day.at("02:00").do(cleanup_task)
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分钟检查一次


def start_cleanup_scheduler():
    """启动日志清理调度器"""
    t = threading.Thread(target=run_scheduler, daemon=True, name="LogCleanup")
    t.start()
