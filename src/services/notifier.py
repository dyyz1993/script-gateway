import json
import requests
from typing import Optional
import logging

from ..core.database import get_setting

logger = logging.getLogger('notifier')
logger.setLevel(logging.INFO)


def send_notify(title: str, body: str):
    url = get_setting('notify_url')
    if not url:
        logger.debug("Notify URL 未配置，跳过通知")
        return
    
    payload = {
        "title": title,
        "body": body,
        "group": "ScriptGateway",
    }
    
    try:
        logger.info(f"发送通知: {title} - {body[:50]}...")
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            logger.info("通知发送成功")
        else:
            logger.warning(f"通知发送失败，状态码: {response.status_code}")
    except Exception as e:
        logger.error(f"通知发送异常: {str(e)}")
