---
name: language-pack-test
description: 语言包/i18n 资源文件直测。在无需驱动 UI 的情况下，直接解析语言包文件，检查键完整性、未翻译值、占位符一致性、英文质量，覆盖 UI 未展示的全部字符串。
type: agent
version: 1.0
---

# 语言包直接测试 Skill

> **背景（Issue 5）**：原 i18n 测试仅依赖 UI 驱动检查可见文本，无法覆盖 UI 未展示的字符串、动态拼接的文案、边缘场景。若待测系统提供语言包文件，应优先进行语言包直测，作为 UI 测试的重要补充。

## 触发条件

- Phase 1.2 中用户确认存在语言包，且提供了路径与格式
- `.memory/shared/environment.md` 中 `language_pack.available = true`

若用户未提供语言包 → 跳过本 Skill，直接进入 Phase 2。

## 输入

从 `.memory/shared/environment.md` 读取语言包信息：

```
language_pack:
  available: true
  root_path: <语言包根目录>
  format: <JSON | JS | YAML | PO | XLIFF | CSV | other>
  languages: [zh-CN, en-US]
  organization: <by_lang | by_module | single_file>
```

可选：示例文件路径（用于格式校准）。

## 支持的格式与解析策略

| 格式 | 扩展名 | 解析方式 |
|------|--------|----------|
| JSON | .json | 直接 `JSON.parse`，支持嵌套 key（用 `.` 拼接路径） |
| JS | .js | 提取 `export default {...}` 或 `module.exports = {...}` 后解析对象字面量 |
| YAML | .yaml/.yml | YAML 解析器，支持嵌套 |
| PO | .po | gettext 格式，解析 `msgid` / `msgstr` 对 |
| XLIFF | .xlf/.xliff | XML 解析，提取 `<source>` / `<target>` |
| CSV | .csv | 按 key,value,zh,en 列解析 |
| 其他 | - | 通过 AskUserQuestion 询问用户格式细节后定制解析 |

> 若格式无法自动解析，通过 AskUserQuestion 向用户索取一个示例文件内容，据此定制解析逻辑。

## 测试流程

### Step 1：语言包发现与加载

1. 根据 `root_path` 遍历语言包文件
2. 按 `organization` 分类：
   - `by_lang`：`<root>/<lang>/...`（如 `locales/en-US/common.json`）
   - `by_module`：`<root>/<module>/<lang>.json`（如 `modules/login/en-US.json`）
   - `single_file`：`<root>/all.json` 单文件含多语言
3. 加载所有文件，构建内部数据结构：

```
语言包数据模型:
{
  "<lang>": {
    "<key>": {
      "value": "<值>",
      "source_file": "<来源文件>",
      "module": "<模块，若 by_module>"
    }
  }
}
```

4. 若加载失败（文件不存在、格式错误），通过 AskUserQuestion 询问用户确认路径/格式，重试一次

### Step 2：键完整性检查

对比各语言的 key 集合：

```
检查项:
- zh-CN 有但 en-US 无的 key（英文缺失，UI 可能显示 key 或 fallback 中文）
- en-US 有但 zh-CN 无的 key（中文缺失）
- 两者都有但 key 拼写不一致（疑似笔误，如 "usernam" vs "username"）
```

输出键完整性报告：

```
键完整性:
  zh-CN 总 key 数: N
  en-US 总 key 数: M
  英文缺失 key: [key1, key2, ...]（Critical，UI 会显示 key 或中文）
  中文缺失 key: [...]（Major）
  疑似笔误 key 对: [(zh-key, en-key), ...]（Minor）
```

### Step 3：未翻译值检测

**英文包中检测中文残留**（核心检查方向，与 Issue 1 一致）：

```
对 en-US 中每个 value:
  - 检测是否包含中文字符（[\u4e00-\u9fff]）
  - 检测是否为占位符未替换（如仍是 "请输入用户名"）
  - 标记为"未翻译"或"部分翻译"
```

**中文包中检测英文残留**（轻量检查，仅标记明显异常）：

```
对 zh-CN 中每个 value:
  - 检测是否纯英文且无中文（可能是误填的英文值）
  - 排除合理英文（URL、邮箱、品牌名、缩写如 ID/URL/API）
  - 标记为"疑似未翻译"
```

输出未翻译值报告：

```
未翻译值:
  英文包中文残留: [key1: "请输入...", key2: "确定", ...]（Critical）
  中文包英文残留: [key1: "Submit", ...]（Major，排除合理英文后）
```

### Step 4：占位符与格式字符串一致性

检查各语言间的占位符/插值表达式是否一致：

```
支持的占位符格式:
- {0}, {1}, {2}...（位置占位符）
- {name}, {count}...（命名占位符）
- %s, %d, %f...（printf 风格）
- {{name}}, {{ count }}...（Mustache/Handlebars）
- ${name}, ${name + 1}...（模板字符串）
- %1$s, %2$d...（带位置参数的 printf）
```

对每个 key，对比 zh-CN 与 en-US 的占位符：

```
检查项:
- 占位符数量是否一致（zh 有 2 个 {0}{1}，en 只有 1 个 → Bug）
- 占位符名称是否一致（zh 用 {name}，en 用 {username} → 可能 Bug）
- 占位符位置顺序是否一致（zh: {0} {1}，en: {1} {0} → 可能有意但需人工确认）
```

输出占位符一致性报告：

```
占位符不一致:
  key: "welcome_msg"
    zh-CN: "欢迎 {name}，您有 {count} 条新消息"  (占位符: {name}, {count})
    en-US: "Welcome {name}"                      (占位符: {name})  ← 缺失 {count}
  严重度: Critical（运行时会因缺少参数报错或显示 undefined）
```

### Step 5：英文质量直测

对 en-US 中所有 value，调用 `english-quality-eval` 子 Skill 的 7 维度评测方法：

- 词汇准确性、语法正确性、语义表达、场合规范、一致性、拼写与大小写、标点符号
- 语言包直测的优势：可一次性评测全部英文值（可能数百到数千条），覆盖 UI 未展示的字符串
- 评测结果作为 Phase 5.5 综合评测的核心输入

> 详细评测方法见 `sub/skills/english-quality-eval/SKILL.md`。

### Step 6：交叉验证（与 UI 采样，Phase 5.5 时执行）

Phase 5 收集 UI 英文样本后，与本语言包直测结果交叉验证：

```
交叉验证项:
- UI 显示文本与语言包对应 key 的值是否一致
  - 不一致 → UI 可能硬编码，未走 i18n（Critical）
  - 一致 → 正常
- UI 采样的文本是否能在语言包中找到对应 key
  - 找不到 → 可能是动态拼接、或硬编码
- 语言包中存在但 UI 未展示的 key
  - 列出供后续 UI 测试补覆盖
```

### Step 7：生成语言包测试报告

输出 `LANGUAGE_PACK_TEST_REPORT.md`：

```markdown
# 语言包直接测试报告

## 1. 语言包概览
- 根目录: <path>
- 格式: <format>
- 支持语言: [zh-CN, en-US]
- 文件组织: <by_lang | by_module | single_file>
- 加载文件数: N
- 总 key 数（zh-CN / en-US）: N / M

## 2. 键完整性
| 检查项 | 数量 | 严重度 | 详情 |
|--------|------|--------|------|
| 英文缺失 key | N | Critical | [列表] |
| 中文缺失 key | N | Major | [列表] |
| 疑似笔误 key | N | Minor | [列表] |

## 3. 未翻译值
| 检查项 | 数量 | 严重度 | 详情 |
|--------|------|--------|------|
| 英文包中文残留 | N | Critical | [key: value 列表] |
| 中文包英文残留（排除合理英文） | N | Major | [key: value 列表] |

## 4. 占位符一致性
| key | zh-CN 占位符 | en-US 占位符 | 问题 | 严重度 |
|-----|-------------|-------------|------|--------|
| ... | ... | ... | ... | ... |

## 5. 英文质量直测结果
- 评测样本数: N（全部 en-US value）
- 综合均分: X.X/10
- 综合等级: A/B/C/D
- 各维度均分: [维度1: X.X, ..., 维度7: X.X]
- 详细评测见 ENGLISH_QUALITY_EVAL_REPORT.md 语言包部分

## 6. 关键问题清单
（按 Critical / Major / Minor 分级，含修复建议）

## 7. 结论
<语言包整体质量评价；是否可作为 UI 测试的有效补充；需优先修复的问题>
```

## 测试原则

1. **覆盖优先**：语言包直测覆盖全部 key，弥补 UI 测试只检查可见文本的不足
2. **方向一致**：未翻译值检测以"英文包中文残留"为主方向（与 Issue 1 裁剪一致），中文包英文残留仅作轻量检查
3. **可追溯**：每个问题关联具体 key、文件、行号（若可获取），便于开发定位
4. **交叉验证**：与 UI 采样结果交叉验证，识别硬编码与动态拼接
5. **格式鲁棒**：遇到无法解析的格式，主动通过 AskUserQuestion 询问，不强行猜测

## 与其他子 Skill 的关系

- **上游**：`i18n-comprehensive-test`（Phase 1.2 收集语言包路径格式信息）
- **协同**：`english-quality-eval`（Step 5 调用其评测方法）、`test-web-execution`（Phase 5 UI 采样用于 Step 6 交叉验证）
- **下游**：`test-report`（Phase 6 综合报告引用本报告结论）

## AskUserQuestion 使用场景

本 Skill 在以下场景使用 AskUserQuestion（与 Issue 5 要求一致）：

1. **Phase 1.2 语言包询问**：询问是否存在语言包，收集路径/格式/语言/组织方式
2. **格式无法解析**：索取示例文件内容以定制解析逻辑
3. **路径/格式确认**：加载失败时与用户确认路径或格式是否正确
4. **疑似笔误 key 确认**：对不确定的 key 笔误，询问用户是否为同一 key
