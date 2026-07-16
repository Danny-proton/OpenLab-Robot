---
system_url: <URL>
username: <账号>
password: <密码>
test_scope: <范围>
captcha_strategy: <none | graphic | sms | unknown>
language_pack:
  available: <true | false>
  root_path: <路径，若 available=true>
  format: <JSON | JS | YAML | PO | XLIFF | CSV | other>
  languages: [zh-CN, en-US]
  organization: <by_lang | by_module | single_file>
---

# 项目环境信息

## 系统入口

| 系统 | 用途 | 地址 |
|------|------|------|
| <系统名> | <用途描述> | <URL> |

## 项目信息

| 项目 | 说明 |
|------|------|
| 项目名称 | <项目名称> |
| 访问方式 | <访问方式描述> |

## 账号引用

| 系统 | 账号用途 | 用户名 |
|------|---------|--------|
| <系统名> | <账号用途> | <用户名> |

## 登录策略（v1.1）

- **验证码类型**: <none | graphic | sms | unknown>
- **登录方式**: <自动 | 半自动（验证码处暂停等待人工）>
- **登录后预期**: <跳转 URL 或登录态元素，用于验证登录成功>

## 语言包信息（v1.1）

- **是否提供**: <是 | 否>
- **根目录路径**: <路径>
- **文件格式**: <JSON | JS | YAML | PO | XLIFF | CSV | other>
- **支持语言**: <语言列表>
- **文件组织方式**: <by_lang | by_module | single_file>
- **示例文件**: <路径（可选）>
