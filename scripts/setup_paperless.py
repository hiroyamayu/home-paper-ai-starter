"""Paperless-ngx の最初の設定（タグ・書類の種類・ワークフロー）を作る。何度動かしても同じ結果になる。

  docker compose run --rm tools python scripts/setup_paperless.py

作るもの：
  タグ        paperless-gpt-auto（AI に渡す目印）、要確認、private、人のタグ
  書類の種類  行事予定 ほか（3 章で予定を取り出す対象は「行事予定」）
  ワークフロー
    1. consume/private/ に入れた書類に private を付ける
    2. private が付いていない書類に、取り込み完了時に paperless-gpt-auto を付ける（AI に渡す）
       「更新時」には付けない。AI が書き戻すたびにまた AI に渡るループになるため（2 章・12 章）
"""
from common import paperless, paperless_all

CONSUMPTION, ADDED = 1, 2   # ワークフローのきっかけ：取り込み開始時・追加時
ASSIGN = 1                  # 動作：付ける
CONSUME_FOLDER, API_UPLOAD, WEB_UI = 1, 2, 4

# 人のタグ。自分の家に合わせて書き換える（prompts/ の「世帯の前提」とそろえる）
PEOPLE = ["長女", "長男", "次男"]
TAGS = ["paperless-gpt-auto", "要確認", "private"] + PEOPLE
DOCUMENT_TYPES = ["行事予定", "お便り", "給食献立", "時間割", "取扱説明書", "保証書", "契約書", "テスト", "その他"]


def ensure(path, name):
    for x in paperless_all(path, {"name__iexact": name}):
        if x["name"] == name:
            return x["id"]
    created = paperless("POST", path, body={"name": name, "matching_algorithm": 0})
    print(f"  作成：{path}{name}")
    return created["id"]


def ensure_workflow(name, order, triggers, actions):
    for w in paperless_all("workflows/"):
        if w["name"] == name:
            print(f"  あり：ワークフロー {name}")
            return
    paperless("POST", "workflows/", body={"name": name, "order": order, "enabled": True,
                                          "triggers": triggers, "actions": actions})
    print(f"  作成：ワークフロー {name}")


def trigger(kind, **kw):
    return {"type": kind, "matching_algorithm": 0, "match": "", "is_insensitive": True,
            "sources": [CONSUME_FOLDER, API_UPLOAD, WEB_UI], **kw}


def main():
    print("タグ")
    tag = {n: ensure("tags/", n) for n in TAGS}
    print("書類の種類")
    for n in DOCUMENT_TYPES:
        ensure("document_types/", n)
    print("ワークフロー")
    ensure_workflow("private フォルダー", 10,
                    [trigger(CONSUMPTION, filter_path="*/private/*", sources=[CONSUME_FOLDER])],
                    [{"type": ASSIGN, "assign_tags": [tag["private"]]}])
    ensure_workflow("AI に渡す", 20,
                    [trigger(ADDED, filter_has_not_tags=[tag["private"]])],
                    [{"type": ASSIGN, "assign_tags": [tag["paperless-gpt-auto"]]}])
    print("できました")


if __name__ == "__main__":
    main()
