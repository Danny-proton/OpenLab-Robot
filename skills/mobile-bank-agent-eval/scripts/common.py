"""agent-eval skill 公共工具。

所有脚本都从这里加载：
- 路径解析（找到 .agent-eval/）
- YAML 加载
- run_id 生成
- trace 事件 schema 校验
- adapter 加载与调用

这个文件不依赖任何第三方库（除 PyYAML），确保 skill 在最小环境下可跑。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError as e:  # pragma: no cover
    sys.stderr.write(
        "[agent-eval] 缺少依赖 PyYAML，请先运行: pip install pyyaml\n"
    )
    raise e


# ---------------------------------------------------------------------------
# 路径解析
# ---------------------------------------------------------------------------

def find_agent_eval_dir(start: Path | None = None) -> Path:
    """从 start 向上查找 .agent-eval/ 目录。找不到就报错。"""
    p = (start or Path.cwd()).resolve()
    for cand in [p, *p.parents]:
        if (cand / ".agent-eval").is_dir():
            return cand / ".agent-eval"
    raise FileNotFoundError(
        f"未找到 .agent-eval/ 目录。请在本项目根目录运行 `python eval_runner.py --scaffold .` 初始化。"
    )


def skill_dir() -> Path:
    """返回 skill 本身所在目录（包含 SKILL.md）。
    标准版: scripts/ 在 plugin 根下，skill 在 skills/agent-eval/。
    """
    p = Path(__file__).resolve().parent  # scripts/
    # 标准版: plugin 根 / scripts / common.py
    # 非标准版: agent-eval / scripts / common.py
    return p.parent


def example_dir() -> Path:
    """返回 plugin 里的 examples/.agent-eval。
    兼容标准版（plugin根/examples/）和非标准版（agent-eval父/examples/）。
    """
    root = skill_dir()
    # 标准版: root/examples/.agent-eval
    cand1 = root / "examples" / ".agent-eval"
    if cand1.exists():
        return cand1
    # 非标准版: root.parent/examples/.agent-eval
    cand2 = root.parent / "examples" / ".agent-eval"
    if cand2.exists():
        return cand2
    return cand1  # 返回默认，让上层报错


# ---------------------------------------------------------------------------
# YAML / JSON 加载
# ---------------------------------------------------------------------------

def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_yaml_all(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [doc for doc in yaml.safe_load_all(f) if doc]


def dump_yaml(obj: Any, path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(obj, f, allow_unicode=True, sort_keys=False)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# run_id 与时间
# ---------------------------------------------------------------------------

def now_iso() -> str:
    # 用本地时区，避免 +00:00 让人困惑
    return datetime.now().astimezone().isoformat(timespec="seconds")


def make_run_id(variant: str, label: str | None = None) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    parts = [ts, variant]
    if label:
        # label 只允许 [a-z0-9_-]
        safe = re.sub(r"[^a-z0-9_-]", "", label.lower())[:32]
        if safe:
            parts.append(safe)
    return "-".join(parts)


# ---------------------------------------------------------------------------
# trace 事件 schema
# ---------------------------------------------------------------------------

# v0 事件类型（向后兼容）
REQUIRED_EVENT_FIELDS = {"run_id", "case_id", "case_run_id", "ts", "event", "step"}
V0_EVENT_TYPES = {
    "agent_start", "prompt_rendered", "model_call", "tool_call",
    "tool_result", "memory_retrieval", "advisor_enter", "advisor_exit",
    "agent_final", "error", "agent_end",
}

# UATR 0.5 事件类型
UATR_SCHEMA_VERSION = "uatr-0.5"
UATR_REQUIRED_FIELDS = {"schema_version", "run_id", "case_id", "case_run_id",
                        "timestamp", "framework", "event_type", "status"}
UATR_EVENT_TYPES = {
    # Agent 生命周期
    "agent.run.start", "agent.run.end", "agent.delegate",
    # Model 调用
    "model.call.start", "model.call.end",
    # Tool 调用
    "tool.call.start", "tool.call.end", "tool.call.error",
    # Memory / 检索
    "memory.retrieve.start", "memory.retrieve.end",
    # Skill（Claude Code）
    "skill.select", "skill.load", "skill.execute.start", "skill.execute.end",
    # 规划 / 反思
    "planner.step", "reflection.step",
    # 文件 / Shell / Browser
    "file.read", "file.write", "shell.command", "browser.action",
    # 人工确认
    "human.approval.request", "human.approval.result",
    # 评测 / 优化
    "judge.score", "optimizer.patch.proposed",
    "optimizer.patch.accepted", "optimizer.patch.rejected",
}

# 同时支持 v0 和 UATR
EVENT_TYPES = V0_EVENT_TYPES | UATR_EVENT_TYPES


def is_uatr(ev: dict[str, Any]) -> bool:
    """判断事件是否是 UATR 格式。"""
    return ev.get("schema_version", "").startswith("uatr")


def validate_event(ev: dict[str, Any]) -> list[str]:
    """返回错误信息列表，空表示合法。支持 v0 和 UATR。"""
    errs: list[str] = []
    if is_uatr(ev):
        missing = UATR_REQUIRED_FIELDS - set(ev.keys())
        if missing:
            errs.append(f"missing UATR fields: {missing}")
        if ev.get("event_type") not in UATR_EVENT_TYPES:
            errs.append(f"unknown UATR event_type: {ev.get('event_type')!r}")
    else:
        # v0 兼容
        missing = REQUIRED_EVENT_FIELDS - set(ev.keys())
        if missing:
            errs.append(f"missing v0 fields: {missing}")
        if ev.get("event") not in V0_EVENT_TYPES:
            errs.append(f"unknown v0 event type: {ev.get('event')!r}")
    return errs


# v0 → UATR 转换
V0_TO_UATR_EVENT = {
    "agent_start": "agent.run.start",
    "agent_end": "agent.run.end",
    "prompt_rendered": "model.call.start",
    "model_call": "model.call.end",
    "tool_call": "tool.call.start",
    "tool_result": "tool.call.end",
    "memory_retrieval": "memory.retrieve.end",
    "advisor_enter": "planner.step",
    "advisor_exit": "planner.step",
    "agent_final": "agent.run.end",
    "error": "tool.call.error",  # 默认归到 tool error，attributes 里保留原 event
}


def v0_to_uatr(ev: dict[str, Any], framework: str = "spring_ai") -> dict[str, Any]:
    """把 v0 事件转成 UATR 事件。已经是 UATR 的直接返回。"""
    if is_uatr(ev):
        return ev

    out: dict[str, Any] = {
        "schema_version": UATR_SCHEMA_VERSION,
        "run_id": ev.get("run_id", ""),
        "case_id": ev.get("case_id", ""),
        "case_run_id": ev.get("case_run_id", ""),
        "timestamp": ev.get("ts") or ev.get("timestamp") or now_iso(),
        "framework": framework,
        "source": ev.get("source", "v0_compat"),
        "event_type": V0_TO_UATR_EVENT.get(ev.get("event", ""), "planner.step"),
        "status": ev.get("status") or ("error" if ev.get("event") == "error" else "success"),
    }
    if "step" in ev:
        out["span_id"] = f"span_{ev['step']:04d}"
        out["attributes"] = {"v0.step": ev["step"]}
    if "agent" in ev:
        out["actor"] = {"type": "agent", "name": ev["agent"], "role": "executor"}
    if "tool" in ev:
        out["component"] = {"type": "tool", "name": ev["tool"]}
    if "arguments" in ev:
        out.setdefault("attributes", {})["tool.arguments"] = ev["arguments"]
    if "result" in ev:
        out["output"] = {"summary": str(ev["result"])[:200]}
    if "final_answer" in ev:
        out["output"] = {"final_answer": ev["final_answer"]}
    if "latency_ms" in ev:
        out["metrics"] = {"latency_ms": ev["latency_ms"]}
    if "input_tokens" in ev or "output_tokens" in ev:
        out.setdefault("metrics", {})
        if "input_tokens" in ev:
            out["metrics"]["input_tokens"] = ev["input_tokens"]
        if "output_tokens" in ev:
            out["metrics"]["output_tokens"] = ev["output_tokens"]
    if "prompt_hash" in ev:
        out.setdefault("attributes", {})["prompt_hash"] = ev["prompt_hash"]
    if "model" in ev:
        out.setdefault("attributes", {})["gen_ai.system"] = ev["model"]
    if "memory_query" in ev:
        out.setdefault("attributes", {})["memory.query"] = ev["memory_query"]
    if "memory_hits" in ev:
        out.setdefault("attributes", {})["memory.hits"] = ev["memory_hits"]
    if "advisor" in ev:
        out.setdefault("attributes", {})["advisor"] = ev["advisor"]
    if "error" in ev and ev["error"]:
        out["attributes"] = out.get("attributes", {})
        out["attributes"]["error"] = ev["error"]
        out["status"] = "error"
    # 保留原始 event 字段以兼容老代码
    out["event"] = ev.get("event", "")
    return out


def normalize_to_uatr(events: list[dict[str, Any]], framework: str = "spring_ai") -> list[dict[str, Any]]:
    """把事件列表统一转成 UATR。已经是 UATR 的保留，v0 的转换。"""
    return [v0_to_uatr(ev, framework) for ev in events]


def hash_prompt(prompt: str) -> str:
    return "sha256:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def hash_arguments(arguments: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(arguments, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]


# ---------------------------------------------------------------------------
# adapter
# ---------------------------------------------------------------------------

@dataclass
class AdapterResult:
    final_answer: str
    raw_trace: list[dict[str, Any]]
    latency_ms: int
    status: str = "success"
    error: dict[str, Any] | None = None


def load_adapter(adapter_path: Path) -> dict[str, Any]:
    return load_yaml(adapter_path)


def call_adapter(
    adapter: dict[str, Any],
    case: dict[str, Any],
    run_id: str,
    case_run_id: str,
) -> AdapterResult:
    """根据 adapter.type 调用对应后端。支持 mock / http / openlab_robot。"""
    atype = adapter.get("type", "mock")
    if atype == "mock":
        return _call_mock(adapter, case, run_id, case_run_id)
    if atype == "http":
        return _call_http(adapter, case, run_id, case_run_id)
    if atype == "openlab_robot":
        # 动态导入，避免没装时影响其他 adapter
        import importlib.util
        adapter_path = Path(__file__).resolve().parent.parent / "adapters" / "openlab_robot_adapter.py"
        spec = importlib.util.spec_from_file_location("openlab_robot_adapter", adapter_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.call_openlab_robot(adapter, case, run_id, case_run_id)
    raise ValueError(f"不支持的 adapter type: {atype!r}")


def _call_mock(
    adapter: dict[str, Any],
    case: dict[str, Any],
    run_id: str,
    case_run_id: str,
) -> AdapterResult:
    """mock adapter：根据 case 里的 expected_tools 模拟一条"基本正确但可能漏工具"的 trace。

    行为规则（让 demo 既有成功也有失败）：
    - 如果 case.expected_tools.required 里包含 'analyze_cashflow' 且 case.id 以 '001' 结尾，
      mock 会故意漏调这个工具，制造 F3.1 失败。
    - 如果 case.business_rules.must_satisfy 里有一条 id 含 'missing_guarantee'，
      mock 的 final_answer 不会提到"担保"，制造 F7.3 失败。
    - 其他 case mock 会调全工具并给出合规答案。
    """
    case_id = case.get("id", "unknown")
    expected_tools = case.get("expected_tools", {}) or {}
    required: list[str] = expected_tools.get("required", []) or []
    forbidden: list[str] = expected_tools.get("forbidden", []) or []
    rules: list[dict[str, Any]] = (
        case.get("business_rules", {}).get("must_satisfy", []) or []
    )

    ts_base = now_iso()
    agent = case.get("agent", "mock-agent")

    events: list[dict[str, Any]] = []
    step = 1

    def add_uatr(event_type: str, **kw: Any) -> None:
        """直接生成 UATR 事件。"""
        nonlocal step
        ev: dict[str, Any] = {
            "schema_version": UATR_SCHEMA_VERSION,
            "run_id": run_id,
            "case_id": case_id,
            "case_run_id": case_run_id,
            "trace_id": f"trace-{case_run_id}",
            "span_id": f"span_{step:04d}",
            "timestamp": ts_base,
            "framework": "mock",
            "source": "mock",
            "event_type": event_type,
            "actor": {"type": "agent", "name": agent, "role": "executor"},
            "status": "success",
        }
        ev.update(kw)
        events.append(ev)
        step += 1

    # agent.run.start
    add_uatr("agent.run.start",
             component={"type": "agent", "name": agent})

    # model.call.start (prompt_rendered)
    add_uatr("model.call.start",
             component={"type": "model", "name": "mock-llm"},
             attributes={"prompt_hash": hash_prompt(f"mock-prompt-{case_id}"),
                         "gen_ai.system": "mock"},
             input={"content_hash": hash_prompt(f"input-{case_id}")})

    # model.call.end
    add_uatr("model.call.end",
             component={"type": "model", "name": "mock-llm"},
             metrics={"input_tokens": 500, "output_tokens": 30, "latency_ms": 200},
             output={"summary": "model decided to call tools"})

    # v1.1: 模拟"笨模型"行为——case 002 故意多绕几步
    # 在工具调用之间插入多余 model_call，触发 F8.2/F8.4
    is_dumb_mode = case_id.endswith("002")

    # 决定是否漏调 analyze_cashflow
    skip_cashflow = (
        "analyze_cashflow" in required
        and case_id.endswith("001")
    )
    called_tools: list[str] = []
    for t in required:
        if skip_cashflow and t == "analyze_cashflow":
            continue
        if t in forbidden:
            continue
        if is_dumb_mode:
            # 笨模型：工具前多想 2 次（F8.4 探索式徘徊）
            add_uatr("model.call.start",
                     component={"type": "model", "name": "mock-llm"},
                     attributes={"note": "dumb think 1"})
            add_uatr("model.call.end",
                     component={"type": "model", "name": "mock-llm"},
                     metrics={"input_tokens": 300, "output_tokens": 20, "latency_ms": 150},
                     output={"summary": "thinking about which tool to call"})
            add_uatr("model.call.start",
                     component={"type": "model", "name": "mock-llm"},
                     attributes={"note": "dumb think 2"})
            add_uatr("model.call.end",
                     component={"type": "model", "name": "mock-llm"},
                     metrics={"input_tokens": 300, "output_tokens": 20, "latency_ms": 150},
                     output={"summary": "still thinking"})
        add_uatr("tool.call.start",
                 component={"type": "tool", "name": t},
                 attributes={"tool.arguments": {
                     "application_id": case.get("input", {}).get("application_id", "A001")
                 }})
        add_uatr("tool.call.end",
                 component={"type": "tool", "name": t},
                 metrics={"latency_ms": 100},
                 output={"summary": f"mock result of {t}"})
        called_tools.append(t)

    # 决定 final_answer 内容
    missing_guarantee = any("missing_guarantee" in r.get("id", "") for r in rules)
    if skip_cashflow:
        final = "已根据负债情况给出结论，建议通过。"  # 漏了流水分析 + 漏了担保
    elif missing_guarantee:
        final = "已分析流水波动和负债，建议通过。"  # 漏了担保
    else:
        final = "已分析流水波动、负债情况和担保信息，建议补充材料后复审。"

    # agent.run.end (含 final_answer)
    add_uatr("agent.run.end",
             component={"type": "agent", "name": agent},
             metrics={"latency_ms": 1500},
             output={"final_answer": final})

    return AdapterResult(
        final_answer=final,
        raw_trace=events,
        latency_ms=1500,
        status="success",
    )


def _call_http(
    adapter: dict[str, Any],
    case: dict[str, Any],
    run_id: str,
    case_run_id: str,
) -> AdapterResult:
    """http adapter：POST 到 adapter.endpoint，传入 case.input 和 case_run_id。

    期望后端返回：
    {
      "final_answer": "...",
      "trace": [...]  # 已规范化的 trace 事件数组
    }

    v0 不实现重试和超时控制——如果后端挂了，直接报错，让用户修后端。
    """
    import urllib.request
    import urllib.error

    endpoint = adapter.get("endpoint")
    if not endpoint:
        raise ValueError("http adapter 需要 endpoint 字段")

    payload = {
        "case_id": case.get("id"),
        "case_run_id": case_run_id,
        "run_id": run_id,
        "input": case.get("input", {}),
        "task": case.get("task", ""),
    }
    headers = {"Content-Type": "application/json"}
    if adapter.get("auth_header"):
        headers["Authorization"] = adapter["auth_header"]

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=adapter.get("timeout_s", 60)) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        return AdapterResult(
            final_answer="",
            raw_trace=[],
            latency_ms=0,
            status="error",
            error={"type": "http_error", "message": str(e)},
        )

    return AdapterResult(
        final_answer=body.get("final_answer", ""),
        raw_trace=body.get("trace", []),
        latency_ms=body.get("latency_ms", 0),
        status=body.get("status", "success"),
    )


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

@dataclass
class EvalConfig:
    root: Path  # .agent-eval/ 的路径
    cases_dir: Path
    metrics_dir: Path
    adapters_dir: Path
    mutators_dir: Path
    traces_dir: Path
    runs_dir: Path
    scores_dir: Path
    reports_dir: Path
    patches_dir: Path
    adapter_name: str
    weights: dict[str, float] = field(default_factory=dict)
    trace_weights: dict[str, float] = field(default_factory=dict)
    trace_target_scores: dict[str, dict] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, config_path: Path) -> "EvalConfig":
        raw = load_yaml(config_path)
        root = config_path.parent
        d = raw.get("dirs", {}) or {}
        def dir_of(name: str, default: str) -> Path:
            v = d.get(name, default)
            return (root / v) if not Path(v).is_absolute() else Path(v)
        return cls(
            root=root,
            cases_dir=dir_of("cases", "cases"),
            metrics_dir=dir_of("metrics", "metrics"),
            adapters_dir=dir_of("adapters", "adapters"),
            mutators_dir=dir_of("mutators", "mutators"),
            traces_dir=dir_of("traces", "traces"),
            runs_dir=dir_of("runs", "runs"),
            scores_dir=dir_of("scores", "scores"),
            reports_dir=dir_of("reports", "reports"),
            patches_dir=dir_of("patches", "patches"),
            adapter_name=raw.get("adapter", "mock"),
            weights=raw.get("weights", {}) or {},
            trace_weights=raw.get("trace", {}).get("weights", {}) or {},
            trace_target_scores=raw.get("trace", {}).get("target_scores", {}) or {},
            extra=raw.get("extra", {}) or {},
        )

    def adapter_path(self) -> Path:
        # mock 是内置的，不需要文件
        if self.adapter_name == "mock":
            return self.adapters_dir / "mock.yaml"  # 可能不存在，call_adapter 不读
        return self.adapters_dir / f"{self.adapter_name}.yaml"


def ensure_dirs(cfg: EvalConfig) -> None:
    for d in [cfg.cases_dir, cfg.metrics_dir, cfg.adapters_dir, cfg.mutators_dir,
              cfg.traces_dir, cfg.runs_dir, cfg.scores_dir, cfg.reports_dir,
              cfg.patches_dir]:
        d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# scaffold
# ---------------------------------------------------------------------------

def scaffold(target: Path) -> None:
    """把 examples/.agent-eval 复制到 target/.agent-eval。"""
    src = example_dir()
    if not src.exists():
        raise FileNotFoundError(f"skill bundle 缺少 examples 目录: {src}")
    dst = target / ".agent-eval"
    if dst.exists():
        raise FileExistsError(f"目标已存在: {dst}。请先删除或重命名。")
    shutil.copytree(src, dst)
    # 创建空目录
    for sub in ["traces", "runs", "scores", "reports", "patches"]:
        (dst / sub).mkdir(exist_ok=True)
        (dst / sub / ".gitkeep").write_text("", encoding="utf-8")
    sys.stdout.write(f"[agent-eval] 已初始化: {dst}\n")
    sys.stdout.write(
        "[agent-eval] 下一步：编辑 .agent-eval/config.yaml 和 cases/train.yaml，"
        "然后运行 eval_runner.py --config .agent-eval/config.yaml --split train\n"
    )


# ---------------------------------------------------------------------------
# 模板渲染（简单字符串替换，不引入 jinja2）
# ---------------------------------------------------------------------------

def render_template(template: str, vars_: dict[str, Any]) -> str:
    out = template
    for k, v in vars_.items():
        out = out.replace("{{ " + k + " }}", str(v))
        out = out.replace("{{" + k + "}}", str(v))
    return out


def load_template(name: str) -> str:
    p = skill_dir() / "templates" / name
    if not p.exists():
        raise FileNotFoundError(f"模板不存在: {p}")
    return p.read_text(encoding="utf-8")


__all__ = [
    "find_agent_eval_dir", "skill_dir", "example_dir",
    "load_yaml", "load_yaml_all", "dump_yaml",
    "load_jsonl", "append_jsonl", "write_json",
    "now_iso", "make_run_id",
    "validate_event", "hash_prompt", "hash_arguments",
    "AdapterResult", "load_adapter", "call_adapter",
    "EvalConfig", "ensure_dirs", "scaffold",
    "render_template", "load_template",
    "load_json",  # re-export
    # UATR
    "UATR_SCHEMA_VERSION", "UATR_EVENT_TYPES", "UATR_REQUIRED_FIELDS",
    "V0_EVENT_TYPES", "V0_TO_UATR_EVENT",
    "is_uatr", "v0_to_uatr", "normalize_to_uatr",
]
