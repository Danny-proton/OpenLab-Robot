#!/usr/bin/env python3
"""generic_json_to_uatr.py — 通用 JSON trace → UATR 转换器。

用于把任意 JSON 格式的 trace 转成 UATR。用户在 adapter yaml 里
配置字段映射规则。

用法:
  python generic_json_to_uatr.py --input raw.jsonl --out uatr.jsonl \\
      --mapping '{"event": "event_type", "ts": "timestamp", ...}'
  python generic_json_to_uatr.py --input raw.jsonl --out uatr.jsonl \\
      --config adapters/generic_to_uatr.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import common as C  # noqa: E402


def convert(raw: dict, mapping: dict, framework: str = "generic") -> dict:
    """按 mapping 把 raw 事件转成 UATR。

    mapping 格式：
      {
        "event_type": "eventType",        # raw 字段名 -> UATR 字段名
        "timestamp": "ts",
        "tool_name": "tool",
        ...
      }
    键是 UATR 字段，值是 raw 字段路径（支持 dot-path）。
    """
    uatr: dict = {
        "schema_version": C.UATR_SCHEMA_VERSION,
        "framework": framework,
        "source": "generic_adapter",
        "status": "success",
    }

    def get_path(obj, path: str):
        cur = obj
        for p in path.split("."):
            if isinstance(cur, dict):
                cur = cur.get(p)
            else:
                return None
        return cur

    for uatr_field, raw_path in mapping.items():
        val = get_path(raw, raw_path)
        if val is not None:
            uatr[uatr_field] = val

    # 必填字段补全
    uatr.setdefault("run_id", raw.get("run_id", ""))
    uatr.setdefault("case_id", raw.get("case_id", ""))
    uatr.setdefault("case_run_id", raw.get("case_run_id", ""))
    uatr.setdefault("timestamp", raw.get("ts") or raw.get("timestamp") or C.now_iso())
    uatr.setdefault("event_type", "planner.step")
    uatr.setdefault("status", raw.get("status", "success"))

    # 把 raw 里所有未映射的字段塞到 attributes
    attrs = {}
    for k, v in raw.items():
        if k not in mapping.values() and k not in uatr:
            attrs[k] = v
    if attrs:
        uatr["attributes"] = attrs

    return uatr


def convert_file(input_path: Path, output_path: Path, mapping: dict) -> tuple[int, int]:
    events = C.load_jsonl(input_path)
    valid, invalid = [], []
    for raw in events:
        uatr = convert(raw, mapping)
        errs = C.validate_event(uatr)
        if errs:
            uatr["_validation_errors"] = errs
            invalid.append(uatr)
        else:
            valid.append(uatr)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for ev in valid:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return len(valid), len(invalid)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out")
    ap.add_argument("--mapping", help="JSON 字符串形式的字段映射")
    ap.add_argument("--config", help="YAML 配置文件，含 mapping 字段")
    ap.add_argument("--framework", default="generic")
    args = ap.parse_args()

    if args.config:
        cfg = C.load_yaml(Path(args.config))
        mapping = cfg.get("mapping", {})
    elif args.mapping:
        mapping = json.loads(args.mapping)
    else:
        ap.error("--mapping 或 --config 必填")

    p = Path(args.input)
    if not p.exists():
        sys.stderr.write(f"文件不存在: {p}\n")
        return 2

    if not args.out:
        # check 模式
        events = C.load_jsonl(p)
        n_valid, n_invalid = 0, 0
        for raw in events:
            uatr = convert(raw, mapping, args.framework)
            if C.validate_event(uatr):
                n_invalid += 1
            else:
                n_valid += 1
        print(f"valid={n_valid} invalid={n_invalid}")
        return 0 if n_invalid == 0 else 1

    n_valid, n_invalid = convert_file(Path(args.input), Path(args.out), mapping)
    print(f"converted: valid={n_valid} invalid={n_invalid}")
    print(f"output: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
