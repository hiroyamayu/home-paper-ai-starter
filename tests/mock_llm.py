"""テスト用の偽の AI。決まった答えを返すだけ。

- POST /v1/chat/completions                 … paperless-gpt から（OpenAI 互換）
- POST /v1beta/models/<model>:generateContent … scripts/extract_events.py から（Gemini）
"""
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EVENTS = [{"date": "2026-11-11", "end_date": None, "title": "校外学習", "target": "2年",
           "items": "お弁当・水筒・レジャーシート"}]


def answer_for(prompt):
    if "タイトルを決めて" in prompt:
        return "校外学習のお知らせ"
    if "種類を、下の一覧から" in prompt:
        return "行事予定"
    if "付けるタグ" in prompt:
        return "長女"
    if "発信元（差出人）" in prompt:
        return "みどり小学校"
    if "YYYY-MM-DD 形式で 1 つだけ" in prompt:
        return "2026-11-05"
    return "その他"


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(200, {"ok": True})

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path.endswith("/chat/completions"):
            msgs = req.get("messages", [])
            text = ""
            for m in msgs:
                c = m.get("content")
                text += c if isinstance(c, str) else "".join(p.get("text", "") for p in c or [])
            out = answer_for(text)
            print("chat:", out, flush=True)
            self._send(200, {
                "id": "mock", "object": "chat.completion", "created": int(time.time()),
                "model": req.get("model", "mock"),
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": out}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})
        elif ":generateContent" in self.path:
            print("gemini: events", flush=True)
            self._send(200, {"candidates": [{"content": {"parts": [
                {"text": json.dumps(EVENTS, ensure_ascii=False)}]}}]})
        else:
            self._send(404, {"error": self.path})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
