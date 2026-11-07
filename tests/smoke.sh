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
mkdir -p paperless/consume/private data

step "Paperless を起動（初回は日本語の OCR データを入れるので数分かかる）"
$DC up -d broker webserver mock
for i in $(seq 1 120); do
  code=$(curl -s -o /dev/null -w '%{http_code}' $API/ || true)
  [ "$code" = "401" ] || [ "$code" = "200" ] && break
  sleep 5
done
[ "$code" = "401" ] || [ "$code" = "200" ] || fail "Paperless が起動しない（$code）"

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
TASK=$(curl -s -H "$H" -F document=@/tmp/notice.pdf $API/documents/post_document/ | tr -d '"')
DOC=""
for i in $(seq 1 60); do
  DOC=$(curl -s -H "$H" "$API/tasks/?task_id=$TASK" | python3 -c 'import json,sys; t=json.load(sys.stdin); t=t[0] if t else {}; print(t.get("related_document") or "")')
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

step "すべて OK"
