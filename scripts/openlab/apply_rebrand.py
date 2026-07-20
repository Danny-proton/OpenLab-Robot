#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Openlab Robot 品牌改造脚本（幂等）。

用途：
  1. 首次将 cc-haha 上游代码改造为 Openlab Robot 品牌。
  2. 后续 cc-haha 上游更新合并后，重新运行本脚本即可机械性重放品牌替换。

用法：
  python3 scripts/openlab/apply_rebrand.py          # 应用替换
  python3 scripts/openlab/apply_rebrand.py --check  # 只检查还有哪些命中未替换

规则说明：
  - 所有规则都是 (相对路径, 旧字符串, 新字符串)，按文件精确替换，幂等。
  - 上游更新后若某条规则的旧字符串找不到，脚本会提示 MISS，
    需要人工核对该处是否被上游改动（见 scripts/openlab/REBRAND_CHECKLIST.md）。
  - 环境变量名（CLAUDE_* / CC_HAHA_* / ANTHROPIC_*）按需求保持不变。
  - docs/、release-notes/、LICENSE、THIRD_PARTY_LICENSES.md 不在替换范围内。
"""

from __future__ import annotations

import argparse
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GITEE_REPO = "https://gitee.com/HongKongJournalist/OpenLab-Robot"
JIUWEN_REPO = "https://atomgit.com/openJiuwen/jiuwenswarm"

# ─── 规则表 ──────────────────────────────────────────────────────────────────
# (文件, 旧, 新)。同一文件多条规则按顺序应用。
RULES: list[tuple[str, str, str]] = [
    # ── 1. 应用标识 / 安装包名 ──
    ("desktop/package.json", '"name": "claude-code-desktop"', '"name": "openlab-robot-desktop"'),
    ("desktop/package.json", '"description": "Desktop coding agent workbench for Claude Code Haha."',
     '"description": "Desktop coding agent workbench for Openlab Robot."'),
    ("desktop/package.json", '"homepage": "https://github.com/NanmiCoder/cc-haha"', f'"homepage": "{GITEE_REPO}"'),
    ("desktop/package.json", '"appId": "com.claude-code-haha.desktop"', '"appId": "com.openlab.robot"'),
    ("desktop/package.json", '"productName": "Claude Code Haha"', '"productName": "Openlab Robot"'),
    ("desktop/package.json", '"artifactName": "Claude-Code-Haha-${version}-${os}-${arch}.${ext}"',
     '"artifactName": "Openlab-Robot-${version}-${os}-${arch}.${ext}"'),
    ("desktop/src-tauri/tauri.conf.json", '"productName": "Claude Code Haha"', '"productName": "Openlab Robot"'),
    ("desktop/src-tauri/tauri.conf.json", '"identifier": "com.claude-code-haha.desktop"', '"identifier": "com.openlab.robot"'),
    ("desktop/src-tauri/tauri.conf.json", '"title": "Claude Code Haha"', '"title": "Openlab Robot"'),
    ("desktop/src-tauri/tauri.conf.json",
     '"https://github.com/NanmiCoder/cc-haha/releases/latest/download/latest.json"',
     f'"{GITEE_REPO}/releases/latest/download/latest.json"'),
    ("desktop/src-tauri/tauri.macos.conf.json", '"title": "Claude Code Haha"', '"title": "Openlab Robot"'),
    ("desktop/src-tauri/tauri.windows.conf.json", '"title": "Claude Code Haha"', '"title": "Openlab Robot"'),
    ("desktop/index.html", "<title>Claude Code Haha</title>", "<title>Openlab Robot</title>"),
    ("desktop/electron/services/appIdentity.ts",
     "export const WINDOWS_APP_USER_MODEL_ID = 'com.claude-code-haha.desktop'",
     "export const WINDOWS_APP_USER_MODEL_ID = 'com.openlab.robot'"),
    ("desktop/electron/services/tray.ts", "tray.setToolTip(app.name || 'Claude Code Haha')",
     "tray.setToolTip(app.name || 'Openlab Robot')"),
    ("desktop/electron/services/tray.ts", "{ label: 'Show Claude Code Haha', click: show }",
     "{ label: 'Show Openlab Robot', click: show }"),
    ("desktop/electron/services/tray.ts", "{ label: 'Quit Claude Code Haha', click: quit }",
     "{ label: 'Quit Openlab Robot', click: quit }"),
    ("desktop/electron/services/menu.ts", "app.name || 'Claude Code Haha'", "app.name || 'Openlab Robot'"),

    # ── 2. 根 package.json ──
    ("package.json", '"name": "claude-code-local"', '"name": "openlab-robot"'),
    ("package.json", '"claude-haha": "./bin/claude-haha"',
     '"openlab-robot": "./bin/openlab-robot",\n    "jiuwen": "./bin/jiuwen",\n    "claude-haha": "./bin/claude-haha"'),

    # ── 3. 关于页 / 默认资料 ──
    ("desktop/src/pages/Settings.tsx",
     "const GITHUB_REPO = 'https://github.com/NanmiCoder/cc-haha'",
     f"const GITHUB_REPO = '{GITEE_REPO}'"),
    ("desktop/src/pages/Settings.tsx",
     'alt="Claude Code Haha"', 'alt="Openlab Robot"'),
    ("desktop/src/pages/Settings.tsx",
     '<h1 className="text-xl font-bold text-[var(--color-text-primary)]">Claude Code Haha</h1>',
     '<h1 className="text-xl font-bold text-[var(--color-text-primary)]">Openlab Robot</h1>'),
    ("desktop/src/pages/Settings.tsx",
     '<div className="text-sm font-medium text-[var(--color-text-primary)]">NanmiCoder/cc-haha</div>',
     '<div className="text-sm font-medium text-[var(--color-text-primary)]">HongKongJournalist/OpenLab-Robot</div>'),
    ("src/server/services/desktopUiPreferencesService.ts",
     "const DEFAULT_PROFILE_SUBTITLE = 'github.com/NanmiCoder/cc-haha'",
     "const DEFAULT_PROFILE_SUBTITLE = 'gitee.com/HongKongJournalist/OpenLab-Robot'"),

    # ── 4. i18n：供应商选项卡改名“大模型” ──
    ("desktop/src/i18n/locales/zh.ts", "'settings.tab.providers': '服务商'", "'settings.tab.providers': '大模型'"),
    ("desktop/src/i18n/locales/zh-TW.ts", "'settings.tab.providers': '服務商'", "'settings.tab.providers': '大模型'"),
    ("desktop/src/i18n/locales/en.ts", "'settings.tab.providers': 'Providers'", "'settings.tab.providers': 'Models'"),
    ("desktop/src/i18n/locales/jp.ts", "'settings.tab.providers': 'プロバイダー'", "'settings.tab.providers': 'モデル'"),
    ("desktop/src/i18n/locales/kr.ts", "'settings.tab.providers': '공급자'", "'settings.tab.providers': '모델'"),
    ("desktop/src/i18n/locales/zh.ts", "'settings.providers.title': '服务商'", "'settings.providers.title': '大模型'"),
    ("desktop/src/i18n/locales/zh-TW.ts", "'settings.providers.title': '服務商'", "'settings.providers.title': '大模型'"),
    ("desktop/src/i18n/locales/en.ts", "'settings.providers.title': 'Providers'", "'settings.providers.title': 'Models'"),
    ("desktop/src/i18n/locales/jp.ts", "'settings.providers.title': 'プロバイダー'", "'settings.providers.title': 'モデル'"),
    ("desktop/src/i18n/locales/kr.ts", "'settings.providers.title': '공급자'", "'settings.providers.title': '모델'"),

    # ── 5. TUI 欢迎语 ──
    ("src/components/LogoV2/WelcomeV2.tsx", 'welcomeMessage="Welcome to Claude Code"',
     'welcomeMessage="Welcome to Openlab Robot"'),
    ("src/components/LogoV2/WelcomeV2.tsx", '{"Welcome to Claude Code"}', '{"Welcome to Openlab Robot"}'),
    ("src/components/LogoV2/LogoV2.tsx", '("Claude Code")', '("Openlab Robot")'),
    ("src/components/LogoV2/LogoV2.tsx", '(" Claude Code ")', '(" Openlab Robot ")'),

    # ── 6. System prompt 身份 ──
    ("src/constants/system.ts",
     "const DEFAULT_PREFIX = `You are Claude Code, Anthropic's official CLI for Claude.`",
     "const DEFAULT_PREFIX = `You are Openlab Robot, an AI coding assistant.`"),
    ("src/constants/system.ts",
     "const AGENT_SDK_CLAUDE_CODE_PRESET_PREFIX = `You are Claude Code, Anthropic's official CLI for Claude, running within the Claude Agent SDK.`",
     "const AGENT_SDK_CLAUDE_CODE_PRESET_PREFIX = `You are Openlab Robot, an AI coding assistant, running within the Openlab Agent SDK.`"),
    ("src/constants/system.ts",
     "const AGENT_SDK_PREFIX = `You are a Claude agent, built on Anthropic's Claude Agent SDK.`",
     "const AGENT_SDK_PREFIX = `You are an Openlab Robot agent, built on the Openlab Agent SDK.`"),
    ("src/constants/prompts.ts",
     "`You are Claude Code, Anthropic's official CLI for Claude.\\n\\nCWD: ${getCwd()}\\nDate: ${getSessionStartDate()}`",
     "`You are Openlab Robot, an AI coding assistant.\\n\\nCWD: ${getCwd()}\\nDate: ${getSessionStartDate()}`"),
    ("src/constants/prompts.ts",
     "export const DEFAULT_AGENT_PROMPT = `You are an agent for Claude Code, Anthropic's official CLI for Claude.",
     "export const DEFAULT_AGENT_PROMPT = `You are an agent for Openlab Robot, an AI coding assistant."),
    ("src/constants/prompts.ts",
     "`/help: Get help with using Claude Code`",
     "`/help: Get help with using Openlab Robot`"),

    # ── 7. 外部链接 → jiuwen ──
    ("src/components/HelpV2/HelpV2.tsx", "https://code.claude.com/docs/en/overview", JIUWEN_REPO),
    ("src/components/TrustDialog/TrustDialog.tsx", "https://code.claude.com/docs/en/security", JIUWEN_REPO),
    ("src/components/BypassPermissionsModeDialog.tsx", "https://code.claude.com/docs/en/security", JIUWEN_REPO),
    ("src/components/CostThresholdDialog.tsx", "https://code.claude.com/docs/en/costs", JIUWEN_REPO),
    ("src/components/sandbox/SandboxSettings.tsx", "https://code.claude.com/docs/en/sandboxing", JIUWEN_REPO),
    ("src/components/sandbox/SandboxOverridesTab.tsx", "https://code.claude.com/docs/en/sandboxing#configure-sandboxing", JIUWEN_REPO),
    ("src/keybindings/template.ts", "https://code.claude.com/docs/en/keybindings", JIUWEN_REPO),
    ("src/components/RemoteEnvironmentDialog.tsx", "https://claude.ai/code", JIUWEN_REPO),
    ("src/components/FeedbackSurvey/TranscriptSharePrompt.tsx",
     "https://code.claude.com/docs/en/data-usage#session-quality-surveys", JIUWEN_REPO),
    ("src/components/SlashLoginFlow.tsx", "https://code.claude.com/docs/en/amazon-bedrock", JIUWEN_REPO),
    ("src/components/SlashLoginFlow.tsx", "https://code.claude.com/docs/en/microsoft-foundry", JIUWEN_REPO),
    ("src/constants/prompts.ts", "https://code.claude.com/docs/en/claude_code_docs_map.md", JIUWEN_REPO),
]


def apply_file(path: str, pairs: list[tuple[str, str]], check_only: bool) -> list[str]:
    msgs: list[str] = []
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        msgs.append(f"MISS-FILE  {path}")
        return msgs
    with io.open(full, encoding="utf-8") as f:
        content = f.read()
    for old, new in pairs:
        if new in content:
            continue  # 已替换，幂等跳过
        if old not in content:
            msgs.append(f"MISS-RULE  {path}  ::  {old[:70]}")
            continue
        if check_only:
            msgs.append(f"PENDING    {path}  ::  {old[:70]}")
            continue
        content = content.replace(old, new)
        msgs.append(f"OK         {path}  ::  {old[:60]} -> {new[:40]}")
    if not check_only:
        with io.open(full, "w", encoding="utf-8", newline="") as f:
            f.write(content)
    return msgs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只检查不写入")
    args = parser.parse_args()

    by_file: dict[str, list[tuple[str, str]]] = {}
    for path, old, new in RULES:
        by_file.setdefault(path, []).append((old, new))

    misses = 0
    for path, pairs in by_file.items():
        for msg in apply_file(path, pairs, args.check):
            print(msg)
            if msg.startswith("MISS"):
                misses += 1
    print(f"\n共 {len(RULES)} 条规则，MISS {misses} 条。")
    return 0 if misses == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
