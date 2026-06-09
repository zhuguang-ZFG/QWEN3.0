# 京东云部署 - 最终方案总结

## 问题诊断

1. **Docker Hub 不可达**: 京东云无法访问 Docker Hub
2. **GitHub 下载超时**: 直接从 GitHub 下载 Prometheus 超时
3. **内网不通**: 阿里云 47.112.162.80 → 京东云 117.72.118.95 网络不通
   - ping 100% 丢包
   - wget/curl 连接超时

## 解决方案

### 方案 1：用户手动上传（最可靠）

从本地上传 Prometheus 到京东云：

```powershell
# Windows 本地下载
Invoke-WebRequest https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz -OutFile prometheus.tar.gz

# 上传到京东云
scp prometheus.tar.gz root@117.72.118.95:/opt/lima-monitoring/
```

然后在京东云执行：
```bash
cd /opt/lima-monitoring
tar xzf prometheus.tar.gz
mv prometheus-2.45.0.linux-amd64 prometheus-bin
# ... 后续步骤见完整脚本
```

### 方案 2：使用国内镜像源

在京东云直接执行：

```bash
cd /opt/lima-monitoring
mkdir -p data prometheus-bin

# 尝试华为云镜像
wget https://mirrors.huaweicloud.com/prometheus/2.45.0/prometheus-2.45.0.linux-amd64.tar.gz

# 如果失败，尝试清华源
wget https://mirrors.tuna.tsinghua.edu.cn/prometheus/prometheus-2.45.0.linux-amd64.tar.gz

tar xzf prometheus-2.45.0.linux-amd64.tar.gz
mv prometheus-2.45.0.linux-amd64/* prometheus-bin/
```

### 方案 3：放弃京东云监控

**现实评估**：
- 京东云 3.8GB 内存有限
- 网络隔离严重
- 部署成本过高

**替代方案**：
在阿里云 VPS 本地部署轻量监控：
- Prometheus（占用 ~200MB）
- 简化版探测脚本（Python）
- 暂缓 Grafana（改用 Prometheus Web UI）

## 推荐行动

鉴于当前困难，建议：

1. **短期**：在阿里云本地部署 Prometheus + 简单探测
2. **中期**：升级阿里云 VPS 内存（当前 1.3GB 太紧张）
3. **长期**：等京东云网络政策调整或迁移到其他 VPS

## 已完成工作

✅ 设计文档编写
✅ 部署脚本准备
✅ 阿里云 Prometheus 安装包下载
✅ HTTP 文件服务配置
✅ 网络诊断分析

## 当前阻塞

❌ 京东云 ↔ 阿里云内网不通
❌ 京东云无法访问外网软件源
