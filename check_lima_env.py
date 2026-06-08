import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('47.112.162.80', username='root', password='XINdandan521!', timeout=15)

# 检查 LiMa 的 .env 文件
stdin,stdout,stderr = ssh.exec_command('cat /opt/lima-router/.env | grep -E "MYSQL|REDIS|DATABASE" 2>&1')
print('LiMa 数据库配置:')
print(stdout.read().decode())

# 检查 MySQL 配置
stdin,stdout,stderr = ssh.exec_command('cat /etc/mysql/mysql.conf.d/mysqld.cnf | grep -E "bind-address|port" 2>&1')
print('\nMySQL 配置:')
print(stdout.read().decode())

# 检查 MySQL 用户权限
stdin,stdout,stderr = ssh.exec_command("mysql -u root -e \"SELECT user, host, plugin FROM mysql.user WHERE user='root';\" 2>&1")
print('\nMySQL root 用户:')
print(stdout.read().decode())

ssh.close()
