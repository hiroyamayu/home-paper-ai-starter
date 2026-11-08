"""MCP サーバー（6 章）用に、書類を見ることだけができる Paperless のユーザーを作り、そのトークンを表示する。
出た値を .env の PAPERLESS_READER_TOKEN に書く。

  docker compose run --rm tools python scripts/create_reader.py

管理者のトークンを MCP に使い回すと、道具にバグがあったときに書類を書き換えられてしまう。
閲覧だけのユーザーなら、道具が何をしても書類は変わらない。

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
    data = urllib.parse.urlencode({"username": USERNAME, "password": password}).encode()
    with urllib.request.urlopen(urllib.request.Request(PAPERLESS_URL + "/api/token/", data=data), timeout=30) as r:
        print(json.loads(r.read())["token"])
    print(f"（ユーザー {USERNAME} を作りました。パスワードは使わないので、どこにも残していません）", file=sys.stderr)


if __name__ == "__main__":
    main()
