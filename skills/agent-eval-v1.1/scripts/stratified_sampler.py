#!/usr/bin/env python3
"""stratified_sampler.py — 组合分层比例采样。

用法:
  python stratified_sampler.py --config .agent-eval/config.yaml --split train --sample-size 50
  python stratified_sampler.py --config .agent-eval/config.yaml --split train --sample-size 50 --out sampled.yaml
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


def infer_risk_and_dimension(case: dict) -> tuple[str, list[str]]:
    """自动推断用例的风险等级和维度。

    规则：
    - 含 forbidden 工具定义 → high 风险
    - 含 business_rules → compliance 维度
    - 含 required tools → operational 维度
    - 默认 → medium 风险, functional 维度
    """
    risk = "medium"
    dimensions = ["functional"]

    expected_tools = case.get("expected_tools") or {}
    if expected_tools.get("forbidden"):
        risk = "high"

    if (case.get("business_rules") or {}).get("must_satisfy"):
        dimensions.append("compliance")

    if expected_tools.get("required"):
        dimensions.append("operational")

    return risk, list(set(dimensions))


def stratified_proportional_sample(
    cases: list[dict],
    strata_config: dict[str, int],
    sample_size: int,
    min_per_stratum: int = 1,
    seed: int | None = 42,
) -> list[dict]:
    """比例分层采样。

    Args:
        cases: 全量用例列表
        strata_config: {分层键: 业务量} 如 {"近1个月_个人贷款_高风险_北京": 120, ...}
        sample_size: 总采样数
        min_per_stratum: 每层最少样本数
        seed: 随机种子

    Returns:
        采样后的用例列表
    """
    if seed is not None:
        random.seed(seed)

    total_volume = sum(strata_config.values())
    if total_volume == 0:
        return cases[:sample_size]

    sampled: list[dict] = []
    remaining = sample_size

    # 第一轮：按比例分配，保证每层最少 1 条
    allocations: dict[str, int] = {}
    for stratum, volume in strata_config.items():
        n = max(min_per_stratum, round(sample_size * volume / total_volume))
        allocations[stratum] = n

    # 如果分配总数超过 sample_size，按比例缩减
    alloc_total = sum(allocations.values())
    if alloc_total > sample_size:
        scale = sample_size / alloc_total
        for k in allocations:
            allocations[k] = max(min_per_stratum, round(allocations[k] * scale))

    # 按层采样
    for stratum, n in allocations.items():
        stratum_cases = [c for c in cases if _get_stratum_key(c) == stratum]
        if not stratum_cases:
            continue
        actual_n = min(n, len(stratum_cases))
        sampled.extend(random.sample(stratum_cases, actual_n))

    return sampled[:sample_size]


def _get_stratum_key(case: dict) -> str:
    """获取用例的分层键。"""
    time_period = case.get("time_period", "unknown")
    loan_type = case.get("loan_type", "unknown")
    risk_level = case.get("risk_level", "unknown")
    branch = case.get("branch", "unknown")
    return f"{time_period}_{loan_type}_{risk_level}_{branch}"


def classify_time_period(case: dict, periods: list[dict]) -> str:
    """根据用例时间戳分类到时间窗口。"""
    ts = case.get("timestamp") or case.get("created_at") or ""
    if not ts:
        return periods[0]["name"] if periods else "unknown"

    try:
        case_time = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return periods[0]["name"] if periods else "unknown"

    now = datetime.now()
    for period in periods:
        window_days = period.get("window_days", 30)
        if case_time >= now - timedelta(days=window_days):
            return period["name"]

    return periods[-1]["name"] if periods else "unknown"


def prepare_sampling(
    cases: list[dict],
    sampling_config: dict,
) -> tuple[list[dict], dict[str, int]]:
    """准备采样：补充缺失字段、计算分层、返回 (enriched_cases, strata_config)。"""
    # 时间窗口配置
    time_periods = sampling_config.get("time_periods", [])
    dimensions = sampling_config.get("dimensions", ["time_period", "loan_type", "risk_level", "branch"])

    # 为每个 case 补充分层字段
    enriched = []
    for case in cases:
        c = dict(case)

        # 自动推断风险和维度（如果缺失）
        if not c.get("risk_level") or not c.get("dimensions"):
            risk, dims = infer_risk_and_dimension(c)
            c.setdefault("risk_level", risk)
            c.setdefault("dimensions", dims)

        # 时间分类
        if time_periods and not c.get("time_period"):
            c["time_period"] = classify_time_period(c, time_periods)

        enriched.append(c)

    # 构建分层配置（业务量权重，这里简化为每层 case 数量）
    strata_counts: dict[str, int] = {}
    for c in enriched:
        key = _get_stratum_key(c)
        strata_counts[key] = strata_counts.get(key, 0) + 1

    return enriched, strata_counts


def main() -> int:
    ap = argparse.ArgumentParser(description="分层采样")
    ap.add_argument("--config", required=True)
    ap.add_argument("--split", default="train")
    ap.add_argument("--sample-size", type=int, default=50)
    ap.add_argument("--out", default=None, help="输出 YAML 路径，默认打印到 stdout")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--method", default="proportional", choices=["proportional", "equal", "weighted"])
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())
    cases_raw = C.load_yaml(cfg.cases_dir / f"{args.split}.yaml").get("cases", [])

    # 读取采样配置
    raw = C.load_yaml(Path(args.config).resolve())
    sampling_config = (raw.get("stratified_sampling") or {})
    if not sampling_config.get("enabled"):
        print("[stratified_sampler] 分层采样未启用（stratified_sampling.enabled=false），返回全部用例")
        print(json.dumps({"sampled_count": len(cases_raw), "total": len(cases_raw)}, ensure_ascii=False))
        return 0

    enriched, strata_counts = prepare_sampling(cases_raw, sampling_config)
    sampled = stratified_proportional_sample(
        enriched,
        strata_counts,
        args.sample_size,
        min_per_stratum=sampling_config.get("min_samples_per_stratum", 1),
        seed=args.seed,
    )

    result = {
        "sampled_count": len(sampled),
        "total": len(cases_raw),
        "strata_count": len(strata_counts),
        "method": args.method,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.out:
        out_path = Path(args.out)
        dump_yaml({"cases": sampled}, out_path)
        print(f"[stratified_sampler] 采样结果已写入 {out_path}")
    else:
        # 打印 YAML 到 stdout
        yaml_str = C.dump_yaml_to_string({"cases": sampled})
        print(yaml_str)

    return 0


# dump_yaml_to_string 辅助
import yaml as _yaml

def _dump_yaml_to_string(obj):
    return _yaml.safe_dump(obj, allow_unicode=True, sort_keys=False)

# monkey-patch 到 common 模块
C.dump_yaml_to_string = _dump_yaml_to_string


if __name__ == "__main__":
    sys.exit(main())