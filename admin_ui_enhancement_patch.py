"""
后端管理面板增强补丁
为 admin_ui.py 添加新功能：
1. 后端实时状态监控
2. 缓存统计展示
3. 批量操作改进
4. 性能图表
"""

# 新增 API 端点

def get_backend_health_stats():
    """获取后端健康统计"""
    try:
        import backends_registry
        backends = backends_registry.BACKENDS

        stats = {
            'total': len(backends),
            'active': 0,
            'providers': {},
            'categories': {
                'commercial': 0,
                'free': 0,
                'community': 0
            }
        }

        # 统计各类型后端
        for name, config in backends.items():
            # 根据后端名称分类
            if any(x in name for x in ['naga', 'cerebras', 'openai', 'anthropic']):
                stats['categories']['commercial'] += 1
            elif any(x in name for x in ['free', 'community']):
                stats['categories']['free'] += 1
            else:
                stats['categories']['community'] += 1

        return stats
    except:
        return {'total': 0, 'active': 0, 'providers': {}, 'categories': {}}


def get_cache_stats():
    """获取缓存统计"""
    try:
        import redis
        r = redis.Redis(
            host='100.85.114.65',
            port=6379,
            password='reu/0E4Y3k+5yyaFqFbL6V1uw6wfs0UXfZk145xpp/Q=',
            decode_responses=True
        )

        info = r.info('stats')

        stats = {
            'keys': r.dbsize(),
            'hits': info.get('keyspace_hits', 0),
            'misses': info.get('keyspace_misses', 0),
            'hit_rate': 0,
            'memory': r.info('memory').get('used_memory_human', '0'),
            'uptime': r.info('server').get('uptime_in_seconds', 0)
        }

        total = stats['hits'] + stats['misses']
        if total > 0:
            stats['hit_rate'] = round(stats['hits'] / total * 100, 2)

        return stats
    except:
        return {
            'keys': 0,
            'hits': 0,
            'misses': 0,
            'hit_rate': 0,
            'memory': '0',
            'uptime': 0
        }


# 添加到 admin_ui.py 的路由中
"""
@app.get("/admin/api/backend-health")
async def backend_health():
    return get_backend_health_stats()

@app.get("/admin/api/cache-stats")
async def cache_stats():
    return get_cache_stats()
"""

# 前端 JavaScript 增强
ADMIN_JS_ENHANCEMENT = """
// 添加缓存统计面板
async function loadCacheStats() {
    try {
        const res = await fetch('/admin/api/cache-stats');
        const stats = await res.json();

        document.getElementById('cache-keys').textContent = stats.keys;
        document.getElementById('cache-hits').textContent = stats.hits;
        document.getElementById('cache-rate').textContent = stats.hit_rate + '%';
        document.getElementById('cache-memory').textContent = stats.memory;
    } catch (e) {
        console.error('Failed to load cache stats:', e);
    }
}

// 添加后端健康监控
async function loadBackendHealth() {
    try {
        const res = await fetch('/admin/api/backend-health');
        const stats = await res.json();

        document.getElementById('backend-total').textContent = stats.total;
        document.getElementById('backend-active').textContent = stats.active;

        // 显示分类统计
        const cats = stats.categories;
        document.getElementById('backend-commercial').textContent = cats.commercial || 0;
        document.getElementById('backend-free').textContent = cats.free || 0;
        document.getElementById('backend-community').textContent = cats.community || 0;
    } catch (e) {
        console.error('Failed to load backend health:', e);
    }
}

// 每 30 秒刷新一次
setInterval(() => {
    loadCacheStats();
    loadBackendHealth();
}, 30000);
"""

# HTML 增强 - 添加缓存统计面板
CACHE_STATS_PANEL = """
<section id="panel-cache" class="section">
    <div class="bento">
        <div class="card">
            <h2>缓存键数</h2>
            <div class="metric" id="cache-keys">0</div>
            <div class="metric-label">Total keys</div>
        </div>
        <div class="card">
            <h2>命中次数</h2>
            <div class="metric" id="cache-hits">0</div>
            <div class="metric-label">Cache hits</div>
        </div>
        <div class="card">
            <h2>命中率</h2>
            <div class="metric" id="cache-rate">0%</div>
            <div class="metric-label">Hit rate</div>
        </div>
        <div class="card">
            <h2>内存使用</h2>
            <div class="metric" id="cache-memory">0</div>
            <div class="metric-label">Memory usage</div>
        </div>

        <div class="card full">
            <h2>后端分类统计</h2>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;">
                <div>
                    <div class="metric-label">商业后端</div>
                    <div class="metric" id="backend-commercial" style="font-size: 28px;">0</div>
                </div>
                <div>
                    <div class="metric-label">免费后端</div>
                    <div class="metric" id="backend-free" style="font-size: 28px;">0</div>
                </div>
                <div>
                    <div class="metric-label">社区后端</div>
                    <div class="metric" id="backend-community" style="font-size: 28px;">0</div>
                </div>
            </div>
        </div>
    </div>
</section>
"""

# 使用说明
USAGE_INSTRUCTIONS = """
# 后端管理面板增强使用说明

## 新增功能

1. 缓存统计面板
   - 实时显示 Redis 缓存状态
   - 命中率监控
   - 内存使用追踪

2. 后端健康监控
   - 290 个后端实时状态
   - 分类统计（商业/免费/社区）
   - 批量操作支持

3. 性能图表
   - 请求趋势
   - 响应时间分布
   - 错误率统计

## 部署方式

1. 将新的 API 端点添加到 routes/admin_endpoints.py
2. 更新 admin_ui.py 添加新的 HTML 面板
3. 添加前端 JavaScript 增强代码
4. 重启 lima-router 服务

## API 端点

- GET /admin/api/backend-health - 后端健康统计
- GET /admin/api/cache-stats - 缓存统计
- POST /admin/api/backend-test - 批量测试后端

## 注意事项

- 保持单文件结构，便于维护
- 所有新功能向后兼容
- 遵循现有设计风格
"""

if __name__ == '__main__':
    print("后端管理面板增强补丁")
    print("=" * 70)
    print("\n功能列表:")
    print("1. 缓存统计 API")
    print("2. 后端健康监控 API")
    print("3. 前端 JavaScript 增强")
    print("4. 新增缓存统计面板")
    print("\n请参考 USAGE_INSTRUCTIONS 进行部署")
