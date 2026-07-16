# 项目测试执行记忆库

本目录存放当前项目的测试执行记忆。一个工作区只对应一个测试项目。

## 目录结构

```
.memory/
├── README.md                    # 记忆库总览和归档原则
│
├── shared/
│   ├── README.md                # shared 目录说明
│   ├── execution_rules.md       # 项目级执行规则（页签管理、工具优先级、证据采集）
│   ├── environment.md           # 项目环境信息（系统入口、项目信息、账号引用）
│   ├── data_rules.md            # 项目级测试数据规则
│   └── cross_module_flows.md    # 跨模块业务流程
│
└── modules/
    └── <module-name>/           # 每个业务模块一个目录
        ├── README.md            # 模块用途、适用场景、入口、前置条件
        ├── objects.md           # 页面对象、字段、按钮、弹窗说明
        ├── guide.md             # 模块内的稳定操作流程
        ├── known_issues.md      # 该模块已知问题和恢复方法
        └── cases/
            ├── INDEX.md         # 历史案例摘要索引
            ├── case-template.md # 案例文件模板（复制此文件并填充内容）
            └── YYYYMMDD-HHMMSS_<case-id>_<topic>.md  # 单次执行案例
```

- shared/：项目内跨模块复用的规则、环境、数据和跨模块流程
- modules/：按被测系统业务模块组织的模块级记忆
- modules/`<module>`/cases/：模块历史执行案例，一次执行一个文件

## 归档原则

1. 项目特有知识进入 memory。
2. 跨模块规则进入 shared。
3. 模块入口、对象、流程、问题进入对应 modules/`<module>`/。
4. 单次执行过程进入 cases/。
5. 可跨项目复用的执行方法抽取到通用 test-web-execution skill。
6. 账号密码不直接写入正文，使用 secret 引用。
