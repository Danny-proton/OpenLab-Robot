#!/usr/bin/env python3
"""annotate_server.py — 启动本地 HTTP 服务 + 静态 HTML 标注页面。

用法:
  python annotate_server.py --config .agent-eval/config.yaml --port 8766

零第三方依赖（http.server 标准库）。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


# ---------------------------------------------------------------------------
# 全局状态
# ---------------------------------------------------------------------------

_cfg: C.EvalConfig | None = None
_cases: list[dict] = []
_annotations_by_case: dict[str, dict] = {}


def _load_data(config_path: str) -> None:
    global _cfg, _cases, _annotations_by_case
    _cfg = C.EvalConfig.load(Path(config_path).resolve())
    C.ensure_dirs(_cfg)

    # 加载用例
    for split in ["train", "regression", "adversarial"]:
        p = _cfg.cases_dir / f"{split}.yaml"
        if p.exists():
            raw = C.load_yaml(p)
            _cases.extend(raw.get("cases", []))

    # 加载标注
    ann_path = _cfg.root / "annotations.jsonl"
    if ann_path.exists():
        for ann in C.load_jsonl(ann_path):
            cid = ann.get("case_id", "")
            _annotations_by_case[cid] = ann


# ---------------------------------------------------------------------------
# API Handlers
# ---------------------------------------------------------------------------

class AnnotateHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._serve_html()
        elif path == "/api/cases":
            self._json_response(self._get_cases(params))
        elif path == "/api/cases/":
            cid = params.get("case_id", [None])[0]
            self._json_response(self._get_case_detail(cid))
        elif path == "/api/annotations":
            self._json_response(self._get_all_annotations())
        elif path == "/api/annotations/stats":
            self._json_response(self._get_stats())
        elif path.startswith("/api/annotations/"):
            cid = path.split("/")[-1]
            ann = _annotations_by_case.get(cid)
            self._json_response(ann or {"error": "not found"})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/annotations":
            content_len = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_len).decode("utf-8"))
            self._json_response(self._save_annotation(body))
        elif path == "/api/annotations/batch":
            content_len = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_len).decode("utf-8"))
            self._json_response(self._save_annotations_batch(body))
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_html(self):
        html_path = Path(__file__).resolve().parent.parent / "templates" / "annotate.html"
        if not html_path.exists():
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"annotate.html template not found")
            return
        content = html_path.read_text(encoding="utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def _json_response(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

    def _get_cases(self, params):
        risk_filter = params.get("risk_level", [None])[0]
        dim_filter = params.get("dimension", [None])[0]
        annotated_only = params.get("annotated_only", ["false"])[0].lower() == "true"

        result = []
        for case in _cases:
            cid = case.get("id", "")
            # 自动推断缺失字段
            if not case.get("risk_level") or not case.get("dimensions"):
                risk, dims = C.infer_risk_dimension(case)
                case.setdefault("risk_level", risk)
                case.setdefault("dimensions", dims)

            if risk_filter and case.get("risk_level") != risk_filter:
                continue
            if dim_filter and dim_filter not in (case.get("dimensions") or []):
                continue
            if annotated_only and cid not in _annotations_by_case:
                continue

            ann = _annotations_by_case.get(cid, {})
            result.append({
                "case_id": cid,
                "name": case.get("name", ""),
                "prompt": case.get("prompt", "")[:500],
                "risk_level": case.get("risk_level", ""),
                "dimensions": case.get("dimensions", []),
                "annotated": cid in _annotations_by_case,
                "auto_scores": self._get_auto_scores(case),
                "annotation": ann,
            })
        return result

    def _get_case_detail(self, cid):
        if not cid:
            return {"error": "case_id required"}
        for case in _cases:
            if case.get("id") == cid:
                ann = _annotations_by_case.get(cid, {})
                return {
                    "case": case,
                    "annotation": ann,
                    "auto_scores": self._get_auto_scores(case),
                }
        return {"error": "not found"}

    def _get_auto_scores(self, case):
        """获取自动化评分（如果有）。"""
        # 简化实现：返回空，由前端从 scores 目录读取
        return {}

    def _get_all_annotations(self):
        return list(_annotations_by_case.values())

    def _get_stats(self):
        from annotator import get_annotation_stats
        return get_annotation_stats(_cfg, _cases)

    def _save_annotation(self, body):
        cid = body.get("case_id", "")
        if not cid:
            return {"error": "case_id required"}

        ann = {
            "run_id": body.get("run_id", f"manual_{C.now_iso().replace(':', '-')[:16]}"),
            "case_id": cid,
            "annotator": body.get("annotator", "web"),
            "timestamp": C.now_iso(),
            "ground_truth": body.get("ground_truth", {}),
            "quality_labels": body.get("quality_labels", {}),
            "human_feedback": body.get("human_feedback", {}),
        }
        ann_path = _cfg.root / "annotations.jsonl"
        C.append_jsonl(ann_path, ann)
        _annotations_by_case[cid] = ann
        return {"ok": True, "case_id": cid}

    def _save_annotations_batch(self, body):
        annotations = body.get("annotations", [])
        saved = 0
        for item in annotations:
            cid = item.get("case_id", "")
            if not cid:
                continue
            ann = {
                "run_id": item.get("run_id", f"batch_{C.now_iso().replace(':', '-')[:16]}"),
                "case_id": cid,
                "annotator": item.get("annotator", "web_batch"),
                "timestamp": C.now_iso(),
                "ground_truth": item.get("ground_truth", {}),
                "quality_labels": item.get("quality_labels", {}),
                "human_feedback": item.get("human_feedback", {}),
            }
            ann_path = _cfg.root / "annotations.jsonl"
            C.append_jsonl(ann_path, ann)
            _annotations_by_case[cid] = ann
            saved += 1
        return {"ok": True, "saved": saved}

    def log_message(self, format, *args):
        pass


def start_annotate_server(config_path: str, port: int = 8766) -> None:
    _load_data(config_path)
    server = HTTPServer(("127.0.0.1", port), AnnotateHandler)
    print(f"[annotate_server] 标注服务已启动: http://127.0.0.1:{port}")
    print(f"[annotate_server] 共 {_cases.__len__()} 条用例, {len(_annotations_by_case)} 条标注")
    print(f"[annotate_server] 按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[annotate_server] 已停止")
        server.server_close()


def main() -> int:
    ap = argparse.ArgumentParser(description="标注 Web 服务")
    ap.add_argument("--config", required=True)
    ap.add_argument("--port", type=int, default=8766)
    args = ap.parse_args()
    start_annotate_server(args.config, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())