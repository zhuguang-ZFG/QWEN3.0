#!/usr/bin/env python3
"""
LiMa 服务健康检查脚本
用于监控关键服务状态并发送告警
"""

import requests
import json
import subprocess
import time
from datetime import datetime

# 配置
HEALTHCHECKS_IO_PING_URL = "https://hc-ping.com/YOUR_PING_UUID"  # 替换为你的 Healthchecks.io ping URL
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"  # 替换为你的 Telegram Bot Token
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"  # 替换为你的 Telegram Chat ID

# 服务配置
SERVICES = {
    'lima-router': {
        'port': 8080,
        'path': '/health',
        'expected_status': 200,
    },
    'nginx': {
        'port': 80,
        'path': '/',
        'expected_status': 200,
    },
    'redis': {
        'port': 6379,
        'check_command': 'redis-cli ping',
    },
}

def check_service(name, config):
    """检查服务状态"""
    try:
        if 'path' in config:
            # HTTP 服务检查
            url = f"http://localhost:{config['port']}{config['path']}"
            response = requests.get(url, timeout=10)
            return response.status_code == config['expected_status']
        elif 'check_command' in config:
            # 命令行检查
            result = subprocess.run(
                config['check_command'].split(),
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
    except Exception as e:
        print(f"检查 {name} 失败: {e}")
        return False

def send_telegram_alert(message):
    """发送 Telegram 告警"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram 未配置，跳过告警")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            print("Telegram 告警发送成功")
        else:
            print(f"Telegram 告警发送失败: {response.status_code}")
    except Exception as e:
        print(f"Telegram 告警发送异常: {e}")

def ping_healthchecks_io():
    """向 Healthchecks.io 发送心跳"""
    if not HEALTHCHECKS_IO_PING_URL or 'YOUR_PING_UUID' in HEALTHCHECKS_IO_PING_URL:
        print("Healthchecks.io 未配置，跳过心跳")
        return
    
    try:
        response = requests.get(HEALTHCHECKS_IO_PING_URL, timeout=10)
        if response.status_code == 200:
            print("Healthchecks.io 心跳发送成功")
        else:
            print(f"Healthchecks.io 心跳发送失败: {response.status_code}")
    except Exception as e:
        print(f"Healthchecks.io 心跳发送异常: {e}")

def main():
    """主检查流程"""
    print(f"\n{'='*60}")
    print(f"LiMa 服务健康检查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    failed_services = []
    
    for service_name, config in SERVICES.items():
        is_healthy = check_service(service_name, config)
        status = "✓ 正常" if is_healthy else "✗ 异常"
        print(f"{service_name}: {status}")
        
        if not is_healthy:
            failed_services.append(service_name)
    
    # 发送心跳
    ping_healthchecks_io()
    
    # 如果有服务异常，发送告警
    if failed_services:
        alert_message = f"""
<b>⚠️ LiMa 服务异常告警</b>

<b>时间:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
<b>异常服务:</b> {', '.join(failed_services)}

请及时检查服务器状态！
        """.strip()
        
        send_telegram_alert(alert_message)
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())
