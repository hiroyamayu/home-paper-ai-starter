"""MCP サーバー（6 章）用に、書類を見ることだけができる Paperless のユーザーを作り、そのトークンを表示する。
出た値を .env の PAPERLESS_READER_TOKEN に書く。

  docker compose run --rm tools python scripts/create_reader.py

管理者のトークンを MCP に使い回すと、道具にバグがあったときに書類を書き換えられてしまう。
閲覧だけのユーザーなら、道具が何をしても書類は変わらない。

タグ・書類の種類・発信元の持ち主も外す（reader から private タグが見えないと、MCP が private を除けないため）。
発信元やタグが増えたら、もう一度動かす（何度動かしてもよい。トークンは作り直される）。

注意：Paperless は、画面や API でアップロードした書類の持ち主を、アップロードした人にする。
持ち主のいる書類は、ほかのユーザー（reader）からは見えない。consume フォルダーに置いた書類は持ち主がいないので見える。
"""
import json
import os
import secrets
import sys
import urllib.parse
import urllib.request

from common import PAPERLESS_URL, paperless, paperless_all

USERNAME = os.environ.get("PAPERLESS_READER_USER", "reader")
PERMS = ["view_document", "view_tag", "view_correspondent", "view_documenttype", "view_note"]


def main():
    password = secrets.token_urlsafe(24)
    users = [u for u in paperless_all("users/") if u["username"] == USERNAME]
    body = {"username": USERNAME, "password": password, "is_active": True,
            "is_staff": False, "is_superuser": False, "user_permissions": PERMS}
    if users:
        paperless("PATCH", f"users/{users[0]['id']}/", body=body)
    else:
        paperless("POST", "users/", body=body)
    # タグ・書類の種類・発信元は、作った人（管理者）が持ち主になっていて、reader からは見えない。
    # 見えないと MCP が private を除けないので、持ち主を外して誰でも見えるようにする（名前だけで、書類の中身ではない）
    for path in ("tags/", "document_types/", "correspondents/"):
        for x in paperless_all(path):
            if x.get("owner") is not None:
                paperless("PATCH", f"{path}{x['id']}/", body={"owner": None})
    data = urllib.parse.urlencode({"username": USERNAME, "password": password}).encode()
    with urllib.request.urlopen(urllib.request.Request(PAPERLESS_URL + "/api/token/", data=data), timeout=30) as r:
        print(json.loads(r.read())["token"])
    print(f"（ユーザー {USERNAME} を作りました。パスワードは使わないので、どこにも残していません）", file=sys.stderr)


if __name__ == "__main__":
    main()
