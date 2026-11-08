"""明日の予定があれば、Pushover でスマホに知らせる（4 章の最小版）。

  docker compose run --rm tools python scripts/notify_tomorrow.py
  docker compose run --rm tools python scripts/notify_tomorrow.py --today 2026-11-10   # 日付を決めて試す

PUSHOVER_TOKEN が空なら、送らずに文面を画面に出すだけ。
予定が無い日は何も送らない。
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

from common import PAPERLESS_URL, data_path

WEEKDAYS = "月火水木金土日"


def events_on(day):
    path = data_path("events.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        store = json.load(f)
    out = []
    for doc_id, d in store["docs"].items():
        for e in d["events"]:
            start = e["date"]
            end = e.get("end_date") or start
            if start <= day.isoformat() <= end:
                out.append({**e, "doc_id": doc_id, "doc_title": d["title"]})
    return out


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


def compose(day, events):
    lines = [f"明日 {day.month}/{day.day}（{WEEKDAYS[day.weekday()]}）の予定", ""]
    for e in events:
        head = f"■ {e['title']}" + (f"（{e['target']}）" if e.get("target") else "")
        lines.append(head)
        if e.get("items"):
            lines.append(f"  {e['items']}")
    lines.append("")
    lines.append("原本：" + " / ".join(sorted(set().union(*(e["doc_titles"] for e in events)))))
    return "\n".join(lines)


def send(title, message, url):
    token = os.environ.get("PUSHOVER_TOKEN", "")
    users = [u.strip() for u in os.environ.get("PUSHOVER_USERS", "").split(",") if u.strip()]
    if not token or not users:
        print("（PUSHOVER_TOKEN か PUSHOVER_USERS が空なので、送らずに表示します）\n")
        print(message)
        return
    for user in users:
        data = urllib.parse.urlencode({"token": token, "user": user, "title": title,
                                       "message": message, "url": url, "url_title": "原本を開く"}).encode()
        for wait in (0, 60, 300):   # 送るのに失敗したら、同じ文面で送り直す
            time.sleep(wait)
            try:
                urllib.request.urlopen("https://api.pushover.net/1/messages.json", data, timeout=10)
                break
            except OSError as e:
                print(f"送れませんでした（{e}）。送り直します", file=sys.stderr)
        else:
            sys.exit("Pushover に送れませんでした")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", help="今日の日付を決めて試す（YYYY-MM-DD）")
    args = ap.parse_args()
    tz = ZoneInfo(os.environ.get("TZ", "Asia/Tokyo"))
    today = dt.date.fromisoformat(args.today) if args.today else dt.datetime.now(tz).date()
    tomorrow = today + dt.timedelta(days=1)

    events = merge(events_on(tomorrow))
    if not events:
        print(f"{tomorrow} の予定はありません。送りません")
        return
    first = events[0]["doc_id"]
    base = os.environ.get("PAPERLESS_PUBLIC_URL") or PAPERLESS_URL   # スマホから開ける URL
    send("明日の予定", compose(tomorrow, events), f"{base.rstrip('/')}/documents/{first}/details")


if __name__ == "__main__":
    main()
