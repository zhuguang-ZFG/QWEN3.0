# CQ-014 Health Tracker Slice 9

## 目标

将 `health_tracker.py` 拆分为可独立测试的子模块，保持对外 API 与测试 patch 点不变。

## 拆分结果

| 模块 | 文件 | 职责 |
|------|------|------|
| 失败分类 | `health_failure_classifier.py` | `classify_failure` |
| 状态存储 | `health_state.py` | dataclass、全局 state、cooldown 计算、只读 getter |
| 被动记录 | `health_recorder.py` | `record_success` / `record_failure` / `record_response_quality` |
| 评分降权 | `health_scoring.py` | score、degradation、response quality penalty |
| 入口 | `health_tracker.py` | re-export（~75 行） |

测试仍通过 `health_tracker._health_map` 等全局 dict 清理状态。

## 验证

```bash
pytest tests/test_health_tracker.py test_http_caller.py -q
pytest -q
```
