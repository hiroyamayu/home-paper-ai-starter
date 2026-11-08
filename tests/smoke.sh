#!/usr/bin/env bash
# 取り込み → AI の名付け → 予定の取り出し → 明日のお知らせ を、偽の AI で通しで確かめる。
#   bash tests/smoke.sh
set -euo pipefail
cd "$(dirname "$0")/.."

DC="docker compose -f compose.yml -f tests/compose.ci.yml"
API=http://localhost:8000/api

step() { echo; echo "=== $*"; }
fail() { echo "NG: $*"; $DC logs --tail=80 webserver paperless-gpt mock || true; exit 1; }

step "準備"
cp tests/ci.env .env
{ echo "PUID=$(id -u)"; echo "PGID=$(id -g)"; } >> .env
mkdir -p paperless/consume/private data config
$DC build tools

step "Paperless を起動（初回は日本語の OCR データを入れるので数分かかる）"
$DC up -d broker webserver mock
for i in $(seq 1 120); do
  code=$(curl -s -o /dev/null -w '%{http_code}' $API/ || true)
  case "$code" in 200|302|401) break ;; esac   # ログインしていないと 302 か 401 が返る
  sleep 5
done
case "$code" in 200|302|401) ;; *) fail "Paperless が起動しない（$code）" ;; esac

step "API トークンを作る"
TOKEN=""
for i in $(seq 1 30); do
  TOKEN=$($DC run --rm -T tools python scripts/get_token.py 2>/dev/null | tail -1) && [ -n "$TOKEN" ] && break
  sleep 5
done
[ -n "$TOKEN" ] || fail "トークンが作れない"
sed -i "s/^PAPERLESS_API_TOKEN=.*/PAPERLESS_API_TOKEN=$TOKEN/" .env
H="Authorization: Token $TOKEN"

step "初期設定（2 回動かしても同じになるか）"
$DC run --rm -T tools python scripts/setup_paperless.py
$DC run --rm -T tools python scripts/setup_paperless.py | grep -q "あり：ワークフロー AI に渡す" || fail "2 回目でワークフローが重複した"

step "paperless-gpt を起動"
$DC up -d paperless-gpt

tag_id() { curl -s -H "$H" "$API/tags/?name__iexact=$1" | python3 -c 'import json,sys; print(json.load(sys.stdin)["results"][0]["id"])'; }
AUTO=$(tag_id paperless-gpt-auto); PRIV=$(tag_id private)

step "作り物のプリントを取り込む"
python3 tests/make_sample_pdf.py /tmp/notice.pdf
curl -s -H "$H" -F document=@/tmp/notice.pdf $API/documents/post_document/ > /dev/null
DOC=""
for i in $(seq 1 60); do
  # 新しい環境なので、取り込まれた最初の書類がこれ
  DOC=$(curl -s -H "$H" "$API/documents/?ordering=id&page_size=1" | python3 -c 'import json,sys; r=json.load(sys.stdin)["results"]; print(r[0]["id"] if r else "")')
  [ -n "$DOC" ] && break
  sleep 5
done
[ -n "$DOC" ] || fail "取り込まれない"
echo "書類 #$DOC"

step "AI に渡す目印が付き、AI が名付けて目印が外れるか"
doc() { curl -s -H "$H" "$API/documents/$DOC/"; }
for i in $(seq 1 60); do
  J=$(doc)
  TITLE=$(echo "$J" | python3 -c 'import json,sys; print(json.load(sys.stdin)["title"])')
  HAS_AUTO=$(echo "$J" | python3 -c "import json,sys; print($AUTO in json.load(sys.stdin)['tags'])")
  [ "$TITLE" = "校外学習のお知らせ" ] && [ "$HAS_AUTO" = "False" ] && break
  sleep 5
done
[ "$TITLE" = "校外学習のお知らせ" ] || fail "タイトルが付かない（$TITLE）"
[ "$HAS_AUTO" = "False" ] || fail "paperless-gpt-auto が外れない"
echo "$J" | python3 -m json.tool | head -30

step "ループしないか（30 秒待って、偽の AI が呼ばれ続けていないか）"
before=$($DC logs mock | grep -c '^.*chat:' || true)
sleep 30
after=$($DC logs mock | grep -c '^.*chat:' || true)
[ "$after" = "$before" ] || fail "名付けのあとも AI が呼ばれ続けている（$before → $after）"

step "書類の種類を行事予定にする（AI が付けていなければ手で）"
TYPE=$(curl -s -H "$H" "$API/document_types/?name__iexact=行事予定" | python3 -c 'import json,sys; print(json.load(sys.stdin)["results"][0]["id"])')
CUR=$(doc | python3 -c 'import json,sys; print(json.load(sys.stdin)["document_type"])')
if [ "$CUR" != "$TYPE" ]; then
  echo "（AI は種類を付けなかったので、手で付けます）"
  curl -s -X PATCH -H "$H" -H 'Content-Type: application/json' -d "{\"document_type\": $TYPE}" "$API/documents/$DOC/" > /dev/null
fi

step "予定を取り出す"
$DC run --rm -T tools python scripts/extract_events.py
grep -q '"2026-11-11"' data/events.json || fail "予定が取り出せない"
$DC run --rm -T tools python scripts/extract_events.py | grep -q "校外学習" && fail "変わっていない書類を読み直している" || true

step "明日のお知らせ（11/10 に送る想定）"
OUT=$($DC run --rm -T tools python scripts/notify_tomorrow.py --today 2026-11-10)
echo "$OUT"
echo "$OUT" | grep -q "校外学習" || fail "お知らせに予定が入らない"
echo "$OUT" | grep -q "お弁当" || fail "お知らせに持ち物が入らない"
$DC run --rm -T tools python scripts/notify_tomorrow.py --today 2026-11-12 | grep -q "送りません" || fail "予定の無い日にも送ろうとする"

step "private フォルダーの書類は AI に渡らないか"
python3 tests/make_sample_pdf.py paperless/consume/private/private-notice.pdf "Private copy for the test."
PDOC=""
for i in $(seq 1 60); do
  PDOC=$(curl -s -H "$H" "$API/documents/?tags__id__all=$PRIV" | python3 -c 'import json,sys; r=json.load(sys.stdin)["results"]; print(r[0]["id"] if r else "")')
  [ -n "$PDOC" ] && break
  sleep 5
done
[ -n "$PDOC" ] || fail "private の書類に private が付かない"
sleep 20
curl -s -H "$H" "$API/documents/$PDOC/" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert $AUTO not in d['tags'], 'private の書類に paperless-gpt-auto が付いた'
assert d['title']!='校外学習のお知らせ', 'private の書類を AI が名付けた'
print('OK：private の書類は AI に渡っていない（タイトル：' + d['title'] + '）')
"

step "カレンダーに書き込む（偽の Google カレンダー）"
cat > config/calendars.json <<'JSON'
{"長女": "cal-chojo", "長男": "cal-chonan", "次男": "cal-jinan", "家族": "cal-family"}
JSON
cal() { $DC run --rm -T tools python -c "import json,urllib.request; print(json.dumps(json.load(urllib.request.urlopen('http://mock:8000/_calendar'))))"; }
$DC run --rm -T tools python scripts/sync_calendar.py --today 2026-11-10 --dry-run | grep -q "（試し）書き込む" || fail "試しの書き込みが出ない"
[ "$(cal)" = "{}" ] || fail "試しなのにカレンダーに書き込んだ"
$DC run --rm -T tools python scripts/sync_calendar.py --today 2026-11-10
cal | python3 -c "
import json,sys
c=json.load(sys.stdin); evs=[e for cal in c.values() for e in cal.values()]
assert any(e['summary']=='校外学習' and e['start']=={'date':'2026-11-11'} and e['end']=={'date':'2026-11-12'} for e in evs), c
assert all(e['id'].startswith('home') for e in evs)
print('OK：', {k: [e['summary'] for e in v.values()] for k,v in c.items()})
"
$DC run --rm -T tools python scripts/sync_calendar.py --today 2026-11-10 > /dev/null
[ "$(cal | python3 -c 'import json,sys; print(sum(len(v) for v in json.load(sys.stdin).values()))')" = "1" ] || fail "2 回目で予定が増えた"

step "人が消した予定は、二度と書き込まない"
EID=$(cal | python3 -c 'import json,sys; c=json.load(sys.stdin); print([(k,i) for k,v in c.items() for i in v][0][0] + "/events/" + [(k,i) for k,v in c.items() for i in v][0][1])')
$DC run --rm -T tools python -c "import urllib.request; urllib.request.urlopen(urllib.request.Request('http://mock:8000/calendar/v3/calendars/$EID', method='DELETE'))"
$DC run --rm -T tools python scripts/sync_calendar.py --today 2026-11-10 | grep -q "人が消した予定" || fail "人が消したことに気づかない"
cal | python3 -c "import json,sys; c=json.load(sys.stdin); assert all(e['status']=='cancelled' for v in c.values() for e in v.values()), '消した予定が戻った'"
$DC run --rm -T tools python scripts/notify_tomorrow.py --today 2026-11-10 | grep -q "送りません" || fail "人が消した予定を知らせた"

step "閲覧だけのユーザー（MCP 用）"
READER=$($DC run --rm -T tools python scripts/create_reader.py 2>/dev/null | tail -1)
[ -n "$READER" ] || fail "閲覧用のトークンが作れない"
code=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Token $READER" $API/documents/)
[ "$code" = "200" ] || fail "閲覧用のトークンで書類の一覧が見られない（$code）"
code=$(curl -s -o /dev/null -w '%{http_code}' -X PATCH -H "Authorization: Token $READER" -H 'Content-Type: application/json' -d '{"title":"x"}' $API/documents/$DOC/)
[ "$code" = "403" ] || [ "$code" = "404" ] || fail "閲覧用のトークンで書類を書き換えられた（$code）"
echo "OK：閲覧はできて、書き換えはできない"

step "MCP の道具（private を返さないか）"
$DC run --rm -T tools python tests/mcp_check.py || fail "MCP の道具"

step "すべて OK"
