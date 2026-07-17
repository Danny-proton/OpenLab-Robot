#!/usr/bin/env python3
"""sse_stream.py — SSE（Server-Sent Events）流式推送评测实时进度。

可选功能，评测运行中通过 SSE endpoint 查看实时进度。

用法:
  python sse_stream.py --port 8765 --config .agent-eval/config.yaml

客户端:
  curl http://localhost:8765/events
  # 或在浏览器 EventSource: new EventSource('http://localhost:8765/events')
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))


# ---------------------------------------------------------------------------
# 全局事件队列
# ---------------------------------------------------------------------------

_events: list[dict] = []
_events_lock = threading.Lock()
_clients: list[Any] = []
_clients_lock = threading.Lock()


def push_event(event_type: str, data: dict) -> None:
    """推送一条 SSE 事件。"""
    evt = {
        "event": event_type,
        "data": json.dumps(data, ensure_ascii=False),
        "timestamp": time.time(),
    }
    with _events_lock:
        _events.append(evt)
    with _clients_lock:
        for q in _clients:
            try:
                q.put(evt)
            except Exception:
                pass


def push_eval_progress(
    run_id: str,
    case_id: str,
    step: str,
    status: str,
    detail: str = "",
    score: float | None = None,
) -> None:
    """推送评测进度事件。"""
    push_event("eval_progress", {
        "run_id": run_id,
        "case_id": case_id,
        "step": step,
        "status": status,
        "detail": detail,
        "score": score,
    })


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class SSEHandler(BaseHTTPRequestHandler):
    """SSE endpoint handler。"""

    def do_GET(self):
        if self.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            # 发送历史事件
            with _events_lock:
                for evt in _events:
                    self._send_sse(evt)

            # 发送心跳
            self.wfile.write(f": heartbeat\n\n".encode("utf-8"))
            self.wfile.flush()

            # 等待新事件（简单实现：轮询）
            last_idx = len(_events)
            try:
                while True:
                    time.sleep(1)
                    with _events_lock:
                        if len(_events) > last_idx:
                            for evt in _events[last_idx:]:
                                self._send_sse(evt)
                            last_idx = len(_events)
                            self.wfile.write(f": heartbeat\n\n".encode("utf-8"))
                            self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
        elif self.path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            with _events_lock:
                self.wfile.write(json.dumps({
                    "total_events": len(_events),
                    "recent": _events[-10:],
                }, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def _send_sse(self, evt: dict) -> None:
        try:
            self.wfile.write(f"event: {evt['event']}\n".encode("utf-8"))
            self.wfile.write(f"data: {evt['data']}\n\n".encode("utf-8"))
            self.wfile.flush()
        except (BrokenPipeError, OSError):
            pass

    def log_message(self, format, *args):
        pass  # 静默日志


def start_sse_server(port: int) -> None:
    """在后台线程启动 SSE 服务器。"""
    server = HTTPServer(("127.0.0.1", port), SSEHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    sys.stdout.write(f"[sse_stream] SSE 服务已启动: http://127.0.0.1:{port}/events\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="SSE 流式推送")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    start_sse_server(args.port)
    sys.stdout.write("[sse_stream] 按 Ctrl+C 停止\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sys.stdout.write("\n[sse_stream] 已停止\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())