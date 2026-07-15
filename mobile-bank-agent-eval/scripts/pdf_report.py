#!/usr/bin/env python3
"""pdf_report.py — PDF 报告生成器。

通过 weasyprint 将 HTML 报告转换为 PDF。

依赖: pip install weasyprint

用法:
  python pdf_report.py --config .agent-eval/config.yaml --run <run_id>
  python pdf_report.py --config .agent-eval/config.yaml --run <run_id> --page-size A4
  python pdf_report.py --config .agent-eval/config.yaml --all  # 批量生成
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import html_report as HR  # noqa: E402
import charts as CH  # noqa: E402


def _cover_html(run_id: str, score: dict, cfg: C.EvalConfig) -> str:
    """生成封面页 HTML。"""
    agg = score.get("aggregate", {})
    return f"""
    <div class="page-break" style="page-break-after:always;height:100vh;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;">
      <h1 style="font-size:42px;color:#2563eb;margin-bottom:24px;">Agent 评测报告</h1>
      <p style="font-size:18px;color:#64748b;margin-bottom:8px;">AgentEvalOps Lite v0.5</p>
      <p style="font-size:16px;color:#0f172a;margin-bottom:32px;"><code>{run_id}</code></p>
      <table style="width:auto;margin:0 auto;font-size:14px;color:#334155;">
        <tr><td style="padding:6px 16px;text-align:right;font-weight:600;">Case 总数</td><td style="padding:6px 16px;">{agg.get('n_cases', 0)}</td></tr>
        <tr><td style="padding:6px 16px;text-align:right;font-weight:600;">成功率</td><td style="padding:6px 16px;">{agg.get('n_success', 0) / max(agg.get('n_cases', 1), 1) * 100:.1f}%</td></tr>
        <tr><td style="padding:6px 16px;text-align:right;font-weight:600;">加权总分</td><td style="padding:6px 16px;">{agg.get('weighted_score', 0):.3f}</td></tr>
        <tr><td style="padding:6px 16px;text-align:right;font-weight:600;">硬失败数</td><td style="padding:6px 16px;">{agg.get('n_hard_fail', 0)}</td></tr>
      </table>
      <p style="margin-top:48px;font-size:13px;color:#94a3b8;">生成时间: {C.now_iso()}</p>
    </div>
    """


def _toc_html() -> str:
    """生成目录页 HTML。"""
    items = [
        ("executive-summary", "1. 执行摘要"),
        ("eval-setup", "2. 评测配置"),
        ("scorecard", "3. 总体评分卡"),
        ("scenario", "4. 场景结果"),
        ("metric-results", "5. 指标结果"),
        ("trace-analysis", "6. 工具分析"),
        ("failure-taxonomy", "7. 失败归因"),
        ("iteration", "8. 迭代历史"),
        ("case-heatmap", "9. Case 热力图"),
        ("trace-timeline", "10. Trace 时间线"),
        ("recommendations", "11. 建议"),
    ]
    rows = "".join(
        f'<tr><td style="padding:8px 0;border-bottom:1px solid #e2e8f0;"><a href="#{aid}" style="color:#2563eb;text-decoration:none;">{title}</a></td></tr>'
        for aid, title in items
    )
    return f"""
    <div class="page-break" style="page-break-after:always;padding-top:60px;">
      <h2 style="color:#0f172a;margin-bottom:24px;">目录</h2>
      <table style="width:100%;font-size:15px;">{rows}</table>
    </div>
    """


def _build_pdf_ready_html(
    cfg: C.EvalConfig,
    run_id: str,
    score: dict,
    charts_data: dict,
    diagnosis: dict | None,
    baseline_score: dict | None,
    include_cover: bool = True,
    include_toc: bool = True,
) -> str:
    """生成适合 PDF 的完整 HTML。"""
    # 复用 html_report.py 生成主体
    html_path = HR.generate_html_report(
        cfg, run_id, score, charts_data, diagnosis, baseline_score
    )
    body = html_path.read_text(encoding="utf-8")

    # 提取 body 内容
    body_start = body.find("<body>")
    body_end = body.find("</body>")
    if body_start == -1 or body_end == -1:
        body_content = body
    else:
        body_content = body[body_start + 6:body_end]

    # 去掉导出按钮和导航（PDF 不需要）
    body_content = body_content.replace('<div class="no-print" style="text-align:right;margin-bottom:16px;">', '<div class="no-print" style="display:none;">')

    cover = _cover_html(run_id, score, cfg) if include_cover else ""
    toc = _toc_html() if include_toc else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Agent 评测报告 — {run_id}</title>
<style>
{HR._css()}
@page {{ size: A4; margin: 15mm; }}
@page :first {{ margin: 0; }}
.page-break {{ page-break-before: always; }}
</style>
</head>
<body>
{cover}
{toc}
{body_content}
</body>
</html>
"""


def generate_pdf_report(
    cfg: C.EvalConfig,
    run_id: str,
    page_size: str = "A4",
    include_cover: bool = True,
    include_toc: bool = True,
) -> Path:
    """生成 PDF 报告。"""
    try:
        from weasyprint import HTML  # type: ignore  # noqa: F811
    except ImportError as e:
        raise ImportError(
            "生成 PDF 需要 weasyprint。请运行: pip install weasyprint"
        ) from e

    score = json.loads((cfg.scores_dir / f"{run_id}.json").read_text(encoding="utf-8"))
    diagnosis = None
    diag_path = cfg.reports_dir / f"{run_id}_diagnosis.json"
    if diag_path.exists():
        diagnosis = json.loads(diag_path.read_text(encoding="utf-8"))

    cases = []
    cases_path = cfg.cases_dir / "train.yaml"
    if cases_path.exists():
        cases = C.load_yaml(cases_path).get("cases", [])

    baseline_score = None
    # 如果 html_report 已经生成了 charts.json，直接读；否则重新生成
    charts_path = cfg.scores_dir / f"{run_id}.charts.json"
    if charts_path.exists():
        charts_data = json.loads(charts_path.read_text(encoding="utf-8"))
    else:
        charts_data = CH.build_charts(cfg, run_id, score, diagnosis, baseline_score, cases)

    html = _build_pdf_ready_html(
        cfg, run_id, score, charts_data, diagnosis, baseline_score,
        include_cover, include_toc,
    )

    out = cfg.reports_dir / f"{run_id}.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = HTML(string=html)
    doc.write_pdf(str(out))
    try:
        import report_manager as RM
        RM.register_report(cfg, out, run_id=run_id, title=f"PDF 报告 — {run_id}")
    except Exception as e:
        sys.stderr.write(f"[report_manager] 注册失败: {e}\n")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--run", help="指定 run_id")
    ap.add_argument("--all", action="store_true", help="批量生成所有 scores/*.json 对应的 PDF")
    ap.add_argument("--page-size", default="A4", choices=["A4", "Letter", "Legal"])
    ap.add_argument("--no-cover", action="store_true")
    ap.add_argument("--no-toc", action="store_true")
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())

    if args.all:
        run_ids = [p.stem for p in sorted(cfg.scores_dir.glob("*.json"))]
        if not run_ids:
            print("未找到可生成 PDF 的 run。", file=sys.stderr)
            return 1
        for rid in run_ids:
            try:
                out = generate_pdf_report(
                    cfg, rid, args.page_size,
                    include_cover=not args.no_cover,
                    include_toc=not args.no_toc,
                )
                print(f"PDF report: {out}")
            except Exception as e:
                print(f"生成 {rid} 的 PDF 失败: {e}", file=sys.stderr)
        return 0

    if not args.run:
        print("请指定 --run <run_id> 或使用 --all", file=sys.stderr)
        return 1

    out = generate_pdf_report(
        cfg, args.run, args.page_size,
        include_cover=not args.no_cover,
        include_toc=not args.no_toc,
    )
    print(f"PDF report: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
