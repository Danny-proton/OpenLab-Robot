#!/usr/bin/env python3
"""patch_manager.py — 多优化器候选 patch 管理器。

v1 可能有多个优化器同时生成候选：
- rule_based mutator（v0/v0.5 已有）
- deepeval PromptOptimizer
- opik MetaPrompt / HRPO / GEPA

本脚本统一管理这些候选，去重、排序、提交给 Gatekeeper 验证。

用法:
  python patch_manager.py --config .agent-eval/config.yaml --run <run_id> --collect
  python patch_manager.py --config .agent-eval/config.yaml --run <run_id> --rank
  python patch_manager.py --config .agent-eval/config.yaml --accept <patch_id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


def collect_candidates(cfg: C.EvalConfig, run_id: str) -> list[dict]:
    """从多个来源收集 candidate patch。"""
    candidates = []

    # 1. rule_based mutator 生成的
    for p in sorted((cfg.patches_dir).glob("candidate_*.md")):
        candidates.append({
            "patch_id": p.stem,
            "source": "rule_based",
            "path": str(p.relative_to(cfg.root)),
            "size_bytes": p.stat().st_size,
        })

    # 2. deepeval 生成的（如果 .deepeval.json 存在）
    deepeval_path = cfg.scores_dir / f"{run_id}.deepeval.json"
    if deepeval_path.exists():
        deepeval_data = json.loads(deepeval_path.read_text(encoding="utf-8"))
        # deepeval PromptOptimizer 可能生成优化后的 prompt
        # 这里简化：把 deepeval 结果作为参考候选
        candidates.append({
            "patch_id": f"deepeval_{run_id}",
            "source": "deepeval",
            "path": str(deepeval_path.relative_to(cfg.root)),
            "size_bytes": deepeval_path.stat().st_size,
            "expected_improvement": 0.05,
        })

    # 3. opik 生成的（如果有）
    for p in sorted((cfg.scores_dir).glob(f"{run_id}.opik_*.json")):
        opik_data = json.loads(p.read_text(encoding="utf-8"))
        candidates.append({
            "patch_id": p.stem,
            "source": "opik",
            "optimizer": opik_data.get("optimizer", "unknown"),
            "path": str(p.relative_to(cfg.root)),
            "size_bytes": p.stat().st_size,
            "expected_improvement": opik_data.get("expected_improvement", 0),
        })

    return candidates


def rank_candidates(candidates: list[dict], diagnosis: dict | None) -> list[dict]:
    """给候选排序。优先级：rule_based > deepeval > opik（按 expected_improvement）。"""
    type_priority = {"rule_based": 0, "deepeval": 1, "opik": 2}

    def key(c: dict) -> tuple:
        return (
            type_priority.get(c.get("source", ""), 99),
            -c.get("expected_improvement", 0),
            c.get("patch_id", ""),
        )

    return sorted(candidates, key=key)


def accept_patch(cfg: C.EvalConfig, patch_id: str) -> dict:
    """接受一个 patch：记录到 accepted_patches.md。"""
    accepted_log = cfg.reports_dir / "accepted_patches.md"
    accepted_log.parent.mkdir(parents=True, exist_ok=True)

    # 读取现有内容
    existing = ""
    if accepted_log.exists():
        existing = accepted_log.read_text(encoding="utf-8")

    # 追加新记录
    entry = f"""
## {C.now_iso()} accept {patch_id}

- patch_id: `{patch_id}`
- accept_time: {C.now_iso()}
- note: accepted via patch_manager.py
"""
    accepted_log.write_text(existing + entry, encoding="utf-8")
    return {"patch_id": patch_id, "accepted": True, "log": str(accepted_log.relative_to(cfg.root))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--run")
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--rank", action="store_true")
    ap.add_argument("--accept", help="接受指定 patch_id")
    ap.add_argument("--out", help="输出 JSON 路径")
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())

    if args.accept:
        result = accept_patch(cfg, args.accept)
        print(f"[patch_manager] accepted: {result['patch_id']}")
        print(f"[patch_manager] log: {result['log']}")
        return 0

    if not args.run:
        ap.error("--run 必填（除非 --accept）")

    candidates = collect_candidates(cfg, args.run)
    print(f"[patch_manager] 收集到 {len(candidates)} 个候选")

    if args.rank:
        # 加载诊断用于排序
        diagnosis = None
        diag_path = cfg.reports_dir / f"{args.run}_diagnosis.json"
        if diag_path.exists():
            diagnosis = json.loads(diag_path.read_text(encoding="utf-8"))
        candidates = rank_candidates(candidates, diagnosis)
        print(f"[patch_manager] 排序完成")

    # 输出
    out_data = {"run_id": args.run, "candidates": candidates}
    out_path = Path(args.out) if args.out else (cfg.scores_dir / f"{args.run}.candidates.json")
    C.write_json(out_path, out_data)
    print(f"[patch_manager] output: {out_path}")
    for c in candidates:
        print(f"  - {c['patch_id']} (source={c['source']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
