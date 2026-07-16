# 项目测试执行记忆使用规则

## 记忆库位置

当前项目的测试执行记忆库位于：

- `.memory/`

通用测试执行方法位于：

- `.claude/skills/test-web-execution/`

## 启动时必须读取

执行任何测试用例前，先读取：

- `.memory/README.md`
- `.memory/shared/README.md`
- `.memory/shared/execution_rules.md`
- `.memory/shared/environment.md`

## 模块定位规则

根据用例中的系统、菜单、页面、业务对象，定位：

- `.memory/modules/<module-name>/`

进入模块后，按顺序读取：

1. `README.md`：了解模块用途、入口和适用范围
2. `objects.md`：了解页面对象、字段、按钮、弹窗和关键业务对象
3. `guide.md`：了解稳定执行流程
4. `known_issues.md`：遇到失败或异常时读取
5. `cases/INDEX.md`：需要历史经验时读取，再打开具体案例文件

## 通用 skill 使用规则

如果问题属于通用 Web 操作对象，例如：

- 表单字段
- 下拉框
- 日期控件
- radio / checkbox
- textarea
- 弹窗
- toast
- iframe
- 文件上传
- 隐藏 DOM 元素
- 截图与断言

优先读取 test-web-execution skill 中对应的操作对象规则。

## 记忆优先级

用户当前指令 > 当前测试用例 > 项目模块记忆 > .memory/shared > 通用 test-web-execution skill > 模型常识。

## 新经验沉淀规则

调试完成后，应调用 memory-organizer skill 整理执行经验：

- 当前项目特有经验：写入 `.memory/modules/<module>/`
- 跨模块项目经验：写入 `.memory/shared/`
- 单次执行过程：写入对应模块 cases/
- 可跨项目复用经验：抽取到 test-web-execution skill
