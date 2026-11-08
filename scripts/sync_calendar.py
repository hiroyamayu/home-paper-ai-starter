"""取り出した予定のうち、家に関係するものだけを、人ごとの Google カレンダーに書き込む（3 章）。

  docker compose run --rm tools python scripts/sync_calendar.py            # 書き込む
  docker compose run --rm tools python scripts/sync_calendar.py --dry-run  # 書き込まずに、何をするかだけ表示
  docker compose run --rm tools python scripts/sync_calendar.py --today 2026-11-10   # 日付を決めて試す

流れ：
  1. data/events.json の予定を、同じ行事ごとにまとめる（今日より前のものは扱わない）
  2. config/calendar_rules.md の決まりに沿って、入れる・外す・どのカレンダーかを AI に選ばせる
     （前回の判定も一緒に渡して、実行するたびに結果が揺れないようにする）
  3. 入れる予定を、config/calendars.json のカレンダーに書き込む。予定の ID はこちらで決める
  4. 書き込んだはずの予定が消えていたら「人が消した」と覚えて、二度と書き込まない

使うもの：
  config/calendars.json       … 人の名前 → カレンダー ID（calendars.example.json を写して作る）
  config/service-account.json … Google Cloud のサービスアカウントの鍵
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import urllib.parse
from zoneinfo import ZoneInfo

import requests

from common import event_key, gemini_json, load_json, merge, save_json

CONFIG = os.environ.get("CONFIG_DIR", os.path.join(os.path.dirname(__file__), "..", "config"))
GOOGLE_API_BASE = os.environ.get("GOOGLE_API_BASE", "https://www.googleapis.com").rstrip("/")
STATE = "calendar_state.json"

JUDGE_PROMPT = """あなたは家庭の予定の整理係です。
下の「カレンダーの決まり」に沿って、最後に並べた予定を 1 件ずつ、カレンダーに入れるかどうか決めてください。

{rules}

## 予定の見方
- tags は、その予定が書かれていた書類に付いた人のタグ（どの子の書類か）
- previous は前回の判定。決まりに照らして明らかにおかしくなければ、前回と同じにする

## 答え方
次の形の JSON の配列で、すべての予定に答える。
[{{"key": "予定の key", "include": true または false, "calendar": "{calendars} のどれか（入れないときは null）", "reason": "短い理由"}}]

<events>
{events}
</events>
"""


def google_token():
    if os.environ.get("GOOGLE_FAKE_TOKEN"):           # テスト用
        return os.environ["GOOGLE_FAKE_TOKEN"]
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    key = os.path.join(CONFIG, "service-account.json")
    if not os.path.exists(key):
        sys.exit("config/service-account.json がありません（3 章：サービスアカウントの鍵）")
    creds = service_account.Credentials.from_service_account_file(
        key, scopes=["https://www.googleapis.com/auth/calendar.events"])
    creds.refresh(Request())
    return creds.token


class Calendar:
    def __init__(self, token):
        self.h = {"Authorization": f"Bearer {token}"}

    def _url(self, cal, event_id=""):
        url = f"{GOOGLE_API_BASE}/calendar/v3/calendars/{urllib.parse.quote(cal)}/events"
        return url + (f"/{event_id}" if event_id else "")

    def get(self, cal, event_id):
        r = requests.get(self._url(cal, event_id), headers=self.h, timeout=30)
        if r.status_code in (404, 410):
            return None
        r.raise_for_status()
        return r.json()

    def upsert(self, cal, body):
        r = requests.post(self._url(cal), headers=self.h, json=body, timeout=30)
        if r.status_code == 409:                        # すでにある → 上書き
            r = requests.put(self._url(cal, body["id"]), headers=self.h, json=body, timeout=30)
        r.raise_for_status()

    def delete(self, cal, event_id):
        r = requests.delete(self._url(cal, event_id), headers=self.h, timeout=30)
        if r.status_code not in (200, 204, 404, 410):
            r.raise_for_status()


def event_id(key):
    # 同じ予定には毎回同じ ID を付ける（何度流しても増えない）。
    # Google カレンダーの ID に使えるのは英小文字 a〜v と数字。home ＋ 16 進数はこの範囲に収まる
    return "home" + hashlib.sha1(key.encode()).hexdigest()


def candidates(today):
    store = load_json("events.json", {"docs": {}})
    events = []
    for d in store["docs"].values():
        for e in d["events"]:
            if (e.get("end_date") or e["date"]) >= today.isoformat():
                events.append({**e, "doc_title": d["title"], "tags": d.get("tags", [])})
    # 同じ日の同じ行事は 1 つにまとめる（日付ごとに）
    by_date = {}
    for e in events:
        by_date.setdefault(e["date"], []).append(e)
    out = []
    for day_events in by_date.values():
        for m in merge(day_events):
            same = [e for e in day_events if event_key(e) == event_key(m)]
            m["tags"] = sorted({t for e in same for t in e["tags"]})
            out.append(m)
    return sorted(out, key=lambda e: e["date"])


def judge(events, state, calendars):
    """決まりに沿って、入れる・外す・どのカレンダーかを AI に選ばせる。前回の判定も渡す"""
    rules = open(os.path.join(CONFIG, "calendar_rules.md"), encoding="utf-8").read()
    items = [{"key": event_key(e), "date": e["date"], "end_date": e.get("end_date"), "title": e["title"],
              "target": e.get("target"), "tags": e["tags"],
              "previous": state["judgements"].get(event_key(e))} for e in events]
    prompt = JUDGE_PROMPT.format(rules=rules, calendars="・".join(calendars),
                                 events=json.dumps(items, ensure_ascii=False, indent=1))
    answers = {a["key"]: a for a in gemini_json(prompt) if a.get("key")}
    for it in items:
        a = answers.get(it["key"])
        if a is None:                       # 答えが無いものは、前回の判定のままにする
            continue
        if a.get("include") and a.get("calendar") not in calendars:
            a = {**a, "include": False, "reason": f"カレンダー「{a.get('calendar')}」が無い"}
        state["judgements"][it["key"]] = {"include": bool(a.get("include")),
                                          "calendar": a.get("calendar"), "reason": a.get("reason")}


def body_for(e, key):
    end = dt.date.fromisoformat(e.get("end_date") or e["date"]) + dt.timedelta(days=1)
    lines = []
    if e.get("items"):
        lines.append(f"持ち物：{e['items']}")
    lines.append("原本：" + " / ".join(sorted(e["doc_titles"])))
    return {"id": event_id(key), "summary": e["title"], "description": "\n".join(lines),
            "start": {"date": e["date"]}, "end": {"date": end.isoformat()}}   # 終日の予定。終わりは「次の日」


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="書き込まずに、何をするかだけ表示する")
    ap.add_argument("--today", help="今日の日付を決めて試す（YYYY-MM-DD）")
    args = ap.parse_args()

    tz = ZoneInfo(os.environ.get("TZ", "Asia/Tokyo"))
    today = dt.date.fromisoformat(args.today) if args.today else dt.datetime.now(tz).date()
    cal_file = os.path.join(CONFIG, "calendars.json")
    if not os.path.exists(cal_file):
        sys.exit("config/calendars.json がありません（calendars.example.json を写して作る）")
    calendars = {k: v for k, v in json.load(open(cal_file, encoding="utf-8")).items() if not k.startswith("_")}

    state = load_json(STATE, {})
    state.setdefault("judgements", {})
    state.setdefault("written", {})
    state.setdefault("deleted", [])

    events = candidates(today)
    new = [e for e in events if event_key(e) not in state["judgements"]]
    if new:
        judge(events, state, calendars)    # 新しい予定があるときだけ、全体を前回の判定つきで見直す
        save_json(STATE, state)

    api = None if args.dry_run else Calendar(google_token())
    keep = set()
    for e in events:
        key = event_key(e)
        j = state["judgements"].get(key, {})
        if not j.get("include") or key in state["deleted"] or j.get("calendar") not in calendars:
            continue
        cal = calendars[j["calendar"]]
        w = state["written"].get(key)
        if w and api:
            got = api.get(w["calendar"], w["id"])
            if got is None or got.get("status") == "cancelled":
                state["deleted"].append(key)              # 人が消した → 二度と書き込まない
                state["written"].pop(key, None)
                print(f"人が消した予定：{e['date']} {e['title']}")
                continue
            if w["calendar"] != cal:                      # カレンダーが変わった → 古い方を消す
                api.delete(w["calendar"], w["id"])
        keep.add(key)
        print(f"{'（試し）' if args.dry_run else ''}書き込む：{e['date']} {e['title']} → {j['calendar']}")
        if api:
            api.upsert(cal, body_for(e, key))
            state["written"][key] = {"calendar": cal, "id": event_id(key)}

    # 前に書き込んだが、今は入れない予定（決まりを変えた・行事が無くなった）は消す
    for key in [k for k in state["written"] if k not in keep and k.split("|")[0] >= today.isoformat()]:
        w = state["written"].pop(key)
        print(f"{'（試し）' if args.dry_run else ''}消す：{key}")
        if api:
            api.delete(w["calendar"], w["id"])

    if not args.dry_run:
        save_json(STATE, state)


if __name__ == "__main__":
    main()
