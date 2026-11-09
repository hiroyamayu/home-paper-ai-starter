"""テスト用のAI と Google カレンダーの代役（モック）。決まった答えを返すだけ。

- POST /v1/chat/completions                   … paperless-gpt から（OpenAI 互換）
- POST /v1beta/models/<model>:generateContent … 予定の取り出し・カレンダーの判定から（Gemini）
- /calendar/v3/calendars/<cal>/events[/<id>]  … scripts/sync_calendar.py から（Google カレンダー）
- GET /_calendar                               … テストが中身を確かめる
"""
import re
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EVENTS = [{"date": "2026-11-11", "weekday": "水", "end_date": None, "title": "校外学習", "target": "2年",
           "items": "お弁当・水筒・レジャーシート"},
          # 曜日が合わない（1 日ずれた読み違い）。extract_events.py が捨てるはず
          {"date": "2026-11-17", "weekday": "月", "end_date": None, "title": "ずれた予定", "target": None,
           "items": None}]


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


CALENDAR = {}   # cal -> {event_id: body}


def judge(prompt):
    m = re.search(r"<events>\n(.*)\n</events>", prompt, re.S)
    items = json.loads(m.group(1)) if m else []
    return [{"key": e["key"], "include": True, "calendar": (e.get("tags") or ["家族"])[0], "reason": "テスト"}
            for e in items]


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cal(self):
        m = re.match(r".*/calendar/v3/calendars/([^/]+)/events(?:/([^/?]+))?", self.path)
        return (m.group(1), m.group(2)) if m else (None, None)

    def do_GET(self):
        if self.path.startswith("/_calendar"):
            return self._send(200, CALENDAR)
        cal, eid = self._cal()
        if cal:
            ev = CALENDAR.get(cal, {}).get(eid)
            return self._send(200, ev) if ev else self._send(404, {"error": "not found"})
        self._send(200, {"ok": True})

    def do_PUT(self):
        cal, eid = self._cal()
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        CALENDAR.setdefault(cal, {})[eid] = {**body, "status": "confirmed"}
        print("calendar: put", cal, body.get("summary"), flush=True)
        self._send(200, body)

    def do_DELETE(self):
        cal, eid = self._cal()
        ev = CALENDAR.get(cal, {}).get(eid)
        if not ev:
            return self._send(404, {"error": "not found"})
        ev["status"] = "cancelled"
        print("calendar: delete", cal, eid, flush=True)
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        cal, _ = self._cal()
        if cal:
            ev = CALENDAR.setdefault(cal, {}).get(req["id"])
            if ev and ev.get("status") != "cancelled":
                return self._send(409, {"error": "duplicate"})
            if ev:   # 本物の Google カレンダーも、消した予定と同じ ID では作り直せない
                return self._send(409, {"error": "duplicate (deleted)"})
            CALENDAR[cal][req["id"]] = {**req, "status": "confirmed"}
            print("calendar: insert", cal, req.get("summary"), flush=True)
            return self._send(200, req)
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
            prompt = "".join(p.get("text", "") for c in req.get("contents", []) for p in c.get("parts", []))
            if "カレンダーの決まり" in prompt:
                out = judge(prompt)
                print("gemini: judge", len(out), flush=True)
            else:
                out = EVENTS
                print("gemini: events", flush=True)
            self._send(200, {"candidates": [{"content": {"parts": [
                {"text": json.dumps(out, ensure_ascii=False)}]}}]})
        else:
            self._send(404, {"error": self.path})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
