"""
Generate synthetic training data for routing model (Qwen3-1.7B).
Routes user queries to the best AI backend with NO system prompt needed.

Output: routing_r14_synthetic.json (HuggingFace SFT trainer compatible)
"""

import json
import random
import os
from typing import List, Dict

random.seed(42)
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "routing_r14_synthetic.json")
TARGET_PER_BACKEND = 260  # ensures 1800+ total across 7 backends


def make_example(query: str, intent: str, complexity: float,
                 backend: str, confidence: float) -> dict:
    """Create a single training example in SFT message format."""
    assistant_json = json.dumps({
        "intent": intent,
        "complexity": round(complexity, 2),
        "backend": backend,
        "confidence": round(confidence, 2)
    }, ensure_ascii=False)
    return {
        "messages": [
            {"role": "user", "content": query},
            {"role": "assistant", "content": assistant_json}
        ]
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SEED DATA PER BACKEND
# Format: (query, intent, complexity, confidence)
# ═══════════════════════════════════════════════════════════════════════════════

LONGCAT_LITE_SEEDS = [
    ("你好", "greeting", 0.05, 0.96),
    ("hi", "greeting", 0.05, 0.97),
    ("hello there", "greeting", 0.05, 0.97),
    ("早上好", "greeting", 0.05, 0.96),
    ("good morning", "greeting", 0.05, 0.96),
    ("晚安", "greeting", 0.05, 0.96),
    ("hey", "greeting", 0.05, 0.95),
    ("谢谢", "greeting", 0.03, 0.96),
    ("再见", "greeting", 0.03, 0.96),
    ("what is GRBL", "simple_qa", 0.15, 0.92),
    ("GRBL是什么", "simple_qa", 0.15, 0.92),
    ("what time is it", "simple_qa", 0.05, 0.97),
    ("现在几点了", "simple_qa", 0.05, 0.97),
    ("1+1等于几", "trivial_math", 0.05, 0.97),
    ("what is 2+2", "trivial_math", 0.05, 0.97),
    ("100除以5等于多少", "trivial_math", 0.1, 0.96),
    ("translate hello to Chinese", "translation", 0.1, 0.95),
    ("把apple翻译成中文", "translation", 0.1, 0.95),
    ("what does CPU stand for", "simple_qa", 0.1, 0.96),
    ("CPU是什么的缩写", "simple_qa", 0.1, 0.96),
    ("who are you", "meta", 0.05, 0.97),
    ("你是谁", "meta", 0.05, 0.97),
    ("what can you do", "meta", 0.08, 0.96),
    ("你能做什么", "meta", 0.08, 0.96),
    ("what is the capital of France", "simple_qa", 0.1, 0.96),
    ("法国的首都是哪里", "simple_qa", 0.1, 0.96),
    ("define photosynthesis", "simple_qa", 0.15, 0.94),
    ("什么是光合作用", "simple_qa", 0.15, 0.94),
    ("how many days in a year", "simple_qa", 0.05, 0.97),
    ("一年有多少天", "simple_qa", 0.05, 0.97),
    ("what color is the sky", "simple_qa", 0.05, 0.97),
    ("天空是什么颜色", "simple_qa", 0.05, 0.97),
    ("summarize this in one sentence", "summary", 0.2, 0.93),
    ("用一句话总结", "summary", 0.2, 0.93),
    ("what is an API", "simple_qa", 0.15, 0.93),
    ("API是什么意思", "simple_qa", 0.15, 0.93),
    ("how tall is Mount Everest", "simple_qa", 0.1, 0.96),
    ("珠穆朗玛峰多高", "simple_qa", 0.1, 0.96),
    ("what is WiFi", "simple_qa", 0.12, 0.95),
    ("WiFi是什么", "simple_qa", 0.12, 0.95),
    ("tell me a joke", "small_talk", 0.1, 0.94),
    ("讲个笑话", "small_talk", 0.1, 0.94),
    ("what is the meaning of life", "small_talk", 0.15, 0.93),
    ("人生的意义是什么", "small_talk", 0.15, 0.93),
    ("how are you", "small_talk", 0.05, 0.96),
    ("你好吗", "small_talk", 0.05, 0.96),
    ("what is HTML", "simple_qa", 0.12, 0.94),
    ("HTML是什么", "simple_qa", 0.12, 0.94),
    ("how old is the earth", "simple_qa", 0.12, 0.95),
    ("地球多少岁了", "simple_qa", 0.12, 0.95),
]

LONGCAT_CHAT_SEEDS = [
    ("帮我写一首关于秋天的诗", "creative_writing", 0.4, 0.95),
    ("write a poem about autumn", "creative_writing", 0.4, 0.95),
    ("帮我写一封辞职信", "email_drafting", 0.45, 0.94),
    ("draft a resignation letter", "email_drafting", 0.45, 0.94),
    ("写一个科幻短篇故事", "storytelling", 0.6, 0.95),
    ("write a short sci-fi story", "storytelling", 0.6, 0.95),
    ("帮我润色这段文字", "polishing", 0.35, 0.94),
    ("polish this paragraph for me", "polishing", 0.35, 0.94),
    ("我想做一个APP，帮我头脑风暴", "brainstorming", 0.5, 0.93),
    ("brainstorm ideas for a mobile app", "brainstorming", 0.5, 0.93),
    ("写一段产品文案", "copywriting", 0.4, 0.95),
    ("write product copy for headphones", "copywriting", 0.4, 0.95),
    ("帮我写一个角色扮演的开场白", "roleplay", 0.35, 0.94),
    ("let's do a roleplay, you are a pirate", "roleplay", 0.35, 0.94),
    ("续写这个故事", "storytelling", 0.5, 0.94),
    ("continue this story", "storytelling", 0.5, 0.94),
    ("write a poem about code", "creative_writing", 0.4, 0.93),
    ("写一首关于代码的诗", "creative_writing", 0.4, 0.93),
    ("帮我写一篇公众号文章", "article_writing", 0.55, 0.94),
    ("write a blog post about productivity", "article_writing", 0.55, 0.94),
    ("给我的猫取个名字", "brainstorming", 0.15, 0.92),
    ("suggest names for my cat", "brainstorming", 0.15, 0.92),
    ("帮我写一段情书", "creative_writing", 0.4, 0.94),
    ("write a love letter", "creative_writing", 0.4, 0.94),
    ("编一个睡前故事", "storytelling", 0.4, 0.95),
    ("tell me a bedtime story", "storytelling", 0.4, 0.95),
    ("帮我改写这段话让它更正式", "polishing", 0.3, 0.94),
    ("rewrite this to sound more formal", "polishing", 0.3, 0.94),
    ("写一段广告词", "copywriting", 0.35, 0.95),
    ("write an ad slogan for coffee", "copywriting", 0.35, 0.95),
    ("帮我写一个演讲稿", "article_writing", 0.55, 0.94),
    ("write a speech for a wedding", "article_writing", 0.55, 0.94),
    ("用幽默的方式描述程序员的一天", "creative_writing", 0.4, 0.93),
    ("describe a programmer's day humorously", "creative_writing", 0.4, 0.93),
    ("帮我写一段自我介绍", "email_drafting", 0.3, 0.93),
    ("write a self-introduction for a job interview", "email_drafting", 0.3, 0.93),
    ("写一首七言绝句", "creative_writing", 0.45, 0.95),
    ("write a haiku about rain", "creative_writing", 0.35, 0.95),
    ("帮我想几个标题", "brainstorming", 0.25, 0.93),
    ("suggest 5 blog post titles", "brainstorming", 0.25, 0.93),
    ("模仿鲁迅的风格写一段话", "creative_writing", 0.5, 0.94),
    ("write in the style of Shakespeare", "creative_writing", 0.5, 0.94),
    ("帮我写一封感谢信", "email_drafting", 0.35, 0.94),
    ("write a thank you email to my boss", "email_drafting", 0.35, 0.94),
    ("创作一个悬疑故事的开头", "storytelling", 0.5, 0.95),
    ("write the opening of a mystery novel", "storytelling", 0.5, 0.95),
]

NVIDIA_QWEN_CODER_SEEDS = [
    ("write a Python function to sort a list", "code_generation", 0.3, 0.96),
    ("写一个Python排序函数", "code_generation", 0.3, 0.96),
    ("explain quicksort", "code_explanation", 0.35, 0.93),
    ("解释快速排序算法", "code_explanation", 0.35, 0.93),
    ("debug this JavaScript code", "debugging", 0.4, 0.95),
    ("帮我调试这段JS代码", "debugging", 0.4, 0.95),
    ("write a REST API in Node.js", "code_generation", 0.5, 0.96),
    ("用Node.js写一个REST API", "code_generation", 0.5, 0.96),
    ("refactor this function to be more efficient", "refactoring", 0.45, 0.95),
    ("重构这个函数提高效率", "refactoring", 0.45, 0.95),
    ("write a Dockerfile for a Python app", "devops", 0.4, 0.95),
    ("写一个Python应用的Dockerfile", "devops", 0.4, 0.95),
    ("how to set up CI/CD with GitHub Actions", "devops", 0.45, 0.94),
    ("如何配置GitHub Actions CI/CD", "devops", 0.45, 0.94),
    ("write a SQL query to join two tables", "sql", 0.3, 0.96),
    ("写一个SQL JOIN查询", "sql", 0.3, 0.96),
    ("write a regex to match email addresses", "regex", 0.35, 0.95),
    ("写一个匹配邮箱的正则表达式", "regex", 0.35, 0.95),
    ("implement binary search in Java", "code_generation", 0.35, 0.96),
    ("用Java实现二分查找", "code_generation", 0.35, 0.96),
    ("write unit tests for this function", "testing", 0.4, 0.95),
    ("给这个函数写单元测试", "testing", 0.4, 0.95),
    ("how to use async/await in Python", "code_explanation", 0.3, 0.94),
    ("Python的async/await怎么用", "code_explanation", 0.3, 0.94),
    ("write a React component for a todo list", "code_generation", 0.4, 0.96),
    ("写一个React的待办事项组件", "code_generation", 0.4, 0.96),
    ("fix this TypeScript type error", "debugging", 0.35, 0.95),
    ("修复这个TypeScript类型错误", "debugging", 0.35, 0.95),
    ("write a bash script to backup files", "code_generation", 0.35, 0.95),
    ("写一个备份文件的bash脚本", "code_generation", 0.35, 0.95),
    ("implement a linked list in C++", "code_generation", 0.4, 0.96),
    ("用C++实现链表", "code_generation", 0.4, 0.96),
    ("write a Go HTTP server", "code_generation", 0.4, 0.96),
    ("用Go写一个HTTP服务器", "code_generation", 0.4, 0.96),
    ("how to use Docker Compose", "devops", 0.35, 0.94),
    ("Docker Compose怎么用", "devops", 0.35, 0.94),
    ("write a Rust function to parse JSON", "code_generation", 0.4, 0.95),
    ("用Rust写一个JSON解析函数", "code_generation", 0.4, 0.95),
    ("optimize this database query", "sql", 0.45, 0.94),
    ("优化这个数据库查询", "sql", 0.45, 0.94),
    ("write a WebSocket server in Python", "code_generation", 0.45, 0.95),
    ("用Python写一个WebSocket服务器", "code_generation", 0.45, 0.95),
    ("implement OAuth2 authentication", "code_generation", 0.55, 0.94),
    ("实现OAuth2认证", "code_generation", 0.55, 0.94),
    ("write a Kubernetes deployment YAML", "devops", 0.4, 0.95),
    ("写一个Kubernetes部署配置", "devops", 0.4, 0.95),
    ("code review this pull request", "code_review", 0.45, 0.94),
    ("帮我review这个PR", "code_review", 0.45, 0.94),
]

DEEPSEEK_PRO_SEEDS = [
    ("prove that sqrt(2) is irrational", "math_proof", 0.8, 0.95),
    ("证明根号2是无理数", "math_proof", 0.8, 0.95),
    ("solve this differential equation", "calculus", 0.75, 0.94),
    ("求解这个微分方程", "calculus", 0.75, 0.94),
    ("analyze the time complexity of this algorithm", "complexity_analysis", 0.7, 0.93),
    ("分析这个算法的时间复杂度", "complexity_analysis", 0.7, 0.93),
    ("explain the P vs NP problem", "theoretical_cs", 0.8, 0.94),
    ("解释P与NP问题", "theoretical_cs", 0.8, 0.94),
    ("derive the eigenvalues of this matrix", "linear_algebra", 0.7, 0.95),
    ("求这个矩阵的特征值", "linear_algebra", 0.7, 0.95),
    ("prove by induction that sum of 1 to n is n(n+1)/2", "math_proof", 0.6, 0.95),
    ("用数学归纳法证明1到n的和等于n(n+1)/2", "math_proof", 0.6, 0.95),
    ("analyze algorithm complexity of merge sort vs quicksort", "complexity_analysis", 0.65, 0.93),
    ("比较归并排序和快速排序的复杂度", "complexity_analysis", 0.65, 0.93),
    ("write a formal proof for the halting problem", "theoretical_cs", 0.85, 0.94),
    ("写停机问题的形式化证明", "theoretical_cs", 0.85, 0.94),
    ("solve this triple integral", "calculus", 0.8, 0.94),
    ("求解这个三重积分", "calculus", 0.8, 0.94),
    ("explain Godel's incompleteness theorem", "theoretical_cs", 0.85, 0.94),
    ("解释哥德尔不完备定理", "theoretical_cs", 0.85, 0.94),
    ("prove the fundamental theorem of calculus", "math_proof", 0.75, 0.95),
    ("证明微积分基本定理", "math_proof", 0.75, 0.95),
    ("analyze the convergence of this series", "calculus", 0.65, 0.94),
    ("分析这个级数的收敛性", "calculus", 0.65, 0.94),
    ("explain lambda calculus and Church encoding", "theoretical_cs", 0.8, 0.93),
    ("解释lambda演算和Church编码", "theoretical_cs", 0.8, 0.93),
    ("solve this system of linear equations using Gaussian elimination", "linear_algebra", 0.6, 0.95),
    ("用高斯消元法解这个线性方程组", "linear_algebra", 0.6, 0.95),
    ("prove the Cauchy-Schwarz inequality", "math_proof", 0.75, 0.95),
    ("证明柯西-施瓦茨不等式", "math_proof", 0.75, 0.95),
    ("analyze the computational complexity of graph coloring", "complexity_analysis", 0.75, 0.93),
    ("分析图着色问题的计算复杂度", "complexity_analysis", 0.75, 0.93),
    ("explain the proof of Fermat's last theorem", "math_proof", 0.9, 0.93),
    ("解释费马大定理的证明", "math_proof", 0.9, 0.93),
    ("derive the Fourier transform of a Gaussian", "calculus", 0.7, 0.94),
    ("推导高斯函数的傅里叶变换", "calculus", 0.7, 0.94),
    ("prove that there are infinitely many primes", "math_proof", 0.6, 0.96),
    ("证明素数有无穷多个", "math_proof", 0.6, 0.96),
    ("explain the relationship between category theory and type theory", "theoretical_cs", 0.85, 0.92),
    ("解释范畴论和类型论的关系", "theoretical_cs", 0.85, 0.92),
    ("analyze space complexity of dynamic programming solutions", "complexity_analysis", 0.65, 0.93),
    ("分析动态规划解法的空间复杂度", "complexity_analysis", 0.65, 0.93),
    ("write a research paper outline on transformer architectures", "research", 0.7, 0.92),
    ("写一篇关于Transformer架构的研究论文大纲", "research", 0.7, 0.92),
]

LONGCAT_THINKING_SEEDS = [
    ("plan a migration from monolith to microservices", "planning", 0.7, 0.94),
    ("规划从单体架构迁移到微服务", "planning", 0.7, 0.94),
    ("design a system for handling 10M concurrent users", "system_design", 0.8, 0.94),
    ("设计一个支持1000万并发用户的系统", "system_design", 0.8, 0.94),
    ("compare React vs Vue for our project", "decision_analysis", 0.5, 0.93),
    ("比较React和Vue哪个更适合我们的项目", "decision_analysis", 0.5, 0.93),
    ("what are the tradeoffs of using NoSQL vs SQL", "tradeoff_analysis", 0.55, 0.93),
    ("NoSQL和SQL的权衡是什么", "tradeoff_analysis", 0.55, 0.93),
    ("design the architecture for a chat application", "system_design", 0.65, 0.94),
    ("设计一个聊天应用的架构", "system_design", 0.65, 0.94),
    ("prioritize these 10 features for the next sprint", "prioritization", 0.5, 0.93),
    ("帮我排列这10个功能的优先级", "prioritization", 0.5, 0.93),
    ("plan a database migration strategy with zero downtime", "planning", 0.7, 0.94),
    ("规划一个零停机的数据库迁移策略", "planning", 0.7, 0.94),
    ("analyze the pros and cons of serverless architecture", "tradeoff_analysis", 0.6, 0.93),
    ("分析无服务器架构的优缺点", "tradeoff_analysis", 0.6, 0.93),
    ("design a caching strategy for our e-commerce site", "system_design", 0.6, 0.94),
    ("为电商网站设计缓存策略", "system_design", 0.6, 0.94),
    ("how should we structure our team for this project", "strategy", 0.5, 0.92),
    ("这个项目应该怎么组织团队", "strategy", 0.5, 0.92),
    ("plan the rollout of a new payment system", "planning", 0.65, 0.94),
    ("规划新支付系统的上线方案", "planning", 0.65, 0.94),
    ("design an event-driven architecture for order processing", "system_design", 0.7, 0.94),
    ("设计一个事件驱动的订单处理架构", "system_design", 0.7, 0.94),
    ("evaluate build vs buy for our auth system", "decision_analysis", 0.55, 0.93),
    ("评估认证系统是自建还是购买", "decision_analysis", 0.55, 0.93),
    ("plan a gradual TypeScript migration", "planning", 0.55, 0.94),
    ("规划渐进式TypeScript迁移", "planning", 0.55, 0.94),
    ("design a multi-tenant SaaS architecture", "system_design", 0.75, 0.94),
    ("设计一个多租户SaaS架构", "system_design", 0.75, 0.94),
    ("what's the best strategy for API versioning", "strategy", 0.5, 0.93),
    ("API版本管理的最佳策略是什么", "strategy", 0.5, 0.93),
    ("plan a disaster recovery strategy", "planning", 0.65, 0.93),
    ("规划灾难恢复策略", "planning", 0.65, 0.93),
    ("design a notification system that scales", "system_design", 0.65, 0.94),
    ("设计一个可扩展的通知系统", "system_design", 0.65, 0.94),
    ("analyze technical debt and create a payoff plan", "strategy", 0.6, 0.92),
    ("分析技术债务并制定偿还计划", "strategy", 0.6, 0.92),
    ("step by step, how should I approach this refactoring", "planning", 0.5, 0.93),
    ("一步步分析，我应该怎么重构这个模块", "planning", 0.5, 0.93),
]

LONGCAT_OMNI_SEEDS = [
    ("describe this image", "image_understanding", 0.3, 0.96),
    ("描述这张图片", "image_understanding", 0.3, 0.96),
    ("what's in this photo", "image_understanding", 0.3, 0.96),
    ("这张照片里有什么", "image_understanding", 0.3, 0.96),
    ("read the text in this screenshot", "ocr", 0.35, 0.96),
    ("识别这个截图中的文字", "ocr", 0.35, 0.96),
    ("analyze this diagram", "diagram_analysis", 0.45, 0.95),
    ("分析这个图表", "diagram_analysis", 0.45, 0.95),
    ("what does this error screenshot show", "image_understanding", 0.35, 0.96),
    ("这个错误截图显示了什么", "image_understanding", 0.35, 0.96),
    ("explain this architecture diagram", "diagram_analysis", 0.5, 0.95),
    ("解释这个架构图", "diagram_analysis", 0.5, 0.95),
    ("OCR this receipt", "ocr", 0.3, 0.96),
    ("识别这张收据上的内容", "ocr", 0.3, 0.96),
    ("what color is the object in this image", "image_understanding", 0.25, 0.96),
    ("图片中的物体是什么颜色", "image_understanding", 0.25, 0.96),
    ("compare these two screenshots", "image_understanding", 0.4, 0.95),
    ("对比这两张截图", "image_understanding", 0.4, 0.95),
    ("extract data from this chart image", "diagram_analysis", 0.5, 0.95),
    ("从这个图表图片中提取数据", "diagram_analysis", 0.5, 0.95),
    ("is there a bug visible in this UI screenshot", "image_understanding", 0.4, 0.95),
    ("这个UI截图中有bug吗", "image_understanding", 0.4, 0.95),
    ("read the handwriting in this picture", "ocr", 0.4, 0.94),
    ("识别这张图片中的手写文字", "ocr", 0.4, 0.94),
    ("what font is used in this image", "image_understanding", 0.3, 0.94),
    ("这张图片用的什么字体", "image_understanding", 0.3, 0.94),
    ("analyze the UML diagram", "diagram_analysis", 0.5, 0.95),
    ("分析这个UML图", "diagram_analysis", 0.5, 0.95),
    ("look at this picture and tell me what's wrong", "image_understanding", 0.35, 0.96),
    ("看看这张图片告诉我哪里有问题", "image_understanding", 0.35, 0.96),
    ("transcribe the whiteboard in this photo", "ocr", 0.4, 0.95),
    ("把这张照片里白板上的内容转录下来", "ocr", 0.4, 0.95),
    ("what does this flowchart describe", "diagram_analysis", 0.45, 0.95),
    ("这个流程图描述了什么", "diagram_analysis", 0.45, 0.95),
    ("identify the plants in this garden photo", "image_understanding", 0.35, 0.93),
    ("识别这张花园照片中的植物", "image_understanding", 0.35, 0.93),
    ("convert this wireframe image to HTML", "image_understanding", 0.6, 0.94),
    ("把这个线框图转换成HTML", "image_understanding", 0.6, 0.94),
    ("看图说话", "image_understanding", 0.25, 0.96),
    ("describe what you see", "image_understanding", 0.25, 0.96),
]

CHINAMOBILE_DEEPSEEK_SEEDS = [
    ("唐朝有哪些著名诗人", "chinese_history", 0.3, 0.95),
    ("解释成语'画蛇添足'的含义", "chinese_idiom", 0.25, 0.96),
    ("中国四大发明是什么", "chinese_culture", 0.2, 0.96),
    ("翻译这段文言文", "classical_chinese", 0.5, 0.95),
    ("高考数学有哪些常考题型", "exam_prep", 0.4, 0.94),
    ("中医里的阴阳五行是什么意思", "traditional_medicine", 0.4, 0.94),
    ("长江和黄河哪个更长", "chinese_geography", 0.15, 0.96),
    ("解释《论语》中'学而时习之'的含义", "classical_chinese", 0.4, 0.95),
    ("中国有多少个省份", "chinese_geography", 0.1, 0.97),
    ("什么是二十四节气", "chinese_culture", 0.3, 0.95),
    ("explain the Chinese civil service examination system", "chinese_history", 0.45, 0.94),
    ("科举制度是怎么回事", "chinese_history", 0.35, 0.95),
    ("红楼梦的主要人物有哪些", "chinese_literature", 0.35, 0.95),
    ("summarize Dream of the Red Chamber", "chinese_literature", 0.4, 0.94),
    ("中考英语作文怎么拿高分", "exam_prep", 0.4, 0.93),
    ("how to prepare for Gaokao math", "exam_prep", 0.4, 0.93),
    ("解释'天人合一'的哲学思想", "chinese_culture", 0.5, 0.94),
    ("what is the philosophy of Tian Ren He Yi", "chinese_culture", 0.5, 0.93),
    ("中药里的君臣佐使是什么", "traditional_medicine", 0.45, 0.94),
    ("explain the four natures in TCM", "traditional_medicine", 0.45, 0.93),
    ("丝绸之路的历史意义", "chinese_history", 0.4, 0.95),
    ("what was the significance of the Silk Road", "chinese_history", 0.4, 0.94),
    ("解释对联的平仄规则", "chinese_literature", 0.4, 0.95),
    ("how do tonal patterns work in Chinese couplets", "chinese_literature", 0.4, 0.93),
    ("中国各省的省会是什么", "chinese_geography", 0.2, 0.96),
    ("list all provincial capitals of China", "chinese_geography", 0.2, 0.95),
    ("春秋战国时期有哪些重要思想家", "chinese_history", 0.4, 0.95),
    ("who were the key philosophers during Spring and Autumn period", "chinese_history", 0.4, 0.93),
    ("初中物理力学知识点总结", "exam_prep", 0.4, 0.94),
    ("summarize middle school physics mechanics", "exam_prep", 0.4, 0.93),
    ("什么是针灸", "traditional_medicine", 0.3, 0.95),
    ("explain acupuncture in TCM", "traditional_medicine", 0.3, 0.94),
    ("李白的代表作有哪些", "chinese_literature", 0.25, 0.96),
    ("what are Li Bai's most famous poems", "chinese_literature", 0.25, 0.95),
    ("解释'知行合一'", "chinese_culture", 0.35, 0.95),
    ("explain Wang Yangming's unity of knowledge and action", "chinese_culture", 0.4, 0.93),
    ("中国的五岳是哪五座山", "chinese_geography", 0.15, 0.96),
    ("what are the Five Great Mountains of China", "chinese_geography", 0.15, 0.95),
    ("高中语文文言文翻译技巧", "exam_prep", 0.4, 0.94),
    ("tips for classical Chinese translation in high school", "exam_prep", 0.4, 0.93),
]


# ═══════════════════════════════════════════════════════════════════════════════
# AUGMENTATION TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

LITE_TEMPLATES_EN = [
    "what is {topic}",
    "define {topic}",
    "tell me about {topic}",
    "what does {topic} mean",
    "how do you say {topic} in Chinese",
    "translate {topic} to English",
    "who invented {topic}",
    "when was {topic} invented",
    "is {topic} true",
    "what's the difference between {a} and {b}",
]

LITE_TEMPLATES_ZH = [
    "{topic}是什么",
    "解释一下{topic}",
    "{topic}是什么意思",
    "把{topic}翻译成英文",
    "{topic}怎么读",
    "{topic}和{b}有什么区别",
    "简单介绍一下{topic}",
    "{topic}的定义是什么",
]

LITE_TOPICS = [
    ("WiFi", "Bluetooth"), ("HTTP", "HTTPS"), ("RAM", "ROM"),
    ("LED", "LCD"), ("USB", "HDMI"), ("GPS", "GLONASS"),
    ("AI", "ML"), ("SSD", "HDD"), ("LAN", "WAN"),
    ("PDF", "DOC"), ("JPG", "PNG"), ("MP3", "WAV"),
    ("DNA", "RNA"), ("AC", "DC"), ("AM", "FM"),
    ("IoT", "5G"), ("VPN", "proxy"), ("TCP", "UDP"),
]

CHAT_TEMPLATES_EN = [
    "write a poem about {topic}",
    "write a short story about {topic}",
    "brainstorm ideas for {topic}",
    "draft an email about {topic}",
    "write ad copy for {topic}",
    "rewrite this to be more {style}",
    "write a {genre} story opening",
    "create a dialogue between {a} and {b}",
    "write a song about {topic}",
    "come up with slogans for {topic}",
]

CHAT_TEMPLATES_ZH = [
    "写一首关于{topic}的诗",
    "写一个关于{topic}的短故事",
    "帮我头脑风暴{topic}的创意",
    "写一封关于{topic}的邮件",
    "为{topic}写一段广告文案",
    "把这段话改写得更{style}",
    "写一个{genre}故事的开头",
    "创作{a}和{b}之间的对话",
    "写一首关于{topic}的歌词",
    "为{topic}想几个口号",
]

CHAT_TOPICS = [
    "spring", "coffee", "friendship", "travel", "music",
    "rain", "sunset", "dreams", "technology", "nature",
    "love", "space", "ocean", "mountains", "childhood",
]
CHAT_STYLES = ["formal", "casual", "humorous", "poetic", "concise"]
CHAT_GENRES = ["mystery", "romance", "horror", "comedy", "sci-fi"]

CODER_TEMPLATES_EN = [
    "write a {lang} function to {task}",
    "implement {algo} in {lang}",
    "debug this {lang} code",
    "refactor this {lang} function",
    "write tests for {task} in {lang}",
    "how to {task} in {lang}",
    "create a {lang} class for {task}",
    "write a {tool} config for {task}",
    "optimize this {lang} code for performance",
    "convert this code from {lang} to {lang2}",
]

CODER_TEMPLATES_ZH = [
    "用{lang}写一个{task}的函数",
    "用{lang}实现{algo}",
    "帮我调试这段{lang}代码",
    "重构这个{lang}函数",
    "给{task}写{lang}单元测试",
    "{lang}里怎么{task}",
    "写一个{lang}的{task}类",
    "写一个{tool}的配置文件",
    "优化这段{lang}代码的性能",
    "把这段代码从{lang}转换成{lang2}",
]

CODER_LANGS = ["Python", "JavaScript", "TypeScript", "Go", "Rust", "Java", "C++", "C#"]
CODER_ALGOS = ["binary search", "BFS", "DFS", "dynamic programming", "hash map", "trie", "heap sort"]
CODER_TASKS = [
    "parse CSV", "validate email", "connect to database", "handle file upload",
    "implement caching", "send HTTP request", "parse JSON", "create REST endpoint",
    "handle authentication", "manage state", "process queue", "read config",
]
CODER_TOOLS = ["Docker", "Kubernetes", "Terraform", "Nginx", "GitHub Actions", "Jenkins"]

DEEPSEEK_TEMPLATES_EN = [
    "prove that {statement}",
    "derive the {formula} for {topic}",
    "analyze the complexity of {algo}",
    "solve this {math_type} problem: {problem}",
    "explain the proof of {theorem}",
    "what is the formal definition of {concept}",
    "compare the theoretical bounds of {a} vs {b}",
    "write a rigorous proof for {statement}",
]

DEEPSEEK_TEMPLATES_ZH = [
    "证明{statement}",
    "推导{topic}的{formula}",
    "分析{algo}的复杂度",
    "求解这个{math_type}问题：{problem}",
    "解释{theorem}的证明",
    "{concept}的形式化定义是什么",
    "比较{a}和{b}的理论界",
    "写一个严格的{statement}证明",
]

DEEPSEEK_STATEMENTS = [
    "every continuous function on [0,1] is bounded",
    "the set of rationals is countable",
    "every finite group of prime order is cyclic",
    "the sum of angles in a triangle is 180 degrees",
    "e is transcendental",
]
DEEPSEEK_THEOREMS = [
    "Bayes' theorem", "Central Limit Theorem", "Pythagorean theorem",
    "Bolzano-Weierstrass theorem", "Cantor's diagonal argument",
]
DEEPSEEK_MATH_TYPES = ["optimization", "probability", "combinatorics", "topology", "number theory"]

THINKING_TEMPLATES_EN = [
    "design a system for {task}",
    "plan a migration from {a} to {b}",
    "what are the tradeoffs of {approach}",
    "how should I architect {system}",
    "prioritize these features: {features}",
    "create a rollout plan for {task}",
    "analyze the risks of {approach}",
    "step by step, how to {task}",
    "evaluate {a} vs {b} for {context}",
    "design a scalable {system}",
]

THINKING_TEMPLATES_ZH = [
    "设计一个{task}的系统",
    "规划从{a}迁移到{b}",
    "{approach}的权衡是什么",
    "应该怎么架构{system}",
    "排列这些功能的优先级：{features}",
    "制定{task}的上线计划",
    "分析{approach}的风险",
    "一步步分析怎么{task}",
    "评估{a}和{b}在{context}中的优劣",
    "设计一个可扩展的{system}",
]

THINKING_SYSTEMS = [
    "notification service", "payment gateway", "search engine",
    "recommendation engine", "logging pipeline", "auth system",
    "message queue", "rate limiter", "load balancer",
]
THINKING_APPROACHES = [
    "microservices", "event sourcing", "CQRS", "serverless",
    "monorepo", "polyrepo", "GraphQL", "gRPC",
]

OMNI_TEMPLATES = [
    "what's in this image",
    "describe this picture",
    "analyze this screenshot",
    "read the text in this photo",
    "what does this diagram show",
    "OCR this document image",
    "compare these two images",
    "identify objects in this photo",
    "explain this chart",
    "这张图片里有什么",
    "描述这张照片",
    "分析这个截图",
    "识别这张图片中的文字",
    "这个图表说明了什么",
    "对比这两张图",
    "识别图中的物体",
    "解释这个图表",
    "看看这张图有什么问题",
    "把图片中的文字提取出来",
]

CHINA_TEMPLATES_ZH = [
    "解释成语'{idiom}'",
    "{dynasty}朝有哪些重要事件",
    "{subject}的考试重点是什么",
    "中医里{concept}是什么意思",
    "{author}的代表作有哪些",
    "{place}在中国哪个省",
    "翻译这段古文：{text}",
    "{topic}的历史背景是什么",
]

CHINA_TEMPLATES_EN = [
    "explain the Chinese idiom '{idiom}'",
    "what happened during the {dynasty} dynasty",
    "how to prepare for {subject} exam in China",
    "what is {concept} in traditional Chinese medicine",
    "who is {author} in Chinese literature",
    "where is {place} located in China",
    "translate this classical Chinese text",
    "what is the historical context of {topic}",
]

CHINA_IDIOMS = [
    "守株待兔", "亡羊补牢", "掩耳盗铃", "刻舟求剑", "杯弓蛇影",
    "对牛弹琴", "画龙点睛", "井底之蛙", "狐假虎威", "塞翁失马",
    "卧薪尝胆", "破釜沉舟", "纸上谈兵", "班门弄斧", "叶公好龙",
]
CHINA_DYNASTIES = ["唐", "宋", "明", "清", "汉", "秦", "元", "隋"]
CHINA_SUBJECTS = ["语文", "数学", "英语", "物理", "化学", "历史", "地理", "生物"]
CHINA_AUTHORS = ["李白", "杜甫", "苏轼", "曹雪芹", "鲁迅", "老舍", "巴金", "莫言"]
CHINA_PLACES = ["敦煌", "西安", "洛阳", "成都", "杭州", "苏州", "桂林", "丽江"]


# ═══════════════════════════════════════════════════════════════════════════════
# GENERATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def generate_lite_augmented() -> List[dict]:
    """Generate augmented longcat_lite examples from templates."""
    examples = []
    for topic_pair in LITE_TOPICS:
        a, b = topic_pair
        for tmpl in LITE_TEMPLATES_EN:
            q = tmpl.format(topic=a, a=a, b=b)
            complexity = round(random.uniform(0.08, 0.2), 2)
            conf = round(random.uniform(0.91, 0.97), 2)
            examples.append(make_example(q, "simple_qa", complexity, "longcat_lite", conf))
        for tmpl in LITE_TEMPLATES_ZH[:4]:
            q = tmpl.format(topic=a, b=b)
            complexity = round(random.uniform(0.08, 0.2), 2)
            conf = round(random.uniform(0.91, 0.97), 2)
            examples.append(make_example(q, "simple_qa", complexity, "longcat_lite", conf))
    return examples


def generate_chat_augmented() -> List[dict]:
    """Generate augmented longcat_chat examples from templates."""
    examples = []
    for topic in CHAT_TOPICS:
        style = random.choice(CHAT_STYLES)
        genre = random.choice(CHAT_GENRES)
        a_char, b_char = "Alice", "Bob"
        for tmpl in CHAT_TEMPLATES_EN:
            q = tmpl.format(topic=topic, style=style, genre=genre, a=a_char, b=b_char)
            complexity = round(random.uniform(0.3, 0.6), 2)
            conf = round(random.uniform(0.90, 0.96), 2)
            intent = random.choice(["creative_writing", "brainstorming", "storytelling", "copywriting"])
            examples.append(make_example(q, intent, complexity, "longcat_chat", conf))
        for tmpl in CHAT_TEMPLATES_ZH:
            q = tmpl.format(topic=topic, style=style, genre=genre, a=a_char, b=b_char)
            complexity = round(random.uniform(0.3, 0.6), 2)
            conf = round(random.uniform(0.90, 0.96), 2)
            intent = random.choice(["creative_writing", "brainstorming", "storytelling", "copywriting"])
            examples.append(make_example(q, intent, complexity, "longcat_chat", conf))
    return examples


def generate_coder_augmented() -> List[dict]:
    """Generate augmented nvidia_qwen_coder examples from templates."""
    examples = []
    for lang in CODER_LANGS:
        lang2 = random.choice([l for l in CODER_LANGS if l != lang])
        algo = random.choice(CODER_ALGOS)
        task = random.choice(CODER_TASKS)
        tool = random.choice(CODER_TOOLS)
        for tmpl in CODER_TEMPLATES_EN:
            q = tmpl.format(lang=lang, lang2=lang2, algo=algo, task=task, tool=tool)
            complexity = round(random.uniform(0.3, 0.6), 2)
            conf = round(random.uniform(0.92, 0.97), 2)
            intent = random.choice(["code_generation", "debugging", "refactoring", "devops", "testing"])
            examples.append(make_example(q, intent, complexity, "nvidia_qwen_coder", conf))
        for tmpl in CODER_TEMPLATES_ZH:
            q = tmpl.format(lang=lang, lang2=lang2, algo=algo, task=task, tool=tool)
            complexity = round(random.uniform(0.3, 0.6), 2)
            conf = round(random.uniform(0.92, 0.97), 2)
            intent = random.choice(["code_generation", "debugging", "refactoring", "devops", "testing"])
            examples.append(make_example(q, intent, complexity, "nvidia_qwen_coder", conf))
    return examples


def generate_deepseek_augmented() -> List[dict]:
    """Generate augmented deepseek_pro examples from templates."""
    examples = []
    for stmt in DEEPSEEK_STATEMENTS:
        for tmpl in DEEPSEEK_TEMPLATES_EN[:3]:
            q = tmpl.format(
                statement=stmt, formula="closed form", topic="series",
                algo=random.choice(CODER_ALGOS), math_type=random.choice(DEEPSEEK_MATH_TYPES),
                problem=stmt, theorem=random.choice(DEEPSEEK_THEOREMS),
                concept="continuity", a="BFS", b="DFS"
            )
            complexity = round(random.uniform(0.6, 0.9), 2)
            conf = round(random.uniform(0.90, 0.96), 2)
            intent = random.choice(["math_proof", "complexity_analysis", "calculus", "theoretical_cs"])
            examples.append(make_example(q, intent, complexity, "deepseek_pro", conf))
        for tmpl in DEEPSEEK_TEMPLATES_ZH[:3]:
            q = tmpl.format(
                statement=stmt, formula="通项公式", topic="级数",
                algo=random.choice(CODER_ALGOS), math_type=random.choice(DEEPSEEK_MATH_TYPES),
                problem=stmt, theorem=random.choice(DEEPSEEK_THEOREMS),
                concept="连续性", a="BFS", b="DFS"
            )
            complexity = round(random.uniform(0.6, 0.9), 2)
            conf = round(random.uniform(0.90, 0.96), 2)
            intent = random.choice(["math_proof", "complexity_analysis", "calculus", "theoretical_cs"])
            examples.append(make_example(q, intent, complexity, "deepseek_pro", conf))
    # Additional from theorems
    for thm in DEEPSEEK_THEOREMS:
        q_en = f"explain the proof of {thm}"
        q_zh = f"解释{thm}的证明"
        examples.append(make_example(q_en, "math_proof", 0.75, "deepseek_pro", 0.94))
        examples.append(make_example(q_zh, "math_proof", 0.75, "deepseek_pro", 0.94))
    return examples


def generate_thinking_augmented() -> List[dict]:
    """Generate augmented longcat_thinking examples from templates."""
    examples = []
    for system in THINKING_SYSTEMS:
        approach = random.choice(THINKING_APPROACHES)
        a, b = random.sample(THINKING_APPROACHES, 2)
        features = ", ".join(random.sample(THINKING_SYSTEMS, 3))
        for tmpl in THINKING_TEMPLATES_EN:
            q = tmpl.format(
                task=system, system=system, approach=approach,
                a=a, b=b, features=features, context="our startup"
            )
            complexity = round(random.uniform(0.5, 0.8), 2)
            conf = round(random.uniform(0.90, 0.95), 2)
            intent = random.choice(["planning", "system_design", "tradeoff_analysis", "strategy"])
            examples.append(make_example(q, intent, complexity, "longcat_thinking", conf))
        for tmpl in THINKING_TEMPLATES_ZH:
            q = tmpl.format(
                task=system, system=system, approach=approach,
                a=a, b=b, features=features, context="我们的创业公司"
            )
            complexity = round(random.uniform(0.5, 0.8), 2)
            conf = round(random.uniform(0.90, 0.95), 2)
            intent = random.choice(["planning", "system_design", "tradeoff_analysis", "strategy"])
            examples.append(make_example(q, intent, complexity, "longcat_thinking", conf))
    return examples


def generate_omni_augmented() -> List[dict]:
    """Generate augmented longcat_omni examples."""
    examples = []
    contexts = [
        "of my code", "of the error", "of this UI design", "I just took",
        "from the meeting", "of the whiteboard", "of this chart",
        "of the receipt", "of this document", "of my screen",
    ]
    for tmpl in OMNI_TEMPLATES:
        for ctx in contexts[:5]:
            q = f"{tmpl} {ctx}" if "image" in tmpl or "图" in tmpl else tmpl
            complexity = round(random.uniform(0.25, 0.5), 2)
            conf = round(random.uniform(0.93, 0.97), 2)
            intent = random.choice(["image_understanding", "ocr", "diagram_analysis"])
            examples.append(make_example(q, intent, complexity, "longcat_omni", conf))
    return examples


def generate_china_augmented() -> List[dict]:
    """Generate augmented chinamobile_deepseek examples."""
    examples = []
    for idiom in CHINA_IDIOMS:
        q_zh = f"解释成语'{idiom}'的含义和典故"
        q_en = f"explain the Chinese idiom '{idiom}'"
        examples.append(make_example(q_zh, "chinese_idiom", 0.3, "chinamobile_deepseek", 0.96))
        examples.append(make_example(q_en, "chinese_idiom", 0.35, "chinamobile_deepseek", 0.94))
    for dynasty in CHINA_DYNASTIES:
        q_zh = f"{dynasty}朝有哪些重要历史事件"
        q_en = f"what were the key events of the {dynasty} dynasty"
        examples.append(make_example(q_zh, "chinese_history", 0.4, "chinamobile_deepseek", 0.95))
        examples.append(make_example(q_en, "chinese_history", 0.4, "chinamobile_deepseek", 0.93))
    for subject in CHINA_SUBJECTS:
        q = f"{subject}考试有哪些常考题型和技巧"
        examples.append(make_example(q, "exam_prep", 0.4, "chinamobile_deepseek", 0.94))
    for author in CHINA_AUTHORS:
        q_zh = f"{author}的生平和代表作品"
        q_en = f"tell me about {author}'s life and major works"
        examples.append(make_example(q_zh, "chinese_literature", 0.35, "chinamobile_deepseek", 0.95))
        examples.append(make_example(q_en, "chinese_literature", 0.4, "chinamobile_deepseek", 0.93))
    for place in CHINA_PLACES:
        q = f"{place}有什么著名的历史文化景点"
        examples.append(make_example(q, "chinese_geography", 0.3, "chinamobile_deepseek", 0.95))
    return examples


# ═══════════════════════════════════════════════════════════════════════════════
# HARD BOUNDARY CASES (critical for correct routing)
# ═══════════════════════════════════════════════════════════════════════════════

BOUNDARY_CASES = [
    # Code topics → nvidia_qwen_coder, NOT longcat_lite
    make_example("explain quicksort", "code_explanation", 0.35, "nvidia_qwen_coder", 0.93),
    make_example("what is a binary tree", "code_explanation", 0.25, "nvidia_qwen_coder", 0.91),
    make_example("how does garbage collection work", "code_explanation", 0.35, "nvidia_qwen_coder", 0.92),
    make_example("explain recursion", "code_explanation", 0.3, "nvidia_qwen_coder", 0.92),
    make_example("what is a hash table", "code_explanation", 0.25, "nvidia_qwen_coder", 0.91),
    make_example("how does TCP handshake work", "code_explanation", 0.35, "nvidia_qwen_coder", 0.91),
    make_example("explain MVC pattern", "code_explanation", 0.3, "nvidia_qwen_coder", 0.92),
    make_example("what is dependency injection", "code_explanation", 0.3, "nvidia_qwen_coder", 0.91),
    make_example("解释快速排序", "code_explanation", 0.35, "nvidia_qwen_coder", 0.93),
    make_example("什么是二叉树", "code_explanation", 0.25, "nvidia_qwen_coder", 0.91),
    make_example("递归是什么", "code_explanation", 0.3, "nvidia_qwen_coder", 0.92),
    make_example("哈希表怎么工作的", "code_explanation", 0.3, "nvidia_qwen_coder", 0.91),

    # Simple Q&A → longcat_lite, NOT chinamobile_deepseek
    make_example("what is GRBL", "simple_qa", 0.15, "longcat_lite", 0.92),
    make_example("GRBL是什么", "simple_qa", 0.15, "longcat_lite", 0.92),
    make_example("what is Linux", "simple_qa", 0.12, "longcat_lite", 0.94),
    make_example("what is an API", "simple_qa", 0.15, "longcat_lite", 0.93),
    make_example("what is machine learning", "simple_qa", 0.18, "longcat_lite", 0.92),
    make_example("什么是机器学习", "simple_qa", 0.18, "longcat_lite", 0.92),
    make_example("what is blockchain", "simple_qa", 0.15, "longcat_lite", 0.93),
    make_example("区块链是什么", "simple_qa", 0.15, "longcat_lite", 0.93),

    # Creative writing → longcat_chat, NOT nvidia_qwen_coder
    make_example("write a poem about code", "creative_writing", 0.4, "longcat_chat", 0.93),
    make_example("写一首关于代码的诗", "creative_writing", 0.4, "longcat_chat", 0.93),
    make_example("write a story about a programmer", "storytelling", 0.5, "longcat_chat", 0.93),
    make_example("写一个程序员的故事", "storytelling", 0.5, "longcat_chat", 0.93),
    make_example("write a haiku about debugging", "creative_writing", 0.35, "longcat_chat", 0.92),
    make_example("用诗意的语言描述算法", "creative_writing", 0.4, "longcat_chat", 0.92),

    # Reasoning/analysis → deepseek_pro, NOT nvidia_qwen_coder
    make_example("analyze algorithm complexity", "complexity_analysis", 0.65, "deepseek_pro", 0.93),
    make_example("分析算法复杂度", "complexity_analysis", 0.65, "deepseek_pro", 0.93),
    make_example("prove this algorithm is correct", "math_proof", 0.7, "deepseek_pro", 0.93),
    make_example("证明这个算法的正确性", "math_proof", 0.7, "deepseek_pro", 0.93),
    make_example("what is the lower bound for comparison sorting", "theoretical_cs", 0.7, "deepseek_pro", 0.92),
    make_example("比较排序的下界是什么", "theoretical_cs", 0.7, "deepseek_pro", 0.92),

    # Planning → longcat_thinking, NOT nvidia_qwen_coder
    make_example("plan a migration from MySQL to PostgreSQL", "planning", 0.6, "longcat_thinking", 0.94),
    make_example("规划从MySQL迁移到PostgreSQL", "planning", 0.6, "longcat_thinking", 0.94),
    make_example("design the architecture for our new app", "system_design", 0.7, "longcat_thinking", 0.94),
    make_example("设计我们新应用的架构", "system_design", 0.7, "longcat_thinking", 0.94),
    make_example("should we use Kafka or RabbitMQ", "decision_analysis", 0.5, "longcat_thinking", 0.93),
    make_example("我们应该用Kafka还是RabbitMQ", "decision_analysis", 0.5, "longcat_thinking", 0.93),

    # Image queries → longcat_omni regardless of topic
    make_example("look at this image and explain the code", "image_understanding", 0.4, "longcat_omni", 0.96),
    make_example("看这张图片解释代码", "image_understanding", 0.4, "longcat_omni", 0.96),
    make_example("what does this screenshot show", "image_understanding", 0.3, "longcat_omni", 0.96),
    make_example("这个截图显示了什么", "image_understanding", 0.3, "longcat_omni", 0.96),
    make_example("analyze the chart in this picture", "diagram_analysis", 0.45, "longcat_omni", 0.95),
    make_example("分析这张图片中的图表", "diagram_analysis", 0.45, "longcat_omni", 0.95),
]


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN: ASSEMBLE, BALANCE, SHUFFLE, OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

def build_from_seeds(seeds: list, backend: str) -> List[dict]:
    """Convert seed tuples to training examples."""
    return [make_example(q, intent, comp, backend, conf) for q, intent, comp, conf in seeds]


def trim_or_pad(examples: List[dict], target: int) -> List[dict]:
    """Trim to target count or duplicate to reach it."""
    if len(examples) >= target:
        return random.sample(examples, target)
    # Pad by duplicating with slight confidence jitter
    padded = list(examples)
    while len(padded) < target:
        ex = random.choice(examples)
        # Create a slightly varied copy
        msgs = ex["messages"]
        orig = json.loads(msgs[1]["content"])
        orig["confidence"] = round(min(0.98, max(0.65, orig["confidence"] + random.uniform(-0.03, 0.03))), 2)
        orig["complexity"] = round(min(1.0, max(0.0, orig["complexity"] + random.uniform(-0.05, 0.05))), 2)
        new_ex = {
            "messages": [
                msgs[0],
                {"role": "assistant", "content": json.dumps(orig, ensure_ascii=False)}
            ]
        }
        padded.append(new_ex)
    return padded[:target]


def main():
    # Build seed-based examples
    lite_seeds = build_from_seeds(LONGCAT_LITE_SEEDS, "longcat_lite")
    chat_seeds = build_from_seeds(LONGCAT_CHAT_SEEDS, "longcat_chat")
    coder_seeds = build_from_seeds(NVIDIA_QWEN_CODER_SEEDS, "nvidia_qwen_coder")
    deepseek_seeds = build_from_seeds(DEEPSEEK_PRO_SEEDS, "deepseek_pro")
    thinking_seeds = build_from_seeds(LONGCAT_THINKING_SEEDS, "longcat_thinking")
    omni_seeds = build_from_seeds(LONGCAT_OMNI_SEEDS, "longcat_omni")
    china_seeds = build_from_seeds(CHINAMOBILE_DEEPSEEK_SEEDS, "chinamobile_deepseek")

    # Generate augmented examples
    lite_aug = generate_lite_augmented()
    chat_aug = generate_chat_augmented()
    coder_aug = generate_coder_augmented()
    deepseek_aug = generate_deepseek_augmented()
    thinking_aug = generate_thinking_augmented()
    omni_aug = generate_omni_augmented()
    china_aug = generate_china_augmented()

    # Combine seeds + augmented per backend
    backends = {
        "longcat_lite": lite_seeds + lite_aug,
        "longcat_chat": chat_seeds + chat_aug,
        "nvidia_qwen_coder": coder_seeds + coder_aug,
        "deepseek_pro": deepseek_seeds + deepseek_aug,
        "longcat_thinking": thinking_seeds + thinking_aug,
        "longcat_omni": omni_seeds + omni_aug,
        "chinamobile_deepseek": china_seeds + china_aug,
    }

    # Balance to target per backend
    all_examples = []
    for backend_name, examples in backends.items():
        balanced = trim_or_pad(examples, TARGET_PER_BACKEND)
        all_examples.extend(balanced)

    # Add boundary cases (always included, not trimmed)
    all_examples.extend(BOUNDARY_CASES)

    # Shuffle
    random.shuffle(all_examples)

    # Write output
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_examples, f, ensure_ascii=False, indent=2)

    # Print stats
    print(f"\nTotal examples: {len(all_examples)}")
    print(f"Output: {OUTPUT_PATH}")
    print("\nPer-backend distribution:")
    from collections import Counter
    counter = Counter()
    for ex in all_examples:
        data = json.loads(ex["messages"][1]["content"])
        counter[data["backend"]] += 1
    for backend_name, count in sorted(counter.items(), key=lambda x: -x[1]):
        print(f"  {backend_name}: {count}")

    print("\n--- Sample examples ---")
    for ex in all_examples[:3]:
        print(json.dumps(ex, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
