#!/usr/bin/env python3
"""report_manager.py — 报告 CRUD 管理器。

为 .agent-eval/reports/ 下生成的所有报告维护一个可检索索引，
支持 list / get / search / update / delete / reindex。

被各报告生成脚本在写入文件后调用；也提供独立 CLI。

用法:
  python report_manager.py --config .agent-eval/config.yaml list
  python report_manager.py --config .agent-eval/config.yaml get <report_id>
  python report_manager.py --config .agent-eval/config.yaml search --run <run_id> --format md
  python report_manager.py --config .agent-eval/config.yaml update <report_id> --tags foo,bar --notes "备注"
  python report_manager.py --config .agent-eval/config.yaml delete <report_id>
  python report_manager.py --config .agent-eval/config.yaml reindex
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


INDEX_FILENAME = "index.jsonl"


# -----------------------------------------------------------------------------
# 报告类型识别规则（filename -> report_type, run_id 提取）
# -----------------------------------------------------------------------------

def _report_type_for(path: Path) -> tuple[str, str | None]:
    """根据文件名返回 (report_type, run_id_or_none)。"""
    name = path.name

    # accepted_patches.md 最先匹配
    if name == "accepted_patches.md":
        return "patch_acceptance_log", None
    if name == "dashboard.html":
        return "dashboard", None

    # abtest 报告：一个文件关联两个 run_id，但索引里只存一条；取 baseline 作为 run_id
    if name.startswith("abtest_") and name.endswith(".md"):
        parts = name[7:-3].split("_vs_")
        if len(parts) == 2:
            return "abtest_report", parts[0]
        return "abtest_report", None

    if name.endswith("_diagnosis.md") or name.endswith("_diagnosis.json"):
        return "diagnosis_data" if name.endswith(".json") else "diagnosis", name.rsplit("_diagnosis", 1)[0]

    if name.endswith("_judges.md") or name.endswith("_judges.json"):
        return "judges_data" if name.endswith(".json") else "judges_report", name.rsplit("_judges", 1)[0]

    if name.endswith("_ci_verdict.json"):
        return "ci_verdict", name[:-14]

    if name.endswith(".md"):
        return "run_report", path.stem
    if name.endswith(".html"):
        return "html_report", path.stem
    if name.endswith(".pdf"):
        return "pdf_report", path.stem

    return "unknown", path.stem


_TYPE_TITLES: dict[str, str] = {
    "run_report": "评测报告",
    "abtest_report": "A/B 评测报告",
    "diagnosis": "诊断报告",
    "diagnosis_data": "诊断数据",
    "html_report": "HTML 评测报告",
    "dashboard": "交互式 Dashboard",
    "judges_report": "多 Judge 评审报告",
    "judges_data": "多 Judge 评审数据",
    "ci_verdict": "CI 回归判定",
    "pdf_report": "PDF 评测报告",
    "patch_acceptance_log": "已接受 Patch 记录",
    "unknown": "报告",
}


def _default_title(report_type: str, run_id: str | None, path: Path) -> str:
    base = _TYPE_TITLES.get(report_type, "报告")
    if report_type == "abtest_report":
        return f"{base} — {path.stem}"
    if run_id:
        return f"{base} — {run_id}"
    return f"{base} — {path.name}"


# -----------------------------------------------------------------------------
# 索引读写
# -----------------------------------------------------------------------------

def _index_path(cfg: C.EvalConfig) -> Path:
    return cfg.reports_dir / INDEX_FILENAME


def _load_index(cfg: C.EvalConfig) -> list[dict[str, Any]]:
    return C.load_jsonl(_index_path(cfg))


def _save_index(cfg: C.EvalConfig, entries: list[dict[str, Any]]) -> None:
    out = _index_path(cfg)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def _make_report_id(report_type: str, path: Path) -> str:
    return f"{report_type}-{path.stem}"


def _normalize_path(cfg: C.EvalConfig, path: Path) -> Path:
    """把 path 转成相对 cfg.root 的路径对象。"""
    p = Path(path)
    if p.is_absolute():
        try:
            return p.relative_to(cfg.root)
        except ValueError:
            pass
    return p


# -----------------------------------------------------------------------------
# 公开 API
# -----------------------------------------------------------------------------

def register_report(
    cfg: C.EvalConfig,
    path: Path | str,
    report_type: str | None = None,
    run_id: str | None = None,
    related_run_ids: list[str] | None = None,
    title: str | None = None,
    meta: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """注册或更新一条报告索引记录。失败时抛出异常，调用方负责捕获。"""
    abs_path = cfg.root / _normalize_path(cfg, path)
    rel_path = _normalize_path(cfg, path)

    inferred_type, inferred_run_id = _report_type_for(abs_path)
    rtype = report_type or inferred_type
    rid = run_id or inferred_run_id

    report_id = _make_report_id(rtype, abs_path)
    now = C.now_iso()

    entries = _load_index(cfg)
    # 去重：按 report_id
    existing = next((e for e in entries if e.get("report_id") == report_id), None)

    if existing:
        entry = existing
        entry["updated_at"] = now
        if title is not None:
            entry["title"] = title
        if meta is not None:
            entry["meta"] = meta
        if tags is not None:
            entry["tags"] = list(tags)
        if notes is not None:
            entry["notes"] = notes
        if related_run_ids is not None:
            entry["related_run_ids"] = list(related_run_ids)
        # 路径/类型/run_id 以最新文件为准
        entry["path"] = str(rel_path)
        entry["report_type"] = rtype
        entry["format"] = abs_path.suffix.lstrip(".")
        if rid:
            entry["run_id"] = rid
    else:
        entry = {
            "report_id": report_id,
            "report_type": rtype,
            "format": abs_path.suffix.lstrip("."),
            "run_id": rid,
            "related_run_ids": list(related_run_ids) if related_run_ids else [],
            "title": title or _default_title(rtype, rid, abs_path),
            "path": str(rel_path),
            "created_at": now,
            "updated_at": now,
            "tags": list(tags) if tags else [],
            "notes": notes or "",
            "meta": dict(meta) if meta else {},
        }
        entries.append(entry)

    _save_index(cfg, entries)
    return entry


def list_reports(
    cfg: C.EvalConfig,
    report_type: str | None = None,
    fmt: str | None = None,
    run_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    missing: bool | None = None,
) -> list[dict[str, Any]]:
    """列出报告索引。missing=True 只返回文件已不存在的条目，missing=False 只返回存在的。

    since/until 为 ISO 日期字符串（如 2026-07-12），按 created_at 过滤。
    """
    entries = _load_index(cfg)
    out = []
    for e in entries:
        if report_type and e.get("report_type") != report_type:
            continue
        if fmt and e.get("format") != fmt:
            continue
        if run_id is not None:
            related = e.get("related_run_ids") or []
            if e.get("run_id") != run_id and run_id not in related:
                continue
        created = e.get("created_at", "")
        if since and created < since:
            continue
        if until and created >= until:
            continue
        p = cfg.root / e.get("path", "")
        exists = p.exists()
        if missing is True and exists:
            continue
        if missing is False and not exists:
            continue
        e = dict(e)
        e["_exists"] = exists
        out.append(e)
    # 默认按 created_at 降序
    out.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return out


def get_report(cfg: C.EvalConfig, report_id: str) -> dict[str, Any] | None:
    """按 report_id 获取单条记录。"""
    for e in _load_index(cfg):
        if e.get("report_id") == report_id:
            e = dict(e)
            e["_exists"] = (cfg.root / e.get("path", "")).exists()
            return e
    return None


def search_reports(
    cfg: C.EvalConfig,
    query: str | None = None,
    report_type: str | None = None,
    fmt: str | None = None,
    run_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> list[dict[str, Any]]:
    """全文搜索：query 匹配 report_id / title / tags / notes / run_id / path。"""
    entries = list_reports(cfg, report_type=report_type, fmt=fmt, run_id=run_id, since=since, until=until)
    if not query:
        return entries
    q = query.lower()
    out = []
    for e in entries:
        texts = [
            str(e.get("report_id", "")),
            str(e.get("title", "")),
            str(e.get("run_id", "")),
            str(e.get("path", "")),
            " ".join(str(t) for t in e.get("tags", [])),
            str(e.get("notes", "")),
        ]
        if any(q in t.lower() for t in texts):
            out.append(e)
    return out


def view_report(
    cfg: C.EvalConfig,
    report_id: str,
    head: int | None = None,
    tail: int | None = None,
) -> dict[str, Any] | None:
    """读取报告文件内容。返回 entry + content 字段；若文件不存在返回 entry 且 content=None。"""
    e = get_report(cfg, report_id)
    if not e:
        return None
    p = cfg.root / e.get("path", "")
    content: str | None = None
    lines: list[str] = []
    if p.exists():
        try:
            text = p.read_text(encoding="utf-8")
            all_lines = text.splitlines()
            if head is not None and tail is not None:
                lines = all_lines[:head]
                if len(all_lines) > head + tail:
                    skipped = len(all_lines) - head - tail
                    lines.append(f"... ({skipped}) 行省略 ...")
                lines.extend(all_lines[-tail:])
            elif head is not None:
                lines = all_lines[:head]
            elif tail is not None:
                lines = all_lines[-tail:]
            else:
                lines = all_lines
            content = "\n".join(lines)
        except Exception as ex:
            content = f"[读取失败: {ex}]"
    e = dict(e)
    e["content"] = content
    return e


def export_report(
    cfg: C.EvalConfig,
    report_id: str,
    dest: Path | str,
) -> dict[str, Any] | None:
    """把报告文件复制到目标路径。返回 entry 和 dest。"""
    e = get_report(cfg, report_id)
    if not e:
        return None
    src = cfg.root / e.get("path", "")
    dst = Path(dest)
    if not src.exists():
        raise FileNotFoundError(f"报告文件不存在: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy2(src, dst)
    e = dict(e)
    e["dest"] = str(dst)
    return e


def rename_report(
    cfg: C.EvalConfig,
    report_id: str,
    new_title: str,
) -> dict[str, Any] | None:
    """重命名报告标题。"""
    return update_report(cfg, report_id, title=new_title)


def daily_report_summary(cfg: C.EvalConfig) -> dict[str, list[dict[str, Any]]]:
    """按日期分组返回报告摘要。"""
    entries = list_reports(cfg)
    by_day: dict[str, list[dict[str, Any]]] = {}
    for e in entries:
        day = e.get("created_at", "")[:10] or "unknown"
        by_day.setdefault(day, []).append(e)
    # 每天内部按时间降序
    for day in by_day:
        by_day[day].sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return dict(sorted(by_day.items(), reverse=True))


def update_report(
    cfg: C.EvalConfig,
    report_id: str,
    tags: list[str] | None = None,
    notes: str | None = None,
    title: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """更新报告元数据。tags 会整体替换；meta 会整体替换。"""
    entries = _load_index(cfg)
    for e in entries:
        if e.get("report_id") == report_id:
            if tags is not None:
                e["tags"] = list(tags)
            if notes is not None:
                e["notes"] = notes
            if title is not None:
                e["title"] = title
            if meta is not None:
                e["meta"] = dict(meta)
            e["updated_at"] = C.now_iso()
            _save_index(cfg, entries)
            return dict(e)
    return None


def delete_report(
    cfg: C.EvalConfig,
    report_id: str,
    remove_file: bool = True,
) -> dict[str, Any] | None:
    """删除索引记录；可选同时删除文件。"""
    entries = _load_index(cfg)
    target = next((e for e in entries if e.get("report_id") == report_id), None)
    if not target:
        return None

    entries = [e for e in entries if e.get("report_id") != report_id]
    _save_index(cfg, entries)

    if remove_file:
        p = cfg.root / target.get("path", "")
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass
    return dict(target)


def _scan_reports(cfg: C.EvalConfig) -> list[dict[str, Any]]:
    """扫描 reports 目录，返回可识别的报告条目。"""
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for p in sorted(cfg.reports_dir.iterdir()):
        if not p.is_file():
            continue
        if p.name == INDEX_FILENAME:
            continue

        rtype, rid = _report_type_for(p)
        if rtype == "unknown":
            continue
        rel = str(_normalize_path(cfg, p))
        report_id = _make_report_id(rtype, p)
        if report_id in seen:
            continue
        seen.add(report_id)

        entries.append({
            "report_id": report_id,
            "report_type": rtype,
            "format": p.suffix.lstrip("."),
            "run_id": rid,
            "related_run_ids": [],
            "title": _default_title(rtype, rid, p),
            "path": rel,
            "created_at": C.now_iso(),
            "updated_at": C.now_iso(),
            "tags": [],
            "notes": "",
            "meta": {},
        })
    return entries


def reindex_reports(cfg: C.EvalConfig) -> list[dict[str, Any]]:
    """重建索引：扫描现有文件并保留旧条目的 tags/notes/title。"""
    old_entries = _load_index(cfg)
    old_by_path: dict[str, dict[str, Any]] = {}
    for e in old_entries:
        old_by_path[e.get("path", "")] = e

    fresh = _scan_reports(cfg)
    for e in fresh:
        old = old_by_path.get(e["path"])
        if old:
            # 保留用户手动维护的元数据
            e["tags"] = list(old.get("tags", []))
            e["notes"] = old.get("notes", "")
            e["title"] = old.get("title", e["title"])
            e["created_at"] = old.get("created_at", e["created_at"])
            e["meta"] = dict(old.get("meta", {}))
            e["related_run_ids"] = list(old.get("related_run_ids", []))
            e["updated_at"] = C.now_iso()

    _save_index(cfg, fresh)
    return fresh


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def _next_day(date_str: str) -> str:
    """把 YYYY-MM-DD 转成第二天的 00:00:00，用于包含当天。"""
    from datetime import datetime, timedelta
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return (dt + timedelta(days=1)).strftime("%Y-%m-%d")
    except ValueError:
        return date_str


def _fmt_tags(tags: list[str]) -> str:
    return ", ".join(tags) if tags else "-"


def _print_table(entries: list[dict[str, Any]]) -> None:
    if not entries:
        print("未找到报告。")
        return
    headers = ["report_id", "type", "format", "run_id", "title", "tags", "path"]
    widths = {h: len(h) for h in headers}
    rows = []
    for e in entries:
        row = {
            "report_id": e.get("report_id", ""),
            "type": e.get("report_type", ""),
            "format": e.get("format", ""),
            "run_id": e.get("run_id") or "-",
            "title": e.get("title", ""),
            "tags": _fmt_tags(e.get("tags", [])),
            "path": e.get("path", ""),
        }
        rows.append(row)
        for h in headers:
            widths[h] = max(widths[h], len(str(row[h])))

    def line(row: dict[str, str] | None = None) -> str:
        if row is None:
            return " | ".join("-" * widths[h] for h in headers)
        return " | ".join(str(row[h]).ljust(widths[h]) for h in headers)

    print(line({h: h for h in headers}))
    print(line())
    for r in rows:
        print(line(r))


def _print_daily_table(entries: list[dict[str, Any]]) -> None:
    """按 created_at 日期分组打印表格。"""
    if not entries:
        print("未找到报告。")
        return
    by_day: dict[str, list[dict[str, Any]]] = {}
    for e in entries:
        day = e.get("created_at", "")[:10] or "unknown"
        by_day.setdefault(day, []).append(e)
    for day in sorted(by_day.keys(), reverse=True):
        print(f"\n📅 {day} ({len(by_day[day])} 条)")
        _print_table(by_day[day])


def _print_daily_summary(summary: dict[str, list[dict[str, Any]]]) -> None:
    """打印每日报告摘要。"""
    if not summary:
        print("未找到报告。")
        return
    for day, entries in summary.items():
        print(f"\n📅 {day} ({len(entries)} 条)")
        for e in entries:
            rid = e.get("run_id") or "-"
            print(f"  [{e.get('created_at', '')[11:19]}] {e.get('report_id')} | {e.get('format')} | run={rid} | {e.get('title', '')}")


def main() -> int:
    ap = argparse.ArgumentParser(description="agent-eval 报告管理器")
    ap.add_argument("--config", required=True, help=".agent-eval/config.yaml 路径")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出（默认表格）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # list
    p_list = sub.add_parser("list", help="列出所有报告")
    p_list.add_argument("--type", help="按 report_type 过滤")
    p_list.add_argument("--format", dest="fmt", help="按格式过滤 (md/html/json/pdf)")
    p_list.add_argument("--run", help="按 run_id 过滤")
    p_list.add_argument("--since", help="日期下限 (YYYY-MM-DD)，含当天")
    p_list.add_argument("--until", help="日期上限 (YYYY-MM-DD)，含当天")
    p_list.add_argument("--missing", action="store_true", help="只显示文件已缺失的索引记录")
    p_list.add_argument("--daily", action="store_true", help="按日期分组展示")

    # get
    p_get = sub.add_parser("get", help="获取单条报告详情")
    p_get.add_argument("report_id")

    # search
    p_search = sub.add_parser("search", help="搜索报告")
    p_search.add_argument("--query", help="关键词")
    p_search.add_argument("--type", help="按 report_type 过滤")
    p_search.add_argument("--format", dest="fmt", help="按格式过滤")
    p_search.add_argument("--run", help="按 run_id 过滤")
    p_search.add_argument("--since", help="日期下限 (YYYY-MM-DD)")
    p_search.add_argument("--until", help="日期上限 (YYYY-MM-DD)")

    # view
    p_view = sub.add_parser("view", help="查看报告内容")
    p_view.add_argument("report_id")
    p_view.add_argument("--head", type=int, help="只看前 N 行")
    p_view.add_argument("--tail", type=int, help="只看后 N 行")

    # rename
    p_rename = sub.add_parser("rename", help="重命名报告标题")
    p_rename.add_argument("report_id")
    p_rename.add_argument("new_title")

    # export
    p_export = sub.add_parser("export", help="导出/下载报告到指定路径")
    p_export.add_argument("report_id")
    p_export.add_argument("dest_path")

    # daily
    p_daily = sub.add_parser("daily", help="按日期查看报告汇总")

    # update
    p_update = sub.add_parser("update", help="更新报告元数据")
    p_update.add_argument("report_id")
    p_update.add_argument("--tags", help="逗号分隔标签，会整体替换")
    p_update.add_argument("--notes", help="备注")
    p_update.add_argument("--title", help="标题")

    # delete
    p_delete = sub.add_parser("delete", help="删除报告索引（默认同时删除文件）")
    p_delete.add_argument("report_id")
    p_delete.add_argument("--keep-file", action="store_true", help="只删索引，保留文件")

    # reindex
    sub.add_parser("reindex", help="根据现有文件重建索引")

    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())
    C.ensure_dirs(cfg)

    if args.cmd == "list":
        entries = list_reports(
            cfg,
            report_type=args.type,
            fmt=args.fmt,
            run_id=args.run,
            since=args.since,
            until=_next_day(args.until) if args.until else None,
            missing=args.missing if args.missing else None,
        )
        if args.daily:
            _print_daily_table(entries)
        elif args.json:
            print(json.dumps(entries, ensure_ascii=False, indent=2))
        else:
            _print_table(entries)
        return 0

    if args.cmd == "get":
        e = get_report(cfg, args.report_id)
        if not e:
            sys.stderr.write(f"未找到报告: {args.report_id}\n")
            return 1
        print(json.dumps(e, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "search":
        entries = search_reports(
            cfg,
            query=args.query,
            report_type=args.type,
            fmt=args.fmt,
            run_id=args.run,
            since=args.since,
            until=_next_day(args.until) if args.until else None,
        )
        if args.json:
            print(json.dumps(entries, ensure_ascii=False, indent=2))
        else:
            _print_table(entries)
        return 0

    if args.cmd == "view":
        e = view_report(cfg, args.report_id, head=args.head, tail=args.tail)
        if not e:
            sys.stderr.write(f"未找到报告: {args.report_id}\n")
            return 1
        if e.get("content") is None:
            sys.stderr.write(f"报告文件不存在: {e.get('path')}\n")
            return 1
        print(f"# {e['title']} ({e['report_id']})")
        print(f"# 路径: {e['path']}")
        print(f"# 创建时间: {e['created_at']}\n")
        print(e["content"])
        return 0

    if args.cmd == "rename":
        e = rename_report(cfg, args.report_id, args.new_title)
        if not e:
            sys.stderr.write(f"未找到报告: {args.report_id}\n")
            return 1
        print(f"已重命名为: {e['title']}")
        return 0

    if args.cmd == "export":
        try:
            e = export_report(cfg, args.report_id, args.dest_path)
        except Exception as ex:
            sys.stderr.write(f"导出失败: {ex}\n")
            return 1
        if not e:
            sys.stderr.write(f"未找到报告: {args.report_id}\n")
            return 1
        print(f"已导出: {e['dest']}")
        return 0

    if args.cmd == "daily":
        summary = daily_report_summary(cfg)
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            _print_daily_summary(summary)
        return 0

    if args.cmd == "update":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None
        e = update_report(cfg, args.report_id, tags=tags, notes=args.notes, title=args.title)
        if not e:
            sys.stderr.write(f"未找到报告: {args.report_id}\n")
            return 1
        print(json.dumps(e, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "delete":
        e = delete_report(cfg, args.report_id, remove_file=not args.keep_file)
        if not e:
            sys.stderr.write(f"未找到报告: {args.report_id}\n")
            return 1
        print(f"已删除: {e['report_id']} ({e['path']})")
        return 0

    if args.cmd == "reindex":
        entries = reindex_reports(cfg)
        print(f"已重建索引，共 {len(entries)} 条报告")
        if args.json:
            print(json.dumps(entries, ensure_ascii=False, indent=2))
        else:
            _print_table(entries)
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
