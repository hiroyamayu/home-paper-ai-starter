"""Paperless-ngx と Gemini を呼ぶための小さな道具。Python の標準ライブラリだけで動く。"""
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

PAPERLESS_URL = os.environ.get("PAPERLESS_URL", "http://localhost:8000").rstrip("/")
PAPERLESS_TOKEN = os.environ.get("PAPERLESS_API_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
# テストでは AI の代役（モック）に向けるために差し替える
GEMINI_API_BASE = os.environ.get("GEMINI_API_BASE", "https://generativelanguage.googleapis.com").rstrip("/")
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))


def _request(method, url, headers=None, data=None, timeout=60):
    req = urllib.request.Request(url, method=method, headers=headers or {}, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def paperless(method, path, params=None, body=None, raw=False):
    """Paperless-ngx の API を呼ぶ。path は /api/ のあと（例：documents/）"""
    if not PAPERLESS_TOKEN:
        sys.exit("PAPERLESS_API_TOKEN が設定されていません（scripts/get_token.py で作れます）")
    url = f"{PAPERLESS_URL}/api/{path.lstrip('/')}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Authorization": f"Token {PAPERLESS_TOKEN}", "Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    status, content = _request(method, url, headers, data)
    if status >= 400:
        sys.exit(f"Paperless の API がエラーを返しました（{status} {path}）：{content[:300]!r}")
    if raw:
        return content
    return json.loads(content) if content else None


def paperless_all(path, params=None):
    """ページをまたいで、結果を全部集める"""
    params = dict(params or {}, page_size=100, page=1)
    out = []
    while True:
        page = paperless("GET", path, params)
        out += page["results"]
        if not page.get("next"):
            return out
        params["page"] += 1


def gemini_json(prompt, pdf_bytes=None):
    """Gemini に（あれば PDF を添えて）頼み、JSON で受け取る。呼ぶのは 1 回だけ"""
    if not GEMINI_API_KEY:
        sys.exit("GEMINI_API_KEY が設定されていません")
    parts = [{"text": prompt}]
    if pdf_bytes is not None:
        parts.append({"inline_data": {"mime_type": "application/pdf",
                                      "data": base64.b64encode(pdf_bytes).decode()}})
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    url = f"{GEMINI_API_BASE}/v1beta/models/{GEMINI_MODEL}:generateContent"
    status, content = _request("POST", url, {"x-goog-api-key": GEMINI_API_KEY,
                                             "Content-Type": "application/json"},
                               json.dumps(body).encode(), timeout=300)
    if status != 200:
        raise RuntimeError(f"Gemini がエラーを返しました（{status}）：{content[:300]!r}")
    r = json.loads(content)
    text = "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"])
    return json.loads(text)


def data_path(name):
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, name)


def load_json(name, default):
    path = data_path(name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(name, obj):
    path = data_path(name)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(path + ".tmp", path)


def _core(title):
    """かっこの中と空白を除いた行事名（「校外学習（市民の森公園）」→「校外学習」）"""
    return re.sub(r"[（(].*?[）)]|\s", "", title)


def merge(events):
    """同じ日に同じ行事が複数のプリントから出たら 1 つにまとめる。持ち物が一番詳しいものを残す"""
    out = []
    for e in sorted(events, key=lambda e: -len(e.get("items") or "")):
        core = _core(e["title"])
        same = next((o for o in out if core and (core in _core(o["title"]) or _core(o["title"]) in core)), None)
        if same:
            same["doc_titles"].add(e["doc_title"])
            if not same.get("target") and e.get("target"):
                same["target"] = e["target"]
        else:
            out.append({**e, "doc_titles": {e["doc_title"]}})
    return out


def event_key(e):
    """同じ行事を見分けるための鍵（日付と、かっこを除いた行事名）"""
    return f"{e['date']}|{_core(e['title'])}"
