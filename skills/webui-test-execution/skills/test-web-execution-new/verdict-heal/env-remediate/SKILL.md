---
name: verdict-heal/env-remediate
description: 环境修复技能。处理环境类故障（空白页、证书警告、会话过期、网络异常等），恢复页面可用状态。
version: V1.0
---

# 环境修复

> 针对环境类故障进行修复，恢复页面可用状态，使测试能够继续执行。

---

## 一、修复场景

### 1.1 空白页修复

```
场景: 登录后页面一直显示空白
步骤:
  1. evaluate_script 确认页面状态:
     function() { return { title: document.title, url: window.location.href } }
  2. 判断: 如果页面能获取到 URL 和 title，说明页面已加载但渲染异常
  3. 修复: 重新 new_page 打开同一 URL（不要关闭其他已登录的页签）
  4. 验证: take_snapshot 确认页面有实质内容
```

### 1.2 HTTPS 证书警告处理

```
场景: 页面出现 "您的连接不是私密连接" 安全警告
步骤:
  1. take_snapshot 确认出现安全警告页面
  2. click 找到 "高级" 链接的 uid
  3. click 找到 "继续前往" 链接的 uid
  4. take_snapshot 验证页面已加载
```

### 1.3 会话过期处理

```
场景: 操作过程中页面跳转到登录页
步骤:
  1. evaluate_script 判断当前 URL 是否为登录页
  2. 如果是: 在新页签（new_page）打开登录页并重新登录
  3. 登录后，用 evaluate_script 获取新页签的 pageId
  4. select_page 切换到正确页签
  5. 回到原操作步骤重新执行
```

### 1.4 页面加载超时

```
场景: 页面长时间无响应，wait_for 超时
步骤:
  1. evaluate_script 确认页面状态
  2. 如果页面已部分加载: 尝试 navigate_page reload
  3. 如果页面未加载: 用 new_page 重新打开
  4. 用 wait_for 等待关键元素出现
```

---

## 二、修复流程

```
输入: fault-classify 输出的故障分类结果
输出: 修复后的页面状态 + 是否可继续

步骤:
  1. 读取故障分类结果
  2. 判断故障类型
  3. 执行对应修复策略
  4. 验证修复结果:
     - take_snapshot 确认页面有实质内容
     - 检查目标元素是否可访问
  5. 输出修复结果
```

---

## 三、修复验证

```
修复后验证:
  1. take_snapshot 确认页面正常
  2. evaluate_script 检查页面状态:
     function() {
       return {
         title: document.title,
         url: window.location.href,
         hasContent: document.body.textContent.trim().length > 100
       };
     }
  3. 验证通过 → 返回原测试步骤继续执行
  4. 验证失败 → 返回 fault-classify 重新分类
```

---

## 四、输出格式

```json
{
  "fault_category": "ENV",
  "sub_category": "空白页",
  "repair_action": "重新 new_page 打开页面",
  "repair_result": "SUCCESS | FAILED",
  "verification": {
    "page_loaded": true,
    "has_content": true,
    "target_elements_available": true
  },
  "next_step": "回到原测试步骤重新执行"
}
```

---

## 五、关键规则

1. **保留已登录页签**: 修复时不要关闭已登录的页签，用 new_page 打开新页签
2. **修复后验证**: 每次修复后必须验证页面状态
3. **修复重试**: 修复失败可重试一次，仍失败则重新分类
4. **会话管理**: 会话过期时重新登录，修复后切回原页签
5. **截图记录**: 修复前后的页面状态都要截图记录
