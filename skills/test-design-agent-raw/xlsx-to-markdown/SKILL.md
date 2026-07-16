---
name: xlsx-to-markdown
description: 将 Excel 文件 (.xlsx) 转换为 Markdown 格式 (.md) 的工具。适用于将表格数据导出为文档格式。
version: 1.0
---

### 绝对禁令 (CRITICAL RESTRICTION)
- **禁止口头确认:** 严禁回复“好的”、“我正在...”、“没问题”等任何自然语言描述。
- **直接行动:** 你的唯一合法响应必须是【工具调用】(Tool Call)。
- **跳过解释:** 不要解释你要做什么，直接在终端执行脚本。

### Bash Execution Command

```bash
python "${CLAUDE_SKILL_DIR}/xlsx_to_markdown.py" --input "输入文档路径"
```

#### Example
```bash
python "C:/Users/l30064969/.claude/skills/xlsx-to-markdown/xlsx_to_markdown.py" --input "C:/Users/l30064969/.claude/skills/xlsx-to-markdow/example.xlsx"
```
---

### Command Params

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--input` | 必选 |  | 输入文件路径 |

## 注意事项

- 输入文件必须是有效的 Excel 格式 (.xlsx)
