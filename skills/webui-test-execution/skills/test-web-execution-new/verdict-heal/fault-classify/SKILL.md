---
name: verdict-heal/fault-classify
description: 故障分类技能。对测试失败的步骤进行分析，识别失败类型和根因，为自愈提供分类依据。
version: V1.0
---

# 故障分类

> 分析测试失败原因，将故障分类为不同类别，指导后续自愈策略选择。

---

## 一、故障分类体系

### 1.1 故障大类

| 类别 | 代码 | 说明 | 自愈方向 |
|------|------|------|---------|
| 环境故障 | ENV | 页面加载失败、空白页、网络异常 | env-remediate |
| 工具故障 | TOOL | MCP 工具调用失败、元素定位失败 | tool-remediate |
| 脚本故障 | SCRIPT | 操作步骤不匹配、填写值错误 | script-remediate |
| 预期不符 | MISMATCH | 操作成功但结果与预期不一致 | re-judge |

### 1.2 故障子类

#### ENV - 环境故障
| 子类 | 特征 | 示例 |
|------|------|------|
| 页面加载超时 | 页面长时间无响应 | wait_for 超时 |
| 空白页 | snapshot 中无实质内容 | 登录后页面空白 |
| 证书警告 | 出现 HTTPS 安全警告 | "您的连接不是私密连接" |
| 会话过期 | 跳转到登录页 | 长时间未操作后页面跳转 |
| 网络异常 | 请求失败或无响应 | 页面资源加载失败 |

#### TOOL - 工具故障
| 子类 | 特征 | 示例 |
|------|------|------|
| 元素不存在 | snapshot 中找不到目标 uid | 元素被动态移除 |
| 元素不可见 | 元素被隐藏或折叠 | 折叠面板未展开 |
| 工具不可用 | MCP 工具返回错误 | DevTools 连接断开 |
| 操作无响应 | 点击/填写无效果 | 元素 disabled |

#### SCRIPT - 脚本故障
| 子类 | 特征 | 示例 |
|------|------|------|
| 填写值错误 | 填写了错误的值 | 选了错误选项 |
| 操作顺序错误 | 步骤顺序与页面逻辑不匹配 | 未登录就访问业务页 |
| 工具选择错误 | 使用了不正确的操作工具 | 对下拉框用 fill |
| 步骤遗漏 | 缺少必要的操作步骤 | 未关闭弹窗 |

#### MISMATCH - 预期不符
| 子类 | 特征 | 示例 |
|------|------|------|
| 页面路径变更 | 实际跳转 URL 与预期不同 | 跳转到了错误页面 |
| 提示信息不同 | 错误/成功提示内容与预期不同 | 提示文案变更 |
| 页面结构变更 | 页面布局/元素结构发生变化 | 字段位置调整 |
| 功能变更 | 页面功能逻辑发生变化 | 必填字段变化 |

---

## 二、故障分析流程

```
步骤:
  1. 获取失败步骤的详细信息:
     - 失败的操作（MCP 工具调用）
     - 失败时的 snapshot 内容
     - 失败时的截图路径
  2. 提取关键信息:
     - 当前页面类型/URL
     - 目标元素是否存在
     - 是否有错误提示/弹窗
     - 页面状态（空白/报错/加载中等）
  3. 对比预期与实际:
     - 预期结果 vs 实际结果
     - 预期页面 vs 实际页面
  4. 分类判定:
     - 匹配故障大类 → 子类
  5. 输出分类结果
```

---

## 三、故障分析辅助命令

```javascript
// 页面状态诊断
function() {
  const body = document.body;
  const bodyText = body.textContent.trim();
  const hasContent = bodyText.length > 50;  // 阈值 50，与 multimodal-parse 空白页检测一致
  const hasErrors = [...document.querySelectorAll('.error, .err, [role="alert"]')]
    .map(el => el.textContent.trim());
  const hasDialog = document.querySelectorAll('dialog, .modal, [role="dialog"]').length > 0;
  const isBlank = bodyText.length < 50;
  
  return {
    title: document.title,
    url: window.location.href,
    isBlank: isBlank,
    hasContent: hasContent,
    hasErrors: hasErrors,
    hasDialog: hasDialog,
    errorTexts: hasErrors.join('; ')
  };
}
```

---

## 四、分类输出格式

```json
{
  "step_number": 3,
  "failed_operation": {
    "tool": "click",
    "target_uid": "3_24",
    "arguments": {}
  },
  "failure_description": "点击按钮后无响应",
  "analysis": {
    "current_page": "form",
    "page_url": "https://...",
    "target_element_found": false,
    "has_errors": ["提交校验失败: 必填字段不能为空"],
    "has_dialogs": false,
    "page_state": "error"
  },
  "classification": {
    "category": "SCRIPT",
    "sub_category": "填写值错误",
    "confidence": "HIGH",
    "reason": "元素存在但校验未通过，说明必填字段未填写"
  },
  "recommended_heal": {
    "skill": "script-remediate",
    "action": "补填未填写的必填字段"
  }
}
```

---

## 五、关键规则

1. **快照驱动分析**: 基于失败时刻的 snapshot 内容进行分析
2. **截图辅助验证**: 截图用于确认视觉层面的故障特征
3. **分类优先级**: 先判环境，再判工具，最后判脚本和预期
4. **置信度标注**: 对分类结果标注置信度（HIGH/MEDIUM/LOW）
5. **自愈建议**: 分类时同时输出推荐的自愈 skill 和行动建议
6. **保留原始数据**: 分类结果中包含原始失败信息，便于人工复核
