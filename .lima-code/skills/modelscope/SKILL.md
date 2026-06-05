# ModelScope (魔搭) Skill

ModelScope 是中国最大的 AI 模型开源社区，提供海量开源模型、数据集和开发工具。

## 核心功能

### 1. 模型搜索与发现
- 搜索开源模型（Qwen、DeepSeek、GLM 等）
- 按任务类型筛选（文本生成、图像生成、语音识别等）
- 查看模型详情、下载量、许可证

### 2. 数据集查询
- 浏览公开数据集
- 查看数据集结构和统计信息

### 3. 创空间 (Studio)
- 云端 GPU 算力环境
- 模型测试与微调
- 部署模型为 API

### 4. MCP 服务器管理
- 查看已部署的 MCP 服务器
- 管理 MCP 服务配置

## 常用命令

### 搜索模型
```
帮我搜索魔搭上的 Qwen2.5-Coder 模型
```

### 查看模型详情
```
查看魔搭上 Qwen/Qwen2.5-Coder-32B-Instruct 模型的详细信息
```

### 搜索数据集
```
搜索魔搭上的中文对话数据集
```

### 查看创空间
```
查看我创建的创空间
```

## API 推理配置

ModelScope 提供免费的 API 推理服务：

**API 端点**: `https://api-inference.modelscope.cn/v1/chat/completions`

**支持的模型**:
- Qwen2.5-Coder 系列（7B/14B/32B）
- DeepSeek V4
- GLM-5
- Kimi K2.5

**LiMa 后端配置**:
已在 `backends_registry.py` 中配置以下魔搭后端：
- `ms_qwen_coder_32b` - 32B 参数，编码能力最强
- `ms_qwen_coder_14b` - 14B 参数，平衡性能
- `ms_qwen_coder_7b` - 7B 参数，响应最快
- `ms_deepseek_v4` - DeepSeek V4 Flash
- `ms_qwen35_27b` - Qwen 3.5 27B
- `ms_kimi_k25` - Kimi K2.5
- `ms_glm5` - GLM-5

## 环境变量

确保在 `.env` 中设置：
```
MODELSCOPE_API_KEY=ms-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

## 使用场景

1. **代码生成**: 使用 Qwen2.5-Coder 系列模型进行代码生成
2. **模型测试**: 在创空间中测试新模型
3. **API 部署**: 将模型部署为 API 供 LiMa 使用
4. **数据集查询**: 查找训练数据集

## 注意事项

- 魔搭 API 推理服务免费但有速率限制
- 部分模型需要申请权限才能使用
- 创空间需要消耗算力点数

## 相关链接

- [魔搭官网](https://www.modelscope.cn)
- [魔搭 API 文档](https://modelscope.cn/docs/model-service/API-Inference/intro)
- [魔搭 MCP 服务](https://modelscope.cn/mcp)
