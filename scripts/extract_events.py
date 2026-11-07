"""「行事予定」の書類から予定を取り出して、data/events.json にためる（3 章の最小版）。

  docker compose run --rm tools python scripts/extract_events.py          # まだ読んでいない書類を読む
  docker compose run --rm tools python scripts/extract_events.py --doc 12 # 1 件だけ読み直す

表は OCR の本文にすると崩れるので、PDF をそのまま Gemini に渡して読ませる。
private の書類と、まだ AI の名付けが済んでいない書類は読まない。
"""
import argparse
import json
import os

from common import data_path, gemini_json, paperless, paperless_all

DOC_TYPE = "行事予定"
EVENTS_FILE = data_path("events.json")

PROMPT = """あなたは家庭の予定の整理係です。添付の PDF は、学校・幼稚園などから届いた行事予定です。
書類の題名：{title}
書類の日付：{created}

この書類に書かれている予定を、次の形の JSON の配列で返してください。
[{{"date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD または null", "title": "行事の名前",
   "target": "対象（学年・組など。書かれていなければ null）", "items": "持ち物・準備（書かれていなければ null）"}}]

守ること：
- 書かれていないことを推測で埋めない。読めない・書かれていない項目は null にする
- 年が書かれていない日付は、書類の日付から考えて最も自然な年にする
- 毎日の授業や、行事でないもの（「通常授業」など）は入れない
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
    if DOC_TYPE not in types:
        raise SystemExit(f"書類の種類「{DOC_TYPE}」がありません。先に setup_paperless.py を動かしてください")
    skip = [str(tags[n]) for n in ("private", "paperless-gpt-auto") if n in tags]
    params = {"document_type__id": types[DOC_TYPE], "ordering": "id"}
    if skip:
        params["tags__id__none"] = ",".join(skip)
    return paperless_all("documents/", params)


def extract(doc):
    pdf = paperless("GET", f"documents/{doc['id']}/download/", {"original": "true"}, raw=True)
    prompt = PROMPT.format(title=doc["title"], created=(doc.get("created") or "")[:10])
    events = gemini_json(prompt, pdf)
    clean = [{k: (e.get(k) or None) for k in ("date", "end_date", "title", "target", "items")}
             for e in events if e.get("date") and e.get("title")]
    return sorted(clean, key=lambda e: e["date"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", type=int, help="この書類だけ読み直す")
    args = ap.parse_args()

    store = load()
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
        store["docs"][key] = {"title": d["title"], "modified": d["modified"], "events": events}
        save(store)
        print(f"#{d['id']} {d['title']}：{len(events)} 件")
    if not docs:
        print(f"「{DOC_TYPE}」の書類はまだありません")


if __name__ == "__main__":
    main()
