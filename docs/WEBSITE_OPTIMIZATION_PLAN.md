# 官网和 Chat 平台性能优化方案

> **发现时间**: 2026-06-08  
> **严重程度**: 高  
> **状态**: 待优化

---

## 🔴 性能问题

### 响应时间过慢
```
chat.donglicao.com: 4.10s (目标 <1s)
donglicao.com:      3.09s (目标 <1s)
api.donglicao.com:  4.78s (目标 <1s)
```

### Agnes 视频服务错误
```
端点: /v1/videos/agnes_generate
错误: Connection refused (upstream 127.0.0.1:8080)
频率: 多次失败
```

---

## 🎯 优化方案

### 方案 1: Nginx Gzip 压缩 (立即执行)

**配置文件**: `/etc/nginx/nginx.conf`

```nginx
# 添加 Gzip 压缩
gzip on;
gzip_vary on;
gzip_proxied any;
gzip_comp_level 6;
gzip_types text/plain text/css text/xml text/javascript 
           application/json application/javascript application/xml+rss 
           application/rss+xml font/truetype font/opentype 
           application/vnd.ms-fontobject image/svg+xml;
gzip_disable "msie6";
```

**预期效果**: 响应大小减少 60-80%

### 方案 2: 静态资源缓存 (立即执行)

```nginx
# 在 server 块中添加
location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg|woff|woff2|ttf)$ {
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```

### 方案 3: 修复 Agnes 服务 (紧急)

**检查命令**:
```bash
# 检查端口 8080 是否监听
netstat -tlnp | grep 8080

# 检查 agnes 服务
systemctl status agnes-service  # 如果有 systemd 服务
ps aux | grep agnes             # 检查进程
```

**临时方案**: 禁用 agnes_generate 路由或返回友好错误

### 方案 4: CDN 配置 (推荐)

**建议使用**:
- Cloudflare (免费)
- 阿里云 CDN
- 腾讯云 CDN

**预期效果**: 响应时间降低 50-70%

---

## 📋 执行清单

### 立即执行 (30分钟)
- [ ] 启用 Nginx Gzip 压缩
- [ ] 配置静态资源缓存
- [ ] 重启 Nginx
- [ ] 验证效果

### 紧急修复 (1小时)
- [ ] 检查 Agnes 服务状态
- [ ] 修复或禁用 agnes_generate
- [ ] 更新 Nginx 配置
- [ ] 测试视频生成功能

### 中期优化 (本周)
- [ ] 配置 CDN
- [ ] 优化图片资源
- [ ] 添加监控告警
- [ ] 性能测试

---

## 🔧 Nginx 完整优化配置

```nginx
# /etc/nginx/sites-available/donglicao.com

server {
    listen 443 ssl http2;
    server_name donglicao.com www.donglicao.com;

    ssl_certificate /etc/letsencrypt/live/donglicao.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/donglicao.com/privkey.pem;

    # Gzip 压缩
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript 
               application/json application/javascript application/xml+rss;

    # 静态资源缓存
    location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg|woff2)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # 主站点
    location / {
        root /var/www/donglicao.com;
        index index.html;
        try_files $uri $uri/ =404;
    }
}

server {
    listen 443 ssl http2;
    server_name chat.donglicao.com;

    ssl_certificate /etc/letsencrypt/live/chat.donglicao.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/chat.donglicao.com/privkey.pem;

    # Gzip 压缩
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript 
               application/json application/javascript;

    # 禁用或修复 agnes_generate (临时)
    location /v1/videos/agnes_generate {
        return 503 '{"error": "Service temporarily unavailable"}';
        add_header Content-Type application/json;
    }

    # 代理到 LiMa
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

---

## 📊 预期效果

| 指标 | 当前 | 优化后 | 提升 |
|------|------|--------|------|
| chat 响应时间 | 4.10s | <1s | **75% ↓** |
| 官网响应时间 | 3.09s | <1s | **67% ↓** |
| API 响应时间 | 4.78s | <1s | **79% ↓** |
| 传输大小 | 100% | 30% | **70% ↓** |
| Agnes 错误率 | 100% | 0% | **修复** |

---

## 🚀 部署步骤

```bash
# 1. 备份配置
sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup
sudo cp /etc/nginx/sites-available/donglicao.com /etc/nginx/sites-available/donglicao.com.backup

# 2. 编辑配置
sudo nano /etc/nginx/nginx.conf
# 添加 Gzip 配置

sudo nano /etc/nginx/sites-available/donglicao.com
# 添加缓存和优化配置

# 3. 测试配置
sudo nginx -t

# 4. 重启 Nginx
sudo systemctl reload nginx

# 5. 验证效果
curl -I https://chat.donglicao.com
curl -I --compressed https://donglicao.com
```

---

## 📞 支持

如需帮助，运行监控工具：
```bash
python scripts/monitor_websites.py --once
```

---

**创建时间**: 2026-06-08  
**优先级**: 高  
**预计时间**: 2 小时
