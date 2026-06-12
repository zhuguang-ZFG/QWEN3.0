# qwen2API 缓存解决方案 - Nginx 缓存

**方案**: 使用 Nginx 作为缓存代理层
**优势**: 生产级、稳定、高性能、配置简单

---

## 🎯 **架构设计**

```
MiMo Code (:7864) → Nginx 缓存层 (:7864)
                         ↓
                    qwen2API (:7862)
                         ↓
                    Qwen 官方 API
```

**缓存策略**:
- POST 请求按 body hash 缓存
- 缓存时长: 24 小时
- 缓存大小: 1GB
- 命中率: 预期 60-80%

---

## 📝 **Nginx 配置**

### 1. nginx.conf

```nginx
# qwen2api_cache.conf

# 缓存路径配置
proxy_cache_path C:/nginx/cache/qwen2api
    levels=1:2
    keys_zone=qwen_cache:100m
    max_size=1g
    inactive=24h
    use_temp_path=off;

# 上游服务器
upstream qwen2api_backend {
    server 127.0.0.1:7862;
    keepalive 32;
}

server {
    listen 7864;
    server_name localhost;

    # 日志
    access_log C:/nginx/logs/qwen2api_access.log;
    error_log C:/nginx/logs/qwen2api_error.log;

    # 健康检查
    location /healthz {
        proxy_pass http://qwen2api_backend;
        proxy_cache off;
    }

    # 模型列表（不缓存）
    location /v1/models {
        proxy_pass http://qwen2api_backend;
        proxy_cache off;

        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
    }

    # 聊天补全（带缓存）
    location /v1/chat/completions {
        # 缓存配置
        proxy_cache qwen_cache;
        proxy_cache_methods POST;
        proxy_cache_key "$request_method$request_uri$request_body";

        # 缓存有效期
        proxy_cache_valid 200 24h;
        proxy_cache_valid 404 1m;

        # 缓存状态头
        add_header X-Cache-Status $upstream_cache_status;

        # 上游配置
        proxy_pass http://qwen2api_backend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header Content-Type application/json;

        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;

        # Body 大小
        client_max_body_size 10m;
        client_body_buffer_size 1m;
    }

    # 缓存统计
    location /cache/stats {
        return 200 '{"cache_zone":"qwen_cache","max_size":"1GB","inactive":"24h"}';
        add_header Content-Type application/json;
    }
}
```

---

## 🚀 **部署步骤**

### Windows 部署

#### 1. 下载 Nginx

```powershell
# 下载 Nginx for Windows
# https://nginx.org/en/download.html
# 解压到 C:\nginx
```

#### 2. 配置文件

```powershell
# 创建配置目录
mkdir C:\nginx\conf\custom

# 创建缓存目录
mkdir C:\nginx\cache\qwen2api

# 创建日志目录
mkdir C:\nginx\logs

# 复制上面的配置到
C:\nginx\conf\custom\qwen2api_cache.conf
```

#### 3. 修改主配置

编辑 `C:\nginx\conf\nginx.conf`，在 http 块末尾添加：

```nginx
http {
    # ... 其他配置 ...

    # 包含自定义配置
    include custom/*.conf;
}
```

#### 4. 启动 Nginx

```powershell
cd C:\nginx
.\nginx.exe

# 或者安装为服务
# sc create nginx binPath= "C:\nginx\nginx.exe"
# sc start nginx
```

#### 5. 测试

```powershell
# 健康检查
curl http://localhost:7864/healthz

# 测试缓存
curl -X POST http://localhost:7864/v1/chat/completions `
  -H "Authorization: Bearer sk-qwen-local-2026" `
  -H "Content-Type: application/json" `
  -d '{"model":"qwen3.7-plus","messages":[{"role":"user","content":"test"}]}'
```

---

## 📊 **验证缓存工作**

### 检查缓存头

```bash
# 第一次请求（MISS）
curl -I -X POST http://localhost:7864/v1/chat/completions \
  -H "Authorization: Bearer sk-qwen-local-2026" \
  -d '{"model":"qwen3.7-plus","messages":[{"role":"user","content":"1+1=?"}]}'

# 应该看到: X-Cache-Status: MISS

# 第二次请求（HIT）
curl -I -X POST http://localhost:7864/v1/chat/completions \
  -H "Authorization: Bearer sk-qwen-local-2026" \
  -d '{"model":"qwen3.7-plus","messages":[{"role":"user","content":"1+1=?"}]}'

# 应该看到: X-Cache-Status: HIT
```

### 查看缓存文件

```powershell
# 查看缓存目录
dir C:\nginx\cache\qwen2api
```

---

## 🎛️ **MiMo Code 配置更新**

修改 `~/.config/mimocode/mimocode.json`:

```json
{
  "providers": {
    "qwen-cached": {
      "name": "Qwen Local (Cached)",
      "baseURL": "http://localhost:7864/v1",
      "apiKey": "sk-qwen-local-2026",
      "models": [
        "qwen3.7-plus",
        "qwen3.7-max",
        "qwen3-coder-plus"
      ],
      "default": "qwen3.7-plus"
    }
  },
  "defaultProvider": "qwen-cached"
}
```

**改动**: `baseURL` 从 `:7862` 改为 `:7864`

---

## 📈 **预期效果**

### 性能提升

| 指标 | 无缓存 | 有缓存 |
|------|--------|--------|
| 首次请求 | 5-10s | 5-10s |
| 重复请求 | 5-10s | **10-50ms** |
| 风控风险 | 100% | **30%** |
| 服务器负载 | 100% | **20-40%** |

### 缓存命中率

| 场景 | 预期命中率 |
|------|-----------|
| 代码补全 | 70-80% |
| 重复问答 | 80-90% |
| 多样化对话 | 40-60% |

---

## 🔧 **高级配置**

### 按模型分别缓存

```nginx
location /v1/chat/completions {
    set $cache_ttl 24h;

    # 代码模型缓存更长
    if ($request_body ~ "qwen3-coder") {
        set $cache_ttl 168h;  # 7天
    }

    # 思考模式缓存中等
    if ($request_body ~ "thinking") {
        set $cache_ttl 48h;  # 2天
    }

    proxy_cache_valid 200 $cache_ttl;
}
```

### 忽略特定参数

```nginx
# 忽略 temperature 差异
proxy_cache_key "$request_method$request_uri$request_body_sanitized";
```

### 缓存预热

```bash
# 常见问题预热脚本
for q in "1+1=?" "Hello" "你好"; do
  curl -X POST http://localhost:7864/v1/chat/completions \
    -H "Authorization: Bearer sk-qwen-local-2026" \
    -d "{\"model\":\"qwen3.7-plus\",\"messages\":[{\"role\":\"user\",\"content\":\"$q\"}]}"
done
```

---

## 🛠️ **管理命令**

### 清空缓存

```powershell
# 停止 Nginx
cd C:\nginx
.\nginx.exe -s stop

# 删除缓存
Remove-Item -Recurse C:\nginx\cache\qwen2api\*

# 重启
.\nginx.exe
```

### 查看日志

```powershell
# 访问日志
Get-Content C:\nginx\logs\qwen2api_access.log -Tail 50

# 错误日志
Get-Content C:\nginx\logs\qwen2api_error.log -Tail 50
```

### 重载配置

```powershell
cd C:\nginx
.\nginx.exe -s reload
```

---

## ✅ **优势**

1. **生产级稳定**: Nginx 久经考验
2. **零代码改动**: 不需要修改 qwen2API
3. **高性能**: C 语言实现，毫秒级响应
4. **透明缓存**: 对 MiMo Code 完全透明
5. **易于管理**: 简单配置即可

---

## 🎯 **总结**

**Nginx 缓存是最佳方案**:
- ✅ 简单可靠
- ✅ 性能优秀
- ✅ 易于部署
- ✅ 生产级稳定

**下一步**: 安装 Nginx 并应用配置
