#!/usr/bin/env python3
"""memory_kb.py — KnowledgeCycle 记忆系统。

在 .agent-eval/.memory/ 目录中读写评测记忆。
格式兼容 Claude Code memory Markdown + frontmatter。

用法:
  python memory_kb.py --remember preference --key model --value claude-sonnet-4
  python memory_kb.py --recall preference
  python memory_kb.py --remember best-practice --key "F8 fix" --value "reference 注入最有效"
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


def memory_dir(cfg: C.EvalConfig) -> Path:
    """返回记忆目录，不存在则创建。"""
    d = cfg.root / ".memory"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slugify(s: str) -> str:
    """把 key 转成文件名安全的 slug。"""
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s)
    return s[:64] or "untitled"


def remember(cfg: C.EvalConfig, category: str, key: str, value: str) -> Path:
    """写入一条记忆。"""
    d = memory_dir(cfg)
    name = f"{category}-{_slugify(key)}"
    path = d / f"{name}.md"
    content = f"""---
name: {name}
description: {category} — {key}
metadata:
  type: project
---

- **{key}**: {value}
- **category**: {category}
- **updated**: auto
"""
    path.write_text(content, encoding="utf-8")
    return path


def recall(cfg: C.EvalConfig, category: str | None = None) -> list[dict]:
    """召回记忆。"""
    d = memory_dir(cfg)
    out: list[dict] = []
    for p in sorted(d.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        end = text.find("---", 3)
        if end == -1:
            continue
        fm = text[3:end].strip()
        body = text[end + 3:].strip()
        meta: dict = {}
        for line in fm.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        if category and not p.name.startswith(f"{category}-"):
            continue
        out.append({
            "path": str(p.relative_to(cfg.root)),
            "name": meta.get("name", p.stem),
            "description": meta.get("description", ""),
            "body": body,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=".agent-eval/config.yaml")
    ap.add_argument("--remember", metavar="CATEGORY")
    ap.add_argument("--recall", metavar="CATEGORY", nargs="?", const="")
    ap.add_argument("--key")
    ap.add_argument("--value")
    args = ap.parse_args()

    cfg_path = Path(args.config).resolve()
    if not cfg_path.exists():
        print(f"config 不存在: {cfg_path}", file=sys.stderr)
        return 1
    cfg = C.EvalConfig.load(cfg_path)

    if args.remember:
        if not args.key or not args.value:
            print("--remember 需要同时指定 --key 和 --value", file=sys.stderr)
            return 1
        path = remember(cfg, args.remember, args.key, args.value)
        print(f"已写入记忆: {path}")
        return 0

    if args.recall is not None:
        items = recall(cfg, args.recall or None)
        for it in items:
            print(f"--- {it['name']} ---")
            print(it["description"])
            print(it["body"])
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
