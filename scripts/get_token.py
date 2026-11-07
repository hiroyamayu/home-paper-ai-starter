"""Paperless-ngx の API トークンを作って表示する。出た値を .env の PAPERLESS_API_TOKEN に書く。

  docker compose run --rm tools python scripts/get_token.py
"""
import json
import os
import sys
import urllib.parse
import urllib.request

url = os.environ.get("PAPERLESS_URL", "http://localhost:8000").rstrip("/") + "/api/token/"
user = os.environ.get("PAPERLESS_ADMIN_USER")
password = os.environ.get("PAPERLESS_ADMIN_PASSWORD")
if not user or not password:
    sys.exit(".env に PAPERLESS_ADMIN_USER と PAPERLESS_ADMIN_PASSWORD を書いてください")

data = urllib.parse.urlencode({"username": user, "password": password}).encode()
with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as r:
    print(json.loads(r.read())["token"])
