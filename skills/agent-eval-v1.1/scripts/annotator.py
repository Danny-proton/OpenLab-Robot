#!/usr/bin/env python3
"""annotator.py — 标注数据 CRUD：加载/保存/校验/导出标注结果。

用法:
  python annotator.py --config .agent-eval/config.yaml --load
  python annotator.py --config .agent-eval/config.yaml --validate
  python annotator.py --config .agent-eval/config.yaml --stats
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class GroundTruth:
    decision: str = ""
    risk_level: str = ""
    sop_complete: Optional[bool] = None
    extra: dict = field(default_factory=dict)


@dataclass
class QualityLabels:
    passed: Optional[bool] = None
    reason: str = ""
    bv_decision_accuracy: Optional[int] = None  # 1-5
    bv_sop_completeness: Optional[int] = None
    bv_customer_experience: Optional[int] = None
    bv_terminology_accuracy: Optional[int] = None
    rc_risk_classification: Optional[int] = None
    # N 维度的动态字段
    extra: dict = field(default_factory=dict)


@dataclass
class HumanFeedback:
    approved: Optional[bool] = None
    suggestion: str = ""


@dataclass
class Annotation:
    run_id: str = ""
    case_id: str = ""
    annotator: str = ""
    timestamp: str = ""
    ground_truth: dict = field(default_factory=lambda: asdict(GroundTruth()))
    quality_labels: dict = field(default_factory=lambda: asdict(QualityLabels()))
    human_feedback: dict = field(default_factory=lambda: asdict(HumanFeedback()))


# 3+N 维度的子指标名称列表
THREE_N_SUB_METRICS = [
    "bv_decision_accuracy",
    "bv_sop_completeness",
    "bv_customer_experience",
    "bv_terminology_accuracy",
    "rc_risk_classification",
]


def annotation_path(cfg: C.EvalConfig) -> Path:
    return cfg.root / "annotations.jsonl"


def load_annotations(cfg: C.EvalConfig) -> list[dict]:
    return C.load_jsonl(annotation_path(cfg))


def load_annotations_by_case(cfg: C.EvalConfig) -> dict[str, list[dict]]:
    """返回 {case_id: [annotation, ...]}"""
    all_ann = load_annotations(cfg)
    by_case: dict[str, list[dict]] = {}
    for a in all_ann:
        cid = a.get("case_id", "")
        by_case.setdefault(cid, []).append(a)
    return by_case


def save_annotation(cfg: C.EvalConfig, ann: dict) -> None:
    """追加一条标注到 annotations.jsonl"""
    if not ann.get("timestamp"):
        ann["timestamp"] = C.now_iso()
    C.append_jsonl(annotation_path(cfg), ann)


def save_annotations_batch(cfg: C.EvalConfig, annotations: list[dict]) -> None:
    """批量保存标注"""
    for ann in annotations:
        save_annotation(cfg, ann)


def validate_annotation(ann: dict) -> list[str]:
    """校验标注数据，返回错误列表。空列表表示合法。"""
    errs: list[str] = []
    if not ann.get("case_id"):
        errs.append("缺少 case_id")
    if not ann.get("annotator"):
        errs.append("缺少 annotator")
    if not ann.get("run_id"):
        errs.append("缺少 run_id")

    gt = ann.get("ground_truth", {})
    ql = ann.get("quality_labels", {})

    # 校验 ground_truth.decision
    if gt.get("decision") and gt["decision"] not in ("approve", "reject", "review", "pending", ""):
        errs.append(f"ground_truth.decision 值无效: {gt['decision']!r}")

    # 校验 ground_truth.risk_level
    if gt.get("risk_level") and gt["risk_level"] not in ("high", "medium", "low", ""):
        errs.append(f"ground_truth.risk_level 值无效: {gt['risk_level']!r}")

    # 校验 1-5 分制
    for key in THREE_N_SUB_METRICS:
        val = ql.get(key)
        if val is not None:
            if not isinstance(val, int) or val < 1 or val > 5:
                errs.append(f"quality_labels.{key} 必须是 1-5 的整数，当前: {val!r}")

    # 校验 N 维度自定义指标
    for key, val in ql.get("extra", {}).items():
        if not isinstance(val, (int, float)) or val < 0 or val > 5:
            errs.append(f"quality_labels.extra.{key} 必须是 0-5 的数值，当前: {val!r}")

    return errs


def get_annotation_stats(cfg: C.EvalConfig, cases: list[dict]) -> dict:
    """返回标注统计信息。"""
    by_case = load_annotations_by_case(cfg)
    total_cases = len(cases)
    annotated_cases = set()
    annotators = set()
    risk_distribution = {"high": 0, "medium": 0, "low": 0}
    dimension_counts: dict[str, int] = {}
    pass_fail = {"pass": 0, "fail": 0, "pending": 0}

    for case in cases:
        cid = case.get("id", "")
        if cid in by_case:
            annotated_cases.add(cid)
            for ann in by_case[cid]:
                annotators.add(ann.get("annotator", ""))
                gt = ann.get("ground_truth", {})
                if gt.get("risk_level") in risk_distribution:
                    risk_distribution[gt["risk_level"]] += 1
                ql = ann.get("quality_labels", {})
                if ql.get("passed") is True:
                    pass_fail["pass"] += 1
                elif ql.get("passed") is False:
                    pass_fail["fail"] += 1
                else:
                    pass_fail["pending"] += 1

    # 从 cases 中统计维度
    for case in cases:
        for dim in case.get("dimensions", []) or []:
            dimension_counts[dim] = dimension_counts.get(dim, 0) + 1

    return {
        "total_cases": total_cases,
        "annotated_count": len(annotated_cases),
        "unannotated_count": total_cases - len(annotated_cases),
        "progress_percent": round(len(annotated_cases) / total_cases * 100, 1) if total_cases > 0 else 0,
        "annotators": sorted(annotators),
        "risk_distribution": risk_distribution,
        "dimension_counts": dimension_counts,
        "pass_fail": pass_fail,
    }


def get_annotation_for_case(cfg: C.EvalConfig, case_id: str) -> Optional[dict]:
    """获取指定 case 的最新标注。"""
    by_case = load_annotations_by_case(cfg)
    anns = by_case.get(case_id, [])
    if not anns:
        return None
    return anns[-1]  # 返回最新一条


def merge_annotation(existing: dict, update: dict) -> dict:
    """合并更新到现有标注（深度合并）。"""
    merged = dict(existing)
    for k, v in update.items():
        if k in ("ground_truth", "quality_labels", "human_feedback") and isinstance(v, dict):
            merged[k] = dict(merged.get(k, {}))
            merged[k].update(v)
        else:
            merged[k] = v
    merged["timestamp"] = C.now_iso()
    return merged


def main() -> int:
    ap = argparse.ArgumentParser(description="标注数据管理")
    ap.add_argument("--config", required=True)
    ap.add_argument("--load", action="store_true", help="加载并输出所有标注")
    ap.add_argument("--validate", action="store_true", help="校验标注数据")
    ap.add_argument("--stats", action="store_true", help="输出标注统计")
    ap.add_argument("--split", default="train", help="用例 split")
    ap.add_argument("--export", help="导出标注到 JSON 文件")
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())
    cases = C.load_yaml(cfg.cases_dir / f"{args.split}.yaml").get("cases", [])

    if args.validate:
        anns = load_annotations(cfg)
        n_err = 0
        for i, ann in enumerate(anns):
            errs = validate_annotation(ann)
            if errs:
                n_err += 1
                print(f"  [{i+1}] case={ann.get('case_id')} errors: {errs}")
        print(f"[annotator] 校验完成: {len(anns)} 条标注, {n_err} 条有误")
        return 0

    if args.stats:
        stats = get_annotation_stats(cfg, cases)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return 0

    if args.load:
        anns = load_annotations(cfg)
        print(json.dumps(anns, ensure_ascii=False, indent=2))
        return 0

    if args.export:
        anns = load_annotations(cfg)
        out = Path(args.export)
        C.write_json(out, anns)
        print(f"[annotator] 已导出 {len(anns)} 条标注到 {out}")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())