---
name: chrome-devtools-plugins
description: Chrome DevTools MCP 完整指令参考与通用操作模式。涵盖全部工具指令详解、核心工作流、页签管理、登录处理、SVG 元素操作、故障排查等。
---

# Chrome DevTools 完整指令参考与操作模式

> 本技能整合了 Chrome DevTools MCP 的全部 32 个工具指令，以及从实战中提炼的通用操作模式。

---

## 一、工具分类总览

| 分类 | 工具 | 说明 |
|------|------|------|
| **页面快照/截图** | `take_snapshot` / `take_screenshot` | 获取 a11y 树 / 截取页面图片 |
| **输入交互** | `click` / `fill` / `fill_form` / `type_text` / `press_key` / `drag` / `hover` / `upload_file` / `handle_dialog` | 点击/填写/拖拽/悬停/上传/处理弹窗 |
| **页面导航** | `navigate_page` / `new_page` / `close_page` / `select_page` / `wait_for` | 导航/新建/关闭/切换/等待页签 |
| **JS 执行** | `evaluate_script` | 在页面上执行 JavaScript |
| **环境模拟** | `emulate` / `resize_page` | 模拟设备/网络/地理位置/缩放窗口 |
| **控制台** | `list_console_messages` / `get_console_message` | 查看/获取控制台消息 |
| **网络** | `list_network_requests` / `get_network_request` | 查看/获取网络请求 |
| **性能** | `performance_start_trace` / `performance_stop_trace` / `performance_analyze_insight` / `lighthouse_audit` | 性能追踪 / Lighthouse 审计 |
| **内存** | `take_memory_snapshot` | 抓取内存堆快照 |

---

## 二、工具详解

### 2.1 页面快照/截图

#### take_snapshot
获取页面 a11y（无障碍）文本树，用于定位和交互元素。

| 参数 | 类型 | 说明 |
|------|------|------|
| `verbose` | boolean | 是否包含完整的 a11y 树细节（默认 false） |
| `filePath` | string | 保存快照到文件路径（可选） |

**返回**: 文本格式的 a11y 树，每个元素有唯一 `uid`（如 `uid=1_0 RootWebArea "Page Title" url="https://..."`）

**用途**:
- 定位页面元素（通过 uid）
- 自动化交互的前提
- 理解页面结构层次

**关键**: 每次操作后 uid 可能变化，操作前务必重新 take_snapshot 获取最新 uid。

#### take_screenshot
截取页面或元素的图片。

| 参数 | 类型 | 说明 |
|------|------|------|
| `format` | string | `png` / `jpeg` / `webp`（默认 png） |
| `quality` | number | JPEG/WebP 质量 0-100（仅 jpeg/webp 有效） |
| `uid` | string | 元素 uid，指定后截图该元素（默认截图整个页面） |
| `fullPage` | boolean | 是否全屏截图（与 uid 互斥，默认 false） |
| `filePath` | string | 保存截图的文件路径（**必须指定**，不带 filePath 的截图视为无效） |

**用途**:
- 测试执行中每步操作后截图记录
- 视觉检查页面状态
- 记录错误/成功/弹窗等状态

**截图命名规范**: `step_{序号}_{操作类型}_{关键词}.png`

**铁律**: 严禁用 take_snapshot 替代 take_screenshot，前者是文本后者是图片。

---

### 2.2 输入交互

#### click
点击指定 uid 的元素。

| 参数 | 类型 | 说明 |
|------|------|------|
| `uid` | string | 必填，元素的 uid |
| `dblClick` | boolean | 是否双击（默认 false） |
| `includeSnapshot` | boolean | 是否返回操作后的快照（默认 false） |

**用途**:
- 点击按钮、链接、复选框、下拉选项、日期数字等
- 点击 SVG/不可见 DOM 元素时需用 evaluate_script 替代

#### fill
向输入框/下拉框/文本域填写文本。

| 参数 | 类型 | 说明 |
|------|------|------|
| `uid` | string | 必填，目标元素的 uid |
| `value` | string | 填写的值（checkbox/radio 用 "true"/"false"） |
| `includeSnapshot` | boolean | 是否返回操作后的快照（默认 false） |

**注意**:
- 对 readonly 的下拉框（el-select）无效，需用 click 展开 → click 选项
- 对已有内容的 textarea，fill 是追加而非替换，需先 Ctrl+A → Delete 清空

#### fill_form
批量填写表单元素（比逐个 fill 更高效）。

| 参数 | 类型 | 说明 |
|------|------|------|
| `elements` | array | 数组，每项包含 `uid` 和 `value` |
| `includeSnapshot` | boolean | 是否返回操作后的快照（默认 false） |

**适用**: textbox、文本域、日期选择器、非 readonly 的 checkbox/radio

#### press_key
按键操作（键盘快捷键、导航键等）。

| 参数 | 类型 | 说明 |
|------|------|------|
| `key` | string | 必填，键名或组合键（如 "Enter"、"Tab"、"Control+A"、"Shift+Tab"、"Escape"、"Delete"） |
| `includeSnapshot` | boolean | 是否返回操作后的快照（默认 false） |

**常用场景**:
- `Ctrl+A` → 全选文本
- `Delete` → 删除选中内容
- `Enter` → 回车提交
- `Tab` / `Shift+Tab` → 切换焦点（无障碍测试）
- `Escape` → 关闭弹窗

#### type_text
在已聚焦的输入框中输入文本。

| 参数 | 类型 | 说明 |
|------|------|------|
| `text` | string | 必填，要输入的文本 |
| `submitKey` | string | 可选，输入后按的键（如 "Enter"） |

**注意**: 需要先聚焦元素（click 该 uid），文本是逐字输入而非批量写入。

#### drag
拖拽一个元素到另一个元素上。

| 参数 | 类型 | 说明 |
|------|------|------|
| `from_uid` | string | 必填，被拖拽元素的 uid |
| `to_uid` | string | 必填，目标位置的 uid |
| `includeSnapshot` | boolean | 是否返回操作后的快照（默认 false） |

#### hover
悬停在指定元素上。

| 参数 | 类型 | 说明 |
|------|------|------|
| `uid` | string | 必填，目标元素 uid |
| `includeSnapshot` | boolean | 是否返回操作后的快照（默认 false） |

#### upload_file
通过文件输入元素上传文件。

| 参数 | 类型 | 说明 |
|------|------|------|
| `uid` | string | 必填，文件输入元素的 uid 或触发文件选择器的元素 uid |
| `filePath` | string | 必填，要上传的本地文件路径 |
| `includeSnapshot` | boolean | 是否返回操作后的快照（默认 false） |

#### handle_dialog
处理浏览器弹窗/对话框。

| 参数 | 类型 | 说明 |
|------|------|------|
| `action` | string | 必填，"accept"（接受）或 "dismiss"（取消） |
| `promptText` | string | 可选，prompt 对话框的输入文本 |

**场景**: 处理 alert、confirm、prompt 弹窗。

---

### 2.3 页面导航

#### navigate_page
在当前页签导航到 URL 或前进/后退/刷新。

| 参数 | 类型 | 说明 |
|------|------|------|
| `type` | string | "url" / "back" / "forward" / "reload" |
| `url` | string | 目标 URL（type=url 时必需） |
| `ignoreCache` | boolean | 是否忽略缓存（reload 时有效） |
| `handleBeforeUnload` | string | "accept" / "decline"，是否自动处理 beforeunload 弹窗 |
| `initScript` | string | 导航前执行的 JS 脚本 |
| `timeout` | number | 最大等待时间毫秒（默认 0 使用默认值） |

**注意**: 不同系统间导航时，**应使用 new_page 而非 navigate_page**，避免覆盖已登录的页签。

#### new_page
打开新页签并加载 URL。

| 参数 | 类型 | 说明 |
|------|------|------|
| `url` | string | 必填，要加载的 URL |
| `background` | boolean | 是否在后台打开（默认 false） |
| `isolatedContext` | string | 使用独立的浏览器上下文（用于隔离 cookie） |
| `timeout` | number | 最大等待时间毫秒 |

**核心规则**: 多系统测试中，始终用 new_page 打开新页签，不用 navigate 覆盖。

#### close_page
关闭指定页签。

| 参数 | 类型 | 说明 |
|------|------|------|
| `pageId` | number | 必填，要关闭的页签 ID |

**注意**: 最后一个打开的页签不能被关闭。

#### select_page
切换当前操作上下文的页签。

| 参数 | 类型 | 说明 |
|------|------|------|
| `pageId` | number | 必填，目标页签 ID |
| `bringToFront` | boolean | 是否将页签移到前台（默认 true） |

#### list_pages
获取所有已打开页签的列表。

**用途**: 查看所有页签，确认目标页签的 pageId。

#### wait_for
等待页面中出现指定文本。

| 参数 | 类型 | 说明 |
|------|------|------|
| `text` | string[] | 必填，等待出现的文本列表 |
| `timeout` | number | 最大等待时间毫秒（默认使用默认值） |

**用途**: 确保页面加载完成后再进行交互操作。

---

### 2.4 JS 执行

#### evaluate_script
在页面中执行 JavaScript 函数。

| 参数 | 类型 | 说明 |
|------|------|------|
| `function` | string | 必填，要执行的 JS 函数（函数声明格式） |
| `args` | string[] | 可选，传入函数的参数（uid 列表） |
| `filePath` | string | 可选，大输出保存到文件路径 |
| `dialogAction` | string | 处理弹窗："accept" / "dismiss" / prompt 回复文本 |

**适用场景**:
- SVG/不可见 DOM 元素点击（这些在 a11y snapshot 中不生成 uid）
- 获取不在 a11y 树中的 DOM 数据
- 排查 iframe 结构、页面 URL、页面状态
- 执行无障碍检查 JS 片段

**不推荐用于**:
- 表单值操作（Element UI 的 Vue 响应式不响应 JS 赋值）
- 下拉框设值（el-select 必须 click 展开 → click 选项）
- radio/checkbox 状态设置（必须用 click 直接点击 uid）

---

### 2.5 环境模拟

#### emulate
模拟不同设备、网络条件、地理位置等。

| 参数 | 类型 | 说明 |
|------|------|------|
| `viewport` | string | 视口尺寸 `<width>x<height>x<devicePixelRatio>[,mobile][,touch][,landscape]` |
| `networkConditions` | string | 网络模拟：`Offline` / `Slow 3G` / `Fast 3G` / `Slow 4G` / `Fast 4G` |
| `cpuThrottlingRate` | number | CPU 节流比 1-20（1=不节流） |
| `colorScheme` | string | 主题：`dark` / `light` / `auto` |
| `geolocation` | string | 模拟地理位置 `<latitude>,<longitude>` |
| `userAgent` | string | 自定义 UA（空字符串清除） |
| `extraHttpHeaders` | string | 额外 HTTP 头（JSON 字符串） |

#### resize_page
调整当前页签窗口大小。

| 参数 | 类型 | 说明 |
|------|------|------|
| `width` | number | 必填，窗口宽度 |
| `height` | number | 必填，窗口高度 |

---

### 2.6 控制台

#### list_console_messages
列出所有控制台消息。

| 参数 | 类型 | 说明 |
|------|------|------|
| `types` | string[] | 过滤消息类型：`log` / `debug` / `info` / `error` / `warn` / `dir` / `dirxml` / `table` / `trace` / `clear` / `assert` / `count` / `timeEnd` / `verbose` / `issue` |
| `pageSize` | number | 每页条数 |
| `pageIdx` | number | 页码（0 开始） |
| `includePreservedMessages` | boolean | 包含跨导航保留的消息 |

**常用场景**: 检查页面错误（`types: ['error']`）、检查警告（`types: ['warn']`）、检查无障碍问题（`types: ['issue']`）。

#### get_console_message
获取特定控制台消息的详情。

| 参数 | 类型 | 说明 |
|------|------|------|
| `msgid` | number | 必填，消息 ID |

---

### 2.7 网络

#### list_network_requests
列出所有网络请求。

| 参数 | 类型 | 说明 |
|------|------|------|
| `resourceTypes` | string[] | 过滤资源类型：`document` / `stylesheet` / `image` / `media` / `font` / `script` / `xhr` / `fetch` / `manifest` / `ping` / `cspviolationreport` / `preflight` / `other` |
| `pageSize` | number | 每页条数 |
| `pageIdx` | number | 页码（0 开始） |
| `includePreservedRequests` | boolean | 包含跨导航保留的请求 |

#### get_network_request
获取特定网络请求的详情。

| 参数 | 类型 | 说明 |
|------|------|------|
| `reqid` | number | 可选，请求 ID（不传则获取当前选中的请求） |
| `requestFilePath` | string | 请求体保存到文件路径 |
| `responseFilePath` | string | 响应体保存到文件路径 |

---

### 2.8 性能

#### performance_start_trace
开始性能追踪记录。

| 参数 | 类型 | 说明 |
|------|------|------|
| `reload` | boolean | 是否自动刷新页面（默认 true） |
| `autoStop` | boolean | 是否自动停止（默认 true） |
| `filePath` | string | 追踪数据保存文件路径 |

**用途**: 捕获完整的页面加载性能数据，用于分析 LCP、FCP 等指标。

#### performance_stop_trace
停止当前性能追踪记录。

| 参数 | 类型 | 说明 |
|------|------|------|
| `filePath` | string | 追踪数据保存文件路径 |

#### performance_analyze_insight
分析性能追踪中的特定洞察。

| 参数 | 类型 | 说明 |
|------|------|------|
| `insightSetId` | string | 必填，洞察集 ID（从 trace 结果中获取） |
| `insightName` | string | 必填，洞察名称：`LCPBreakdown` / `DocumentLatency` / `RenderBlocking` / `LCPDiscovery` |

#### lighthouse_audit
运行 Lighthouse 审计。

| 参数 | 类型 | 说明 |
|------|------|------|
| `mode` | string | "navigation"（刷新后审计）/ "snapshot"（分析当前状态） |
| `device` | string | "desktop" / "mobile" |
| `outputDirPath` | string | 审计报告保存目录 |

**用途**: 无障碍审计、SEO 检查、最佳实践检查、性能分析。

---

### 2.9 内存

#### take_memory_snapshot
抓取内存堆快照。

| 参数 | 类型 | 说明 |
|------|------|------|
| `filePath` | string | 必填，保存 `.heapsnapshot` 文件的路径 |

**用途**: 内存泄漏分析。抓取 baseline/target/final 三个状态的快照，配合 memlab 分析。

**注意**: 不要直接读取 `.heapsnapshot` 文件（太大），使用 memlab 分析。

---

## 三、核心操作模式

### 3.1 标准操作工作流

```
1. 导航: navigate_page 或 new_page
2. 等待: wait_for 确保内容已加载
3. 快照: take_snapshot 理解页面结构
4. 交互: 使用 uid 进行 click/fill/click 等操作
5. 验证: take_snapshot / take_screenshot 确认结果
6. 截图: take_screenshot(filePath="...") 保存截图
```

### 3.2 工具选择原则

| 场景 | 首选工具 | 说明 |
|------|---------|------|
| 定位页面元素 | `take_snapshot` | 获取 a11y 树和 uid |
| 点击按钮/链接/选项 | `click` | 通过 uid 点击 |
| 填写普通输入框 | `fill_form` | 批量填写，比逐个 fill 高效 |
| 下拉框选择 | `click` 展开 → `click` 选项 | el-select 必须 click → click |
| 日期选择 | `fill_form` 填值 → `click` 日期数字 | 不能点关闭按钮 |
| radio/checkbox | `click` 直接点击 | 不能用 JS 操作 |
| 键盘操作 | `press_key` | 快捷键、Tab、Enter 等 |
| 文件上传 | `upload_file` | 通过文件输入 uid |
| 弹窗处理 | `handle_dialog` | accept/dismiss |
| 悬停/拖拽 | `hover` / `drag` | 特定交互场景 |
| 视觉检查 | `take_screenshot` | 截图记录 |
| 排查 DOM | `evaluate_script` | 获取不在 a11y 树中的信息 |

**铁律**: 能用 `take_snapshot` / `click` / `fill_form` 解决的，绝不绕道 JavaScript。

### 3.3 高效操作技巧

- 使用 `filePath` 参数保存大输出（截图、快照、trace）
- 使用分页（`pageIdx`, `pageSize`）和过滤（`types`, `resourceTypes`）减少数据量
- 输入操作设置 `includeSnapshot: false` 除非需要更新后的页面状态
- 多个独立的工具调用可以并行发送

---

## 四、通用处理场景

### 4.1 HTTPS 证书警告处理

**场景**: 网页打开遇到 "您的连接不是私密连接" 提示。

**处理**:
1. take_snapshot 确认出现安全警告页面
2. click 找到 "高级" 链接的 uid
3. click 找到 "继续前往" 链接的 uid

### 4.2 空白页恢复

**场景**: 登录后页面一直显示空白，持续等待超过 10s。

**处理**:
1. 用 evaluate_script 确认页面状态：`() => ({ title: document.title, url: window.location.href })`
2. 重新在新页签打开并登录
3. 不要关闭其他已登录的页签

### 4.3 多系统页签管理

**核心规则**:
- 不同系统间导航时，**必须新建页签**（new_page），禁止关闭或覆盖已打开的页签
- 登录后的页签必须保持打开
- 使用 list_pages 查看 / select_page 切换

### 4.4 登录方式选择（SVG 元素）

**场景**: 登录方式图标使用 SVG 呈现，在 a11y snapshot 中不生成 uid。

**识别特征**: DOM 选择器为 `.login_method_tab .item`

**方法**: 必须用 JS 点击：
```javascript
document.querySelectorAll('.login_method_tab .item')[N].click()
```

### 4.5 隐藏 Checkbox 操作

**场景**: Element UI 的 checkbox 原生 input 是隐藏的（opacity:0）。

**方法**: 点击可见的视觉层：
```javascript
document.querySelector('.el-checkbox__inner').click()
```

### 4.6 输入框识别

**常见模式**: 系统 DOM 上可能存在多组 input

```
idx 0: text → 隐藏/装饰用
idx 1: password → 隐藏/装饰用
idx 2: text → 用户可见的账号输入框
idx 3: password → 用户可见的密码输入框
```

**通用识别原则**:
```javascript
[...document.querySelectorAll('input')].map((el, i) => ({
  index: i, type: el.type,
  visible: el.offsetParent !== null && el.style.opacity !== '0'
}))
```

---

## 五、调试排查思路

### 5.1 元素定位失败

```
元素找不到？
  → take_snapshot 刷新页面结构
  → 检查元素是否在 iframe 内（click/fill_form 自动跨 iframe）
  → 检查元素是否为 SVG（用 evaluate_script 定位）
  → 检查 DOM 是否已就绪（等待页面加载）
  → 重新 take_snapshot 获取最新 uid（uid 每次操作后可能变化）
```

### 5.2 表单操作不生效

```
下拉框填了值但校验仍报错？
  → 检查是否用了 evaluate_script / fill() 强行设值
  → 改回 click 展开 → click 选项 uid

日期选择器不生效？
  → fill_form 填值后，多次 take_snapshot
  → 等日历中目标日期数字出现在快照中
  → click 日期数字 uid，不能点关闭按钮

Textarea 内容异常？
  → 停止用 fill() 覆盖
  → 改为 press_key "Control+A" → "Delete" → 输入新值
```

### 5.3 页签相关问题

```
页签丢失？
  → list_pages 查看所有页签
  → select_page 切换到正确页签
  → 始终用 new_page 打开新页签，不用 navigate 覆盖

页面空白？
  → evaluate_script 确认 title 和 url
  → 重新 new_page 打开并登录
```

---

## 六、故障排查速查表

| 问题 | 原因 | 解决方法 |
|------|------|---------|
| 页面空白 | 加载失败或 JS 错误 | 重新 new_page 打开并登录 |
| 点击无响应 | 元素不可见或 DOM 未就绪 | take_snapshot 确认元素存在 |
| 输入无效 | 输入框被隐藏或 readonly | 检查 input type/style |
| 登录失败 | 登录方式选择错误 | 确认图标索引（0 或 2） |
| 元素定位失败 | iframe 或 SVG 元素 | iframe 用 uid，SVG 用 JS |
| 页签丢失 | navigate 覆盖了已有页签 | 用 new_page 而非 navigate |
| 安全警告 | HTTPS 证书不信任 | 高级 → 继续前往 |
| 工具不可用 | read-only 模式 | 禁用 read-only |
| DevToolsActivePort 错误 | Chrome 未启用远程调试 | chrome://inspect/#remote-debugging |
| Target closed | 页签被关闭 | list_pages 重新查看 |

---

## 七、常用 JS 代码片段

> 各子技能中已包含常用的 evaluate_script 代码片段。如需更多 JS 片段，可参考 dom-agent/multimodal-parse、verdict-heal/fault-classify、verdict-heal/tool-remediate 等子技能中的 JS 示例。
