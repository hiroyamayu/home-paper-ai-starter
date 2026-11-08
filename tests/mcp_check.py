"""MCP サーバーの道具を、そのまま呼んで確かめる（tools コンテナの中で動かす）。"""
import asyncio
import sys

sys.path.insert(0, "scripts")
import mcp_server as m  # noqa: E402

names = {t.name for t in asyncio.run(m.mcp.list_tools())}
assert names == {"search_documents", "get_document_text", "search_events"}, names
print("道具：", sorted(names))

found = m.search_documents("Field trip")
print("search_documents:", [(d["id"], d["title"]) for d in found])
assert found, "書類が見つからない"
assert all("Private copy" not in m.get_document_text(d["id"]) for d in found), "private の書類が検索に出た"

hidden = m.search_documents("Private copy")
assert not hidden, f"private の書類が検索に出た：{hidden}"

ev = m.search_events(start="2026-11-11", end="2026-11-11")
print("search_events:", ev)
assert any("校外学習" in e["title"] for e in ev), "予定が引けない"
assert not m.search_events(query="存在しない行事"), "関係ない予定が出た"
print("OK：MCP の道具")
