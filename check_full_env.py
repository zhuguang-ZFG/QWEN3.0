import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('47.112.162.80', username='root', password='XINdandan521!', timeout=15)

# 查看完整的 .env 文件
stdin,stdout,stderr = ssh.exec_command('cat /opt/lima-router/.env 2>&1')
print('LiMa .env 完整内容:')
print(stdout.read().decode()[:3000])

# 检查 MySQL 配置文件位置
stdin,stdout,stderr = ssh.exec_command('ls -la /etc/mysql/ 2>&1')
print('\nMySQL 配置目录:')
print(stdout.read().decode())

# 检查 MySQL 错误日志
stdin,stdout,stderr = ssh.exec_command('tail -50 /var/log/mysql/error.log 2>&1 | tail -30')
print('\nMySQL 错误日志:')
print(stdout.read().decode())

ssh.close()
