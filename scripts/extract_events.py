"""「行事予定」と「お便り」の書類から予定を取り出して、data/events.json にためる（3 章の最小版）。

  docker compose run --rm tools python scripts/extract_events.py          # まだ読んでいない書類を読む
  docker compose run --rm tools python scripts/extract_events.py --doc 12 # 1 件だけ読み直す

表は OCR の本文にすると崩れるので、PDF をそのまま Gemini に渡して読ませる。
private の書類と、まだ AI の名付けが済んでいない書類は読まない。
"""
import argparse
import datetime as dt
import json
import os

from common import data_path, gemini_json, paperless, paperless_all

# 予定を取り出す書類の種類。お便り（学年だより・お知らせ）にも、行事と持ち物が書いてあることが多い
DOC_TYPES = ["行事予定", "お便り"]
EVENTS_FILE = data_path("events.json")
WEEKDAYS = "月火水木金土日"

PROMPT = """あなたは家庭の予定の整理係です。添付の PDF は、学校・幼稚園などから届いた行事予定やお便りです。
書類の題名：{title}
書類の日付：{created}

この書類に書かれている予定を、次の形の JSON の配列で返してください。
[{{"date": "YYYY-MM-DD", "weekday": "書類に印刷された曜日 1 文字（月〜日。書かれていなければ null）",
   "end_date": "YYYY-MM-DD または null", "title": "行事の名前",
   "target": "対象（学年・組など。書かれていなければ null）", "items": "持ち物・準備（書かれていなければ null）"}}]

守ること：
- 書かれていないことを推測で埋めない。読めない・書かれていない項目は null にする
- 年が書かれていない日付は、書類の日付から考えて最も自然な年にする
- 毎日の授業や、行事でないもの（「通常授業」など）は入れない
- 日付と曜日は、その行に印刷されているとおりに書く。表の並び順から数えて日付を決めない
- 予定が 1 つも無ければ [] を返す
"""


def load():
    if os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"docs": {}}


def save(store):
    tmp = EVENTS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=1)
    os.replace(tmp, EVENTS_FILE)


def candidates():
    types = {t["name"]: t["id"] for t in paperless_all("document_types/")}
    tags = {t["name"]: t["id"] for t in paperless_all("tags/")}
    missing = [n for n in DOC_TYPES if n not in types]
    if missing:
        raise SystemExit(f"書類の種類「{'・'.join(missing)}」がありません。先に setup_paperless.py を動かしてください")
    skip = [str(tags[n]) for n in ("private", "paperless-gpt-auto") if n in tags]
    params = {"document_type__id__in": ",".join(str(types[n]) for n in DOC_TYPES), "ordering": "id"}
    if skip:
        params["tags__id__none"] = ",".join(skip)
    return paperless_all("documents/", params)


def extract(doc):
    pdf = paperless("GET", f"documents/{doc['id']}/download/", {"original": "true"}, raw=True)
    prompt = PROMPT.format(title=doc["title"], created=(doc.get("created") or "")[:10])
    events = gemini_json(prompt, pdf)
    clean = []
    for e in events:
        if not (e.get("date") and e.get("title")):
            continue
        bad = weekday_mismatch(e)
        if bad:
            print(f"  #{doc['id']} 曜日が合わないので入れません：{bad}")
            continue
        clean.append({k: (e.get(k) or None) for k in ("date", "end_date", "title", "target", "items")})
    return sorted(clean, key=lambda e: e["date"])


def weekday_mismatch(e):
    """印刷の曜日と、日付から計算した曜日が違えば理由を返す（日付の読み違いを捨てる）。"""
    try:
        d = dt.date.fromisoformat(e["date"])
    except ValueError:
        return f"{e['date']} は日付として読めない"
    wd = (e.get("weekday") or "").strip()[:1]
    if wd and wd != WEEKDAYS[d.weekday()]:
        return f"{e['date']}（{wd}）{e.get('title')}。実際は {WEEKDAYS[d.weekday()]} 曜日"
    return None


def tag_names():
    return {t["id"]: t["name"] for t in paperless_all("tags/")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", type=int, help="この書類だけ読み直す")
    args = ap.parse_args()

    store = load()
    names = tag_names()
    docs = [paperless("GET", f"documents/{args.doc}/")] if args.doc else candidates()
    for d in docs:
        key = str(d["id"])
        if not args.doc and store["docs"].get(key, {}).get("modified") == d["modified"]:
            continue   # 前に読んでから変わっていない
        try:
            events = extract(d)
        except RuntimeError as e:
            print(f"#{d['id']} {d['title']}：読めませんでした（{e}）")
            continue
        # 書類に付いたタグ（長女・長男など）も残す。3 章でカレンダーを選ぶときに使う
        tags = [names[t] for t in d.get("tags", []) if t in names]
        store["docs"][key] = {"title": d["title"], "modified": d["modified"], "tags": tags, "events": events}
        save(store)
        print(f"#{d['id']} {d['title']}：{len(events)} 件")
    if not docs:
        print(f"「{'・'.join(DOC_TYPES)}」の書類はまだありません")


if __name__ == "__main__":
    main()
