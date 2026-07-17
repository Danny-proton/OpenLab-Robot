# 执行器适配器接口规范

## 已实现适配器
| 适配器 | 位置 | 适用 |
|--------|------|------|
| mock | scripts/adapters/ (内置) | 测试 pipeline |
| http | scripts/adapters/ (内置) | HTTP agent |
| openlab_robot | scripts/adapters/ (内置) | cc-haha subprocess |

## 规划适配器（子 skill 形式）
| 适配器 | 位置 | 状态 |
|--------|------|------|
| cdp-web-executor | adapters/cdp-web-executor/ | 待提供 |
| script-executor | adapters/script-executor/ | 待实现 |
| api-executor | adapters/api-executor/ | 待实现 |

## 适配器接口

```python
def call_adapter(adapter_config, case, run_id, case_run_id) -> AdapterResult:
    # 返回: final_answer, raw_trace, latency_ms, status, error
```

## 用例输入适配器
| 格式 | 适配器 |
|------|--------|
| YAML | case_io.py (内置) |
| Excel | excel_adapter.py |

## 适配器选择
通过 config.yaml 的 adapter 字段：mock / http / openlab_robot / cdp_web / script / api
