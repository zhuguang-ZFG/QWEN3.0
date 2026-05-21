"""
intent_templates.py — 编程意图增强模板库
匹配用户模糊意图 → 输出精确的增强 prompt，零模型调用成本
"""
import re

TEMPLATES = [
    # (匹配模式, 增强 prompt 模板)
    (r"排序|sort", "实现{detail}排序算法。要求：类型注解，处理空列表和单元素，注释时间复杂度，附带测试"),
    (r"爬虫|scrape|crawl", "爬取{detail}。要求：请求头伪装，限速(1req/s)，异常重试3次，数据存为JSON，处理编码"),
    (r"API|接口|endpoint", "实现{detail} RESTful API。要求：输入验证，错误处理(4xx/5xx)，状态码规范，返回统一JSON格式"),
    (r"数据库|table|schema|建表", "设计{detail}表结构。要求：主键策略，索引，外键约束，软删除字段，created_at/updated_at"),
    (r"登录|认证|auth|login", "实现{detail}认证。要求：密码bcrypt哈希，JWT令牌，刷新机制，CSRF防护，输入验证"),
    (r"正则|regex|匹配", "编写正则表达式匹配{detail}。要求：注释每个部分含义，给出匹配/不匹配示例各3个，附带测试"),
    (r"测试|test|unittest", "为{detail}编写测试。要求：覆盖正常路径+边界+异常，使用pytest，每个test函数名描述行为"),
    (r"重构|refactor", "重构{detail}。要求：保持行为不变，拆分长函数，提取公共逻辑，改善命名，添加类型注解"),
    (r"缓存|cache|redis", "实现{detail}缓存。要求：TTL策略，缓存穿透防护，并发安全，缓存失效处理，监控hit/miss"),
    (r"并发|concurrent|async|异步", "实现{detail}并发处理。要求：线程安全，错误隔离，超时控制，资源清理，进度反馈"),
    (r"文件|读写|read.*file|write.*file", "实现{detail}文件操作。要求：with语句管理资源，编码声明(utf-8)，异常处理，大文件流式读取"),
    (r"日志|log|logging", "实现{detail}日志系统。要求：分级(DEBUG/INFO/WARN/ERROR)，结构化输出，日志轮转，敏感信息脱敏"),
    (r"CLI|命令行|argparse", "实现{detail}CLI工具。要求：argparse参数定义，help文档，子命令支持，错误友好提示，退出码"),
    (r"WebSocket|实时|realtime", "实现{detail} WebSocket。要求：心跳保活，断线重连，消息序列化，并发连接管理，优雅关闭"),
    (r"部署|deploy|Docker", "编写{detail}部署配置。要求：多阶段构建，非root用户，健康检查，环境变量注入，日志到stdout"),
    (r"分页|pagination", "实现{detail}分页。要求：游标分页(非offset)，总数可选，边界检查，空结果处理"),
    (r"上传|upload", "实现{detail}文件上传。要求：大小限制，类型白名单，文件名消毒，存储路径隔离，进度回调"),
    (r"加密|encrypt|hash", "实现{detail}加密。要求：使用标准库(不自造轮子)，安全随机数，密钥管理，时间安全比较"),
    (r"队列|queue|任务|celery", "实现{detail}任务队列。要求：重试策略，死信队列，幂等性，超时控制，结果回调"),
    (r"配置|config|settings", "实现{detail}配置管理。要求：环境变量优先，默认值，类型验证，敏感值不打印，热重载可选"),
]


def match_template(query: str) -> str | None:
    """匹配用户查询到增强模板，返回增强后的 prompt。未匹配返回 None。"""
    for pattern, template in TEMPLATES:
        if re.search(pattern, query, re.I):
            detail = query.strip()
            return template.format(detail=detail)
    return None


def amplify_intent(query: str, messages: list = None) -> str:
    """意图增强：匹配模板或返回原始 query。"""
    enhanced = match_template(query)
    if enhanced:
        return f"{enhanced}\n\n用户原始需求: {query}"
    return query
