"""Claude などの AI から、家の書類と予定を引くための MCP サーバー（6 章）。読み取り専用。

原則：
  1. 読み取り専用。書類やカレンダーを書き換える道具は作らない
  2. private の書類は、道具の側で必ず除く（AI への指示に頼らない）
  3. 道具の説明文に、いつ使うかを書く（AI はこれを読んで道具を選ぶ）

Claude Desktop からのつなぎ方は README の「AI から家の書類を引く」を参照。
"""
import json
import os
import re
import urllib.parse
import urllib.request

from mcp.server.mcpserver import MCPServer

PAPERLESS_URL = os.environ.get("PAPERLESS_URL", "http://localhost:8000").rstrip("/")
PUBLIC_URL = (os.environ.get("PAPERLESS_PUBLIC_URL") or PAPERLESS_URL).rstrip("/")
# 閲覧だけできるユーザーのトークンを使う（scripts/create_reader.py）。無ければ管理者のトークン
TOKEN = os.environ.get("PAPERLESS_READER_TOKEN") or os.environ.get("PAPERLESS_API_TOKEN", "")
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
HIDDEN_TAGS = ("private",)   # この名前のタグが付いた書類は、道具が返さない

mcp = MCPServer("home-docs", instructions=(
    "家の書類（学校・幼稚園のお便り、行事予定、給食の献立、家電の説明書・保証書、契約など）と、"
    "そこから取り出した行事予定を引くための道具です。家庭の予定・持ち物・提出物・家電について聞かれたら、"
    "推測で答えずにこの道具で調べ、答えには書類のタイトルと日付を添えてください。"))


def _get(path, params=None):
    url = f"{PAPERLESS_URL}/api/{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"Authorization": f"Token {TOKEN}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


_hidden_ids = None


def hidden_tag_ids():
    global _hidden_ids
    if _hidden_ids is None:
        tags = _get("tags/", {"page_size": 1000})["results"]
        _hidden_ids = {t["id"] for t in tags if t["name"] in HIDDEN_TAGS}
    return _hidden_ids


def _names(path):
    return {x["id"]: x["name"] for x in _get(path, {"page_size": 1000})["results"]}


@mcp.tool()
def search_documents(query: str, limit: int = 10) -> list[dict]:
    """家の書類を、本文の言葉で全文検索する。
    学校・幼稚園のお便り、行事、持ち物、提出物、給食、家電の使い方や保証、契約について聞かれたら、まずこれで探す。
    返すのは id・タイトル・日付・発信元・種類・原本の URL。本文が要るときは get_document_text に id を渡す。"""
    params = {"query": query, "page_size": max(1, min(limit, 25))}
    hidden = hidden_tag_ids()
    if hidden:
        params["tags__id__none"] = ",".join(map(str, hidden))   # private は返さない
    corr, types = _names("correspondents/"), _names("document_types/")
    return [{"id": d["id"], "title": d["title"], "created": (d.get("created") or "")[:10],
             "correspondent": corr.get(d.get("correspondent")), "document_type": types.get(d.get("document_type")),
             "url": f"{PUBLIC_URL}/documents/{d['id']}/details"}
            for d in _get("documents/", params)["results"]]


@mcp.tool()
def get_document_text(id: int, max_chars: int = 8000) -> str:
    """書類 1 件の本文（OCR で読んだ文字）を返す。search_documents で見つけた id を渡す。
    表は行と列が崩れていることがあるので、日付や持ち物は search_events の結果と突き合わせる。"""
    d = _get(f"documents/{int(id)}/")
    if set(d.get("tags", [])) & hidden_tag_ids():
        return "この書類は読めません（AI に渡さない書類です）。"
    head = f"タイトル：{d['title']}\n日付：{(d.get('created') or '')[:10]}\n原本：{PUBLIC_URL}/documents/{d['id']}/details\n\n"
    return head + (d.get("content") or "")[:max(500, min(max_chars, 30000))]


@mcp.tool()
def search_events(start: str = "", end: str = "", query: str = "") -> list[dict]:
    """プリントから取り出した行事予定を探す。日付は YYYY-MM-DD。
    「明日の持ち物は？」「来週の行事は？」「持久走大会はいつ？」のような質問では、まずこれを使う。
    返すのは日付・行事名・対象・持ち物・どの子の書類か（tags）・元の書類。"""
    path = os.path.join(DATA_DIR, "events.json")
    if not os.path.exists(path):
        return []
    store = json.load(open(path, encoding="utf-8"))
    q = re.sub(r"\s", "", query)
    out = []
    for d in store["docs"].values():
        if set(d.get("tags", [])) & set(HIDDEN_TAGS):
            continue
        for e in d["events"]:
            last = e.get("end_date") or e["date"]
            if start and last < start or end and e["date"] > end:
                continue
            if q and q not in re.sub(r"\s", "", f"{e['title']}{e.get('items') or ''}{e.get('target') or ''}"):
                continue
            out.append({**e, "tags": d.get("tags", []), "document": d["title"]})
    return sorted(out, key=lambda e: e["date"])[:100]


if __name__ == "__main__":
    mcp.run()   # 標準入出力でつなぐ（Claude Desktop 用）
