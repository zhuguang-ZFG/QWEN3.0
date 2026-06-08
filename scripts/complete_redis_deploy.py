#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完成 Redis 部署的最后步骤
"""
import paramiko
import sys
import io
import time

# 修复 Windows 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SERVER = '117.72.118.95'
PASSWORD = 'XINdandan521!'
REDIS_PASSWORD = 'reu/0E4Y3k+5yyaFqFbL6V1uw6wfs0UXfZk145xpp/Q='

def main():
    print('='*60)
    print('完成 Redis 部署')
    print('='*60)

    print('\n[1/5] 连接京东云...')
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username='root', password=PASSWORD, timeout=10)
    print('[OK] 已连接')

    print('\n[2/5] 备份当前配置...')
    stdin, stdout, stderr = ssh.exec_command('cp /etc/redis/redis.conf /etc/redis/redis.conf.backup.manual')
    stdout.channel.recv_exit_status()
    print('[OK] 已备份')

    print('\n[3/5] 写入新配置...')
    config_content = f"""bind 0.0.0.0
port 6379
protected-mode yes
requirepass {REDIS_PASSWORD}
timeout 300
tcp-keepalive 300

maxmemory 1gb
maxmemory-policy allkeys-lru

save 900 1
save 300 10
save 60 10000
rdbcompression yes
rdbchecksum yes
dbfilename dump.rdb
dir /var/lib/redis

loglevel notice
logfile /var/log/redis/redis-server.log

databases 16
daemonize no
supervised systemd
"""

    # 使用 cat 写入
    config_cmd = f"cat > /etc/redis/redis.conf << 'EOFCONFIG'\n{config_content}\nEOFCONFIG"
    stdin, stdout, stderr = ssh.exec_command(config_cmd)
    stdout.channel.recv_exit_status()
    print('[OK] 配置已写入')

    print('\n[4/5] 重启 Redis...')
    stdin, stdout, stderr = ssh.exec_command('systemctl restart redis-server')
    stdout.channel.recv_exit_status()
    time.sleep(3)
    print('[OK] Redis 已重启')

    print('\n[5/5] 测试连接...')
    test_cmd = f"redis-cli -a '{REDIS_PASSWORD}' ping 2>&1 | tail -1"
    stdin, stdout, stderr = ssh.exec_command(test_cmd)
    result = stdout.read().decode().strip()

    print(f'结果: {result}')

    if 'PONG' in result:
        print('\n' + '='*60)
        print('[SUCCESS] Redis 部署成功!')
        print('='*60)
        print(f'\n密码: {REDIS_PASSWORD}')
        print(f'主机: {SERVER}')
        print('端口: 6379')
        print('\n密码已保存到: C:\\Users\\zhugu\\Downloads\\redis_password.txt')
        print('\n下一步: 配置防火墙')
        print('  运行: bash /tmp/configure_firewall.sh')
    else:
        print('\n[ERROR] 测试失败')
        print(f'错误: {result}')

    ssh.close()

if __name__ == '__main__':
    main()
