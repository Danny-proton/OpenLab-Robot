#!/usr/bin/env python3
"""case_io.py — YAML case 读写工具（纯 IO，不调 LLM）。

子 skill 的 Agent 生成维度/用例后，通过本脚本写入 YAML。
agent-eval 的 eval_runner 直接读这些 YAML 执行。

用法:
  # 写需求分析
  python case_io.py write-requirements --output requirements.yaml --json '{"dimensions":[...]}'

  # 读需求分析
  python case_io.py read-requirements --input requirements.yaml

  # 写测试用例（agent-eval 格式）
  python case_io.py write-cases --output cases/train.yaml --json '{"cases":[...]}'

  # 读测试用例
  python case_io.py read-cases --input cases/train.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("[ERROR] PyYAML 未安装: pip install pyyaml\n")
    sys.exit(1)


def main() -> int:
    ap = argparse.ArgumentParser(description="YAML case IO 工具")
    sub = ap.add_subparsers(dest="command")

    # write-requirements
    p1 = sub.add_parser("write-requirements")
    p1.add_argument("--output", required=True)
    p1.add_argument("--json", required=True, help="JSON 字符串")

    # read-requirements
    p2 = sub.add_parser("read-requirements")
    p2.add_argument("--input", required=True)

    # write-cases
    p3 = sub.add_parser("write-cases")
    p3.add_argument("--output", required=True)
    p3.add_argument("--json", required=True)

    # read-cases
    p4 = sub.add_parser("read-cases")
    p4.add_argument("--input", required=True)

    args = ap.parse_args()

    if args.command == "write-requirements":
        data = json.loads(args.json)
        output = {
            "dimensions": data.get("dimensions", []),
            "scenarios": data.get("scenarios", []),
        }
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            yaml.safe_dump(output, f, allow_unicode=True, sort_keys=False)
        print(json.dumps({
            "status": "ok", "file": args.output,
            "dimensions": len(output["dimensions"]),
            "scenarios": len(output["scenarios"]),
        }, ensure_ascii=False))

    elif args.command == "read-requirements":
        with open(args.input, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        print(json.dumps(data, ensure_ascii=False, indent=2))

    elif args.command == "write-cases":
        data = json.loads(args.json)
        cases = data.get("cases", [])
        output = {"cases": cases}
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            yaml.safe_dump(output, f, allow_unicode=True, sort_keys=False)
        print(json.dumps({
            "status": "ok", "file": args.output, "count": len(cases),
        }, ensure_ascii=False))

    elif args.command == "read-cases":
        with open(args.input, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        print(json.dumps(data, ensure_ascii=False, indent=2))

    else:
        ap.print_help()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
