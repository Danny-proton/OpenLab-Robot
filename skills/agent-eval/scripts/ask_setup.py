#!/usr/bin/env python3
"""ask_setup.py — 交互式信息收集模块。

在 agent-eval 启动时，主动收集用户信息。设计原则：
1. 优先读 config.yaml / 环境变量 / 默认值，已经有的不问
2. 缺失的关键信息必须问
3. 可选信息给默认值，用户可直接回车跳过
4. 收集完写入 config.yaml / adapter yaml，下次不再问

注意：本模块设计为可被 Claude Code 调用。当 agent-eval skill 触发时，
Claude Code 会读 SKILL.md 里的指引，调用本模块的函数收集信息，
然后用 AskUserQuestion 工具问用户。

本模块提供：
- collect_startup_info() — 首次启动信息收集
- collect_eval_info() — 评测环节信息收集
- collect_judge_info() — 多 Agent 评测信息收集
- collect_optimize_info() — 优化环节信息收集
- collect_abtest_info() — A/B 环节信息收集
- write_config() — 把收集到的信息写入 config

用法:
  # 被 eval_runner.py --interactive 调用
  python ask_setup.py --stage startup --config .agent-eval/config.yaml

  # 输出待问问题 JSON（供 Claude Code 用 AskUserQuestion 工具问用户）
  python ask_setup.py --stage startup --config .agent-eval/config.yaml --emit-questions
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


# ---------------------------------------------------------------------------
# 各环节默认值
# ---------------------------------------------------------------------------

STARTUP_DEFAULTS = {
    "adapter": "openlab_robot",  # 默认 OpenLab Robot（使用方是 cc-haha 改的）
    "openlab_bin": "",
    "anthropic_auth_token": "",  # 从环境变量读
    "anthropic_base_url": "",  # 空 = Anthropic 官方
    "anthropic_model": "claude-sonnet-4-20250514",
    "workdir": "/tmp/openlab-work",
    "permission_mode": "bypassPermissions",
    "max_turns": 20,
    "max_budget_usd": 1.0,
    "timeout_s": 600,
    "allowed_tools": [],  # 空 = 全部
}

EVAL_DEFAULTS = {
    "split": "train",
    "variant": "baseline",
    "label": "",
    "limit": None,  # None = 跑全部
}

# 多 Agent 评测：默认启动的 Judge
JUDGE_DEFAULTS = {
    # 规则型 Judge（默认全开，确定性，无 LLM 成本）
    "DomainJudge": True,
    "ToolTraceJudge": True,
    "WorkflowJudge": True,
    "FaithfulnessJudge": True,
    "RegressionJudge": True,  # 仅 A/B 模式
    "SafetyJudge": True,
    # LLM 型 Judge（默认关，需要 Claude Code 执行）
    "OptimizerPlanner": False,
    "PatchWriter": False,
    "Gatekeeper": True,  # 规则版默认开
    "ReportWriter": False,
    # 阈值
    "judge_consensus_threshold": 0.7,
    "safety_veto_forced": True,
}

OPTIMIZE_DEFAULTS = {
    "optimizer": "hrpo",  # rule_based / deepeval / opik_hrpo / opik_gepa
    "budget": "small",  # small / medium / large
    "auto_apply_reference": True,
    "auto_apply_patch": False,  # patch 改动风险高，默认不自动
    "auto_git_commit": False,
    "auto_git_rollback": True,
}

ABTEST_DEFAULTS = {
    "baseline_run_id": "",
    "candidate_patch": "",
    "split": "regression",
    "label": "candidate",
    "train_threshold": 0.03,
    "latency_max_ratio": 1.5,
}


# ---------------------------------------------------------------------------
# 首次启动信息收集
# ---------------------------------------------------------------------------

def collect_startup_info(cfg: C.EvalConfig | None = None) -> dict:
    """收集首次启动需要的信息。

    优先级：config.yaml > 环境变量 > 默认值。
    返回 dict，缺失的字段标 missing。
    """
    info = dict(STARTUP_DEFAULTS)

    # 从 config.yaml 读
    if cfg:
        adapter_name = cfg.adapter_name
        info["adapter"] = adapter_name
        if adapter_name == "openlab_robot":
            adapter_path = cfg.adapter_path()
            if adapter_path.exists():
                adapter_cfg = C.load_yaml(adapter_path)
                info["openlab_bin"] = adapter_cfg.get("bin", "")
                info["workdir"] = adapter_cfg.get("workdir", info["workdir"])
                info["permission_mode"] = adapter_cfg.get("permission_mode", info["permission_mode"])
                info["max_turns"] = adapter_cfg.get("max_turns", info["max_turns"])
                info["max_budget_usd"] = adapter_cfg.get("max_budget_usd", info["max_budget_usd"])
                info["timeout_s"] = adapter_cfg.get("timeout_s", info["timeout_s"])
                info["allowed_tools"] = adapter_cfg.get("allowed_tools", [])
                env = adapter_cfg.get("env", {})
                info["anthropic_auth_token"] = env.get("ANTHROPIC_AUTH_TOKEN", "")
                info["anthropic_base_url"] = env.get("ANTHROPIC_BASE_URL", "")
                info["anthropic_model"] = env.get("ANTHROPIC_MODEL", info["anthropic_model"])

    # 从环境变量读（覆盖 config）
    info["anthropic_auth_token"] = (
        os.environ.get("ANTHROPIC_AUTH_TOKEN") or
        os.environ.get("ANTHROPIC_API_KEY") or
        info["anthropic_auth_token"]
    )
    info["anthropic_base_url"] = os.environ.get("ANTHROPIC_BASE_URL") or info["anthropic_base_url"]
    info["anthropic_model"] = os.environ.get("ANTHROPIC_MODEL") or info["anthropic_model"]

    # 标记缺失
    missing = []
    if info["adapter"] == "openlab_robot":
        if not info["openlab_bin"]:
            missing.append("openlab_bin")
        if not info["anthropic_auth_token"]:
            missing.append("anthropic_auth_token")
    info["_missing"] = missing

    return info


def emit_startup_questions(info: dict) -> list[dict]:
    """生成首次启动的问题列表（供 AskUserQuestion 用）。

    只对 missing 的字段生成问题。
    """
    questions = []
    missing = info.get("_missing", [])

    # Q1: adapter 类型（如果 config 没指定或要让用户确认）
    questions.append({
        "question": "你要评测的 Agent 是什么类型？这决定用哪个 adapter 调用它。",
        "header": "Agent 类型",
        "type": "single",
        "options": [
            {"label": "OpenLab Robot", "description": "基于 cc-haha / Claude Code 的 agent。通过 subprocess 调 claude-haha CLI，适合评测 Claude Code skill",
             "recommended": info["adapter"] == "openlab_robot"},
            {"label": "Spring AI", "description": "Spring AI ChatClient agent。通过 HTTP 调 /api/chat，需要 Java 服务在跑",
             "recommended": info["adapter"] == "spring_ai_http"},
            {"label": "其他 HTTP", "description": "任意暴露 HTTP API 的 agent。需要自己提供 trace",
             "recommended": False},
            {"label": "Mock 测试", "description": "不用真实 agent，用内置 mock 跑通流程。适合第一次试用",
             "recommended": False},
        ],
    })

    # Q2: cc-haha binary 路径（仅 OpenLab Robot 且缺失时问）
    if "openlab_bin" in missing or info["adapter"] == "openlab_robot":
        questions.append({
            "question": "OpenLab Robot (cc-haha) 的可执行文件路径？通常是 cc-haha/bin/claude-haha",
            "header": "Binary 路径",
            "type": "single",
            "options": [
                {"label": "~/cc-haha/bin/claude-haha", "description": "默认克隆位置",
                 "recommended": True},
                {"label": "~/projects/cc-haha/bin/claude-haha", "description": "projects 目录下"},
                {"label": "PATH 中已有", "description": "claude-haha 已在 PATH，直接用命令名"},
                {"label": "自定义路径", "description": "我会输入完整路径"},
            ],
        })

    # Q3: API key（缺失时问）
    if "anthropic_auth_token" in missing:
        questions.append({
            "question": "ANTHROPIC API key 没设置。OpenLab Robot adapter 需要它调用模型。你要怎么提供？",
            "header": "API Key",
            "type": "single",
            "options": [
                {"label": "环境变量已设", "description": "我刚才 export ANTHROPIC_AUTH_TOKEN=sk-xxx 了，重新读"},
                {"label": "写入 config", "description": "我把 key 写到 .agent-eval/adapters/openlab_robot.yaml（注意不要 git commit）",
                 "recommended": True},
                {"label": "稍后配置", "description": "先跳过，我之后自己配"},
            ],
        })

    # Q4: 模型选择
    questions.append({
        "question": "用哪个模型跑评测？",
        "header": "模型",
        "type": "single",
        "options": [
            {"label": "claude-sonnet-4", "description": "Anthropic Sonnet 4，性价比高",
             "recommended": "sonnet" in info["anthropic_model"]},
            {"label": "claude-haiku", "description": "Haiku，便宜快，适合大量 case"},
            {"label": "claude-opus", "description": "Opus，最强但贵"},
            {"label": "自定义", "description": "我用自己的模型（MiniMax / DeepSeek / 本地模型等）"},
        ],
    })

    # Q5: 工作目录
    questions.append({
        "question": "Agent 工作目录？agent 的 cwd，CLAUDE.md / .claude/ 从这里读",
        "header": "工作目录",
        "type": "single",
        "options": [
            {"label": "/tmp/openlab-work", "description": "临时目录，评测完可清",
             "recommended": True},
            {"label": "当前项目目录", "description": "用 . 作为 workdir，agent 能访问项目文件"},
            {"label": "自定义路径", "description": "我指定一个路径"},
        ],
    })

    # Q6: 权限模式 + 安全约束
    questions.append({
        "question": "权限模式？评测沙箱通常跳过权限，但生产环境可能需要更严格",
        "header": "权限模式",
        "type": "single",
        "options": [
            {"label": "bypassPermissions", "description": "跳过所有权限检查，评测沙箱推荐",
             "recommended": True},
            {"label": "acceptEdits", "description": "自动接受文件编辑，但其他操作仍问权限"},
            {"label": "default", "description": "每个工具调用都问权限（会卡住，不推荐）"},
        ],
    })

    # Q7: 成本控制
    questions.append({
        "question": "成本控制？防止 agent 死循环或烧钱",
        "header": "成本控制",
        "type": "single",
        "options": [
            {"label": "宽松（20轮/5刀）", "description": "max_turns=20, max_budget=5.0，适合复杂任务",
             "recommended": True},
            {"label": "标准（10轮/1刀）", "description": "max_turns=10, max_budget=1.0，平衡"},
            {"label": "严格（5轮/0.2刀）", "description": "max_turns=5, max_budget=0.2，调试用"},
            {"label": "不限制", "description": "不设限制（危险，仅信任的 agent 用）"},
        ],
    })

    return questions


# ---------------------------------------------------------------------------
# 评测环节信息收集
# ---------------------------------------------------------------------------

def collect_eval_info(cfg: C.EvalConfig | None = None, args: dict | None = None) -> dict:
    """收集评测环节需要的信息。"""
    info = dict(EVAL_DEFAULTS)
    if args:
        info["split"] = args.get("split", info["split"])
        info["variant"] = args.get("variant", info["variant"])
        info["label"] = args.get("label", info["label"])
        info["limit"] = args.get("limit")
    return info


def emit_eval_questions(info: dict, available_splits: list[str]) -> list[dict]:
    """生成评测环节的问题。"""
    return [{
        "question": "跑哪个 split？train 用于迭代优化，regression 用于验证不破坏旧能力，adversarial 用于压测",
        "header": "Split",
        "type": "single",
        "options": [
            {"label": "train", "description": "训练集，迭代优化用",
             "recommended": info["split"] == "train" and "train" in available_splits},
            {"label": "regression", "description": "回归集，接受 patch 前必须跑",
             "recommended": info["split"] == "regression" and "regression" in available_splits},
            {"label": "adversarial", "description": "对抗集，压测边缘场景",
             "recommended": info["split"] == "adversarial" and "adversarial" in available_splits},
        ],
    }, {
        "question": "这次评测的 variant 标签？baseline=基线，candidate_xxx=优化后版本",
        "header": "Variant",
        "type": "single",
        "options": [
            {"label": "baseline", "description": "基线版本，作为对比基准",
             "recommended": info["variant"] == "baseline"},
            {"label": "candidate", "description": "候选版本（优化后）",
             "recommended": info["variant"] != "baseline"},
        ],
    }]


# ---------------------------------------------------------------------------
# 多 Agent 评测信息收集
# ---------------------------------------------------------------------------

def collect_judge_info(cfg: C.EvalConfig | None = None) -> dict:
    """收集多 Agent 评测需要的信息。"""
    return dict(JUDGE_DEFAULTS)


def emit_judge_questions(info: dict) -> list[dict]:
    """生成多 Agent 评测的问题。"""
    return [{
        "question": "启动哪些规则型 Judge？规则型 Judge 用 Python 实现，确定性，无 LLM 成本。默认全开。",
        "header": "规则型 Judge",
        "type": "multi",
        "options": [
            {"label": "DomainJudge", "description": "业务规则覆盖：检查 case 里的 business_rules 是否被满足",
             "recommended": info["DomainJudge"]},
            {"label": "ToolTraceJudge", "description": "工具调用轨迹：检查 required/forbidden/order/参数",
             "recommended": info["ToolTraceJudge"]},
            {"label": "WorkflowJudge", "description": "流程完整性：前置检查/fallback/异常恢复",
             "recommended": info["WorkflowJudge"]},
            {"label": "FaithfulnessJudge", "description": "证据一致性：检测幻觉、编造数据",
             "recommended": info["FaithfulnessJudge"]},
            {"label": "RegressionJudge", "description": "回归风险：对比 baseline 检测退化（仅 A/B 模式）",
             "recommended": info["RegressionJudge"]},
            {"label": "SafetyJudge", "description": "安全合规：forbidden tool/敏感数据/越权（可一票否决）",
             "recommended": info["SafetyJudge"]},
        ],
    }, {
        "question": "是否启用 LLM 型 Judge？这些需要 Claude Code 按 Agent.md 执行，更智能但有成本",
        "header": "LLM 型 Judge",
        "type": "multi",
        "options": [
            {"label": "Gatekeeper", "description": "最终裁决：综合所有 Judge + A/B 给 ACCEPT/REJECT。规则版默认开",
             "recommended": info["Gatekeeper"]},
            {"label": "OptimizerPlanner", "description": "优化规划：根据 Judge 结论制定优化计划（不写代码）",
             "recommended": info["OptimizerPlanner"]},
            {"label": "PatchWriter", "description": "Patch 编写：按计划生成代码改动（唯一能改代码的 Agent）",
             "recommended": info["PatchWriter"]},
            {"label": "ReportWriter", "description": "报告撰写：整合所有结论成专业报告",
             "recommended": info["ReportWriter"]},
        ],
    }, {
        "question": "Judge 共识阈值？低于此值说明 Judge 之间分歧大，结论不可信",
        "header": "共识阈值",
        "type": "single",
        "options": [
            {"label": "0.7（推荐）", "description": "70% 一致率才算可信",
             "recommended": info["judge_consensus_threshold"] == 0.7},
            {"label": "0.5（宽松）", "description": "50% 即可，适合探索阶段"},
            {"label": "0.9（严格）", "description": "90% 一致率，适合生产环境"},
        ],
    }, {
        "question": "SafetyJudge 一票否决是否强制？开启后，安全违规直接 REJECT，不看其他条件",
        "header": "安全否决",
        "type": "single",
        "options": [
            {"label": "强制否决", "description": "安全违规 = 直接 REJECT（推荐）",
             "recommended": info["safety_veto_forced"]},
            {"label": "仅警告", "description": "安全违规只记录，不强制 reject"},
        ],
    }]


# ---------------------------------------------------------------------------
# 优化环节信息收集
# ---------------------------------------------------------------------------

def collect_optimize_info(cfg: C.EvalConfig | None = None) -> dict:
    return dict(OPTIMIZE_DEFAULTS)


def emit_optimize_questions(info: dict) -> list[dict]:
    return [{
        "question": "用哪个优化器？HRPO 是层次化根因分析，最适合缩短执行轮数",
        "header": "优化器",
        "type": "single",
        "options": [
            {"label": "HRPO", "description": "层次化根因分析：现象→直接原因→根因→修复层。最适合 F8 执行冗余",
             "recommended": info["optimizer"] == "hrpo"},
            {"label": "rule_based", "description": "规则驱动：按 mutators/*.yaml 生成 patch 建议"},
            {"label": "DeepEval", "description": "DeepEval PromptOptimizer（需 pip install deepeval）"},
            {"label": "Opik GEPA", "description": "梯度引导优化（需 pip install opik）"},
        ],
    }, {
        "question": "Budget？控制一次生成多少 patch",
        "header": "Budget",
        "type": "single",
        "options": [
            {"label": "small", "description": "最多 3 个 patch，每个改 ≤2 文件。推荐",
             "recommended": info["budget"] == "small"},
            {"label": "medium", "description": "最多 5 个 patch，每个改 ≤3 文件"},
            {"label": "large", "description": "最多 10 个 patch，每个改 ≤5 文件（风险高）"},
        ],
    }, {
        "question": "自动 apply 哪些改动？reference 风险低可自动，patch 改代码风险高",
        "header": "自动 Apply",
        "type": "multi",
        "options": [
            {"label": "reference 文件", "description": "自动生成并注入到 agent_assets/（推荐，风险低）",
             "recommended": info["auto_apply_reference"]},
            {"label": "prompt/tool patch", "description": "自动改 prompt / @Tool description（风险高）",
             "recommended": info["auto_apply_patch"]},
        ],
    }, {
        "question": "Gatekeeper 决策后自动执行什么？",
        "header": "自动 Git",
        "type": "multi",
        "options": [
            {"label": "ACCEPT 时 git commit", "description": "接受 patch 后自动 commit",
             "recommended": info["auto_git_commit"]},
            {"label": "REJECT 时 git checkout 回滚", "description": "拒绝后自动回滚 reference（推荐）",
             "recommended": info["auto_git_rollback"]},
        ],
    }]


# ---------------------------------------------------------------------------
# A/B 环节信息收集
# ---------------------------------------------------------------------------

def collect_abtest_info(cfg: C.EvalConfig | None = None) -> dict:
    return dict(ABTEST_DEFAULTS)


def emit_abtest_questions(info: dict, available_runs: list[str], available_patches: list[str]) -> list[dict]:
    return [{
        "question": "baseline run_id？作为对比基准",
        "header": "Baseline",
        "type": "single",
        "options": [
            {"label": rid, "description": f"score={_get_run_score(rid)}", "recommended": i == 0}
            for i, rid in enumerate(available_runs[:5])
        ] or [{"label": "（无历史 run）", "description": "请先跑 baseline", "recommended": True}],
    }, {
        "question": "candidate patch 文件？apply 到 agent 后跑 A/B",
        "header": "Candidate",
        "type": "single",
        "options": [
            {"label": p, "description": "", "recommended": i == 0}
            for i, p in enumerate(available_patches[:5])
        ] or [{"label": "（无 patch）", "description": "请先跑 mutator 生成 patch", "recommended": True}],
    }, {
        "question": "在哪个 split 上跑 A/B？",
        "header": "Split",
        "type": "single",
        "options": [
            {"label": "regression", "description": "回归集，验证不破坏旧能力（推荐）",
             "recommended": info["split"] == "regression"},
            {"label": "train", "description": "训练集，验证是否修了目标失败"},
            {"label": "adversarial", "description": "对抗集，压测边缘场景"},
        ],
    }, {
        "question": "接受阈值？candidate.train_score 比 baseline 高多少才算 ACCEPT",
        "header": "接受阈值",
        "type": "single",
        "options": [
            {"label": "0.03（推荐）", "description": "提升 3% 才接受，防 LLM 抖动",
             "recommended": info["train_threshold"] == 0.03},
            {"label": "0.02（宽松）", "description": "case 数 ≥50 时可用"},
            {"label": "0.05（严格）", "description": "case 数 <10 时建议"},
        ],
    }]


def _get_run_score(run_id: str) -> str:
    """读 run 的 score（简化，返回占位）。"""
    return "?"


# ---------------------------------------------------------------------------
# 写入 config
# ---------------------------------------------------------------------------

def write_startup_config(cfg: C.EvalConfig, info: dict) -> None:
    """把收集到的信息写入 config.yaml 和 adapter yaml。"""
    # 写 config.yaml
    config_path = cfg.root / "config.yaml"
    config = C.load_yaml(config_path) if config_path.exists() else {}
    config["adapter"] = info["adapter"]
    C.dump_yaml(config, config_path)

    # 写 adapter yaml
    if info["adapter"] == "openlab_robot":
        adapter_path = cfg.adapters_dir / "openlab_robot.yaml"
        adapter_cfg = C.load_yaml(adapter_path) if adapter_path.exists() else {}
        adapter_cfg["type"] = "openlab_robot"
        if info.get("openlab_bin"):
            adapter_cfg["bin"] = info["openlab_bin"]
        adapter_cfg["workdir"] = info.get("workdir", "/tmp/openlab-work")
        adapter_cfg["permission_mode"] = info.get("permission_mode", "bypassPermissions")
        adapter_cfg["max_turns"] = info.get("max_turns", 20)
        adapter_cfg["max_budget_usd"] = info.get("max_budget_usd", 1.0)
        adapter_cfg["timeout_s"] = info.get("timeout_s", 600)
        adapter_cfg["allowed_tools"] = info.get("allowed_tools", [])
        env = adapter_cfg.get("env", {})
        if info.get("anthropic_auth_token"):
            env["ANTHROPIC_AUTH_TOKEN"] = info["anthropic_auth_token"]
        if info.get("anthropic_base_url"):
            env["ANTHROPIC_BASE_URL"] = info["anthropic_base_url"]
        if info.get("anthropic_model"):
            env["ANTHROPIC_MODEL"] = info["anthropic_model"]
        env["DISABLE_TELEMETRY"] = "1"
        env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
        adapter_cfg["env"] = env
        C.dump_yaml(adapter_cfg, adapter_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True,
                    choices=["startup", "eval", "judge", "optimize", "abtest"])
    ap.add_argument("--config", default=".agent-eval/config.yaml")
    ap.add_argument("--emit-questions", action="store_true",
                    help="输出待问问题 JSON（供 Claude Code 用 AskUserQuestion）")
    args = ap.parse_args()

    cfg = None
    if Path(args.config).exists():
        try:
            cfg = C.EvalConfig.load(Path(args.config).resolve())
        except Exception:
            pass

    if args.stage == "startup":
        info = collect_startup_info(cfg)
        questions = emit_startup_questions(info)
    elif args.stage == "eval":
        info = collect_eval_info(cfg)
        available = []
        if cfg:
            available = [p.stem for p in (cfg.cases_dir).glob("*.yaml")]
        questions = emit_eval_questions(info, available)
    elif args.stage == "judge":
        info = collect_judge_info(cfg)
        questions = emit_judge_questions(info)
    elif args.stage == "optimize":
        info = collect_optimize_info(cfg)
        questions = emit_optimize_questions(info)
    elif args.stage == "abtest":
        info = collect_abtest_info(cfg)
        runs = []
        patches = []
        if cfg:
            runs = [p.stem for p in sorted((cfg.runs_dir).glob("*.jsonl"), reverse=True)]
            patches = [p.name for p in sorted((cfg.patches_dir).glob("candidate_*.md"), reverse=True)]
        questions = emit_abtest_questions(info, runs, patches)

    if args.emit_questions:
        # 输出 JSON 供 Claude Code 读取
        print(json.dumps({
            "stage": args.stage,
            "collected_info": {k: v for k, v in info.items() if not k.startswith("_")},
            "missing": info.get("_missing", []),
            "questions": questions,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"=== {args.stage} 环节信息收集 ===")
        print(f"\n已收集:")
        for k, v in info.items():
            if not k.startswith("_"):
                print(f"  {k}: {v}")
        print(f"\n缺失: {info.get('_missing', [])}")
        print(f"\n待问问题数: {len(questions)}")
        for i, q in enumerate(questions, 1):
            print(f"\n  Q{i}: {q['question']}")
            print(f"     类型: {q['type']}")
            for opt in q["options"]:
                rec = " (推荐)" if opt.get("recommended") else ""
                print(f"     - {opt['label']}{rec}: {opt['description']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
