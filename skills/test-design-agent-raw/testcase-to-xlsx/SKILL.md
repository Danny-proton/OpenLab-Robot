---
name: testcase-to-xlsx
description: 将测试用例 markdown 文件 (.md) 转换为 Excel 格式 (.xlsx) 的工具。适用于将测试规格文档导出为电子表格格式进行管理和分享。
version: 2.0
---

### 绝对禁令 (CRITICAL RESTRICTION)
- **禁止口头确认:** 严禁回复“好的”、“我正在...”、“没问题”等任何自然语言描述。
- **直接行动:** 你的唯一合法响应必须是【工具调用】(Tool Call)。
- **跳过解释:** 不要解释你要做什么，直接在终端执行脚本。

### Bash Execution Command

```bash
python "${CLAUDE_SKILL_DIR}/testcase-to-xlsx.py" --input "输入文档路径"
```

#### Example
```bash
python "C:/Users/l30064969/.claude/skills/testcase-to-xlsx/testcase-to-xlsx.py" --input "C:/Users/l30064969/.claude/skills/testcase-to-xlsx/example.md"
```
---

### Command Params

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--input` | 必选 |  | 输入文件路径 |

### 依赖要求

- Python 3.x
- pandas 库
- openpyxl 库

安装依赖：
```bash
pip install pandas openpyxl
```

## 注意事项

- 输入文件必须是有效的 MarkDown 格式 (.md)
