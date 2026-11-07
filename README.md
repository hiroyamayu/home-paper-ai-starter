# home-paper-ai-starter

家の紙（学校のプリント、説明書、保証書…）を NAS に集めて、AI が読める形に整理する仕組みの、いちばん小さな形です。Zenn の本「家の紙を全部 AI に読ませる」の 1 章「週末で動かす最短ルート」で使います。

できること：

1. スキャンした書類やスマホで撮った書類を **Paperless-ngx** に取り込み、全文検索できるようにする
2. **paperless-gpt** と Gemini で、書類にタイトル・種類・発信元・タグを付ける
3. 「行事予定」の書類から、予定を取り出してためる
4. 明日の予定があれば、前の晩に **Pushover** でスマホに知らせる

カレンダーへの書き込み、子どもごとの振り分け、Claude や Gemini からの検索（MCP）は、本の 3〜6 章で足していきます。

## 用意するもの

| もの | 例 |
|---|---|
| Docker（Docker Compose）が動くサーバー | NAS（UGREEN・Synology・QNAP）、余った PC |
| Gemini の API キー | Google AI Studio で作る。**課金を有効にした契約**で使う（無料枠は送った内容がサービスの改善に使われる。本の 7 章） |
| Pushover | 通知を受けたいスマホにアプリを入れる（30 日の試用のあと、買い切り） |

## 始め方

```bash
git clone https://github.com/hiroyamayu/home-paper-ai-starter.git
cd home-paper-ai-starter
cp .env.example .env
# .env の＜＞の中を書き換える

# 1. Paperless を起動する（初回は日本語の OCR データを入れるので数分かかる）
docker compose up -d broker webserver

# 2. API トークンを作り、出た値を .env の PAPERLESS_API_TOKEN に書く
docker compose run --rm tools python scripts/get_token.py

# 3. タグ・書類の種類・ワークフローを作る
docker compose run --rm tools python scripts/setup_paperless.py

# 4. paperless-gpt を起動する
docker compose up -d paperless-gpt
```

ブラウザで `http://<サーバーの IP>:8000` を開き、`.env` に書いた管理者でログインします。

### 書類を入れる

`paperless/consume/` に PDF を置くと取り込まれます。数分すると、AI がタイトルや種類を付けます。

- スキャナーの保存先を、このフォルダー（NAS の共有フォルダー）にしておくと楽です
- スマホからは、Paperless 対応のアプリ（Paperless Mobile など）でアップロードできます
- **AI に名付けさせたくない書類は `paperless/consume/private/` に入れます。**名付けにも、予定の取り出しにも使いません

### 作り物のプリントで試す

`samples/` に、作り物のプリント（学年だより・行事予定表・給食献立表・家電の説明書など）を入れてあります。自分の家の書類を入れる前に、これで試せます（[samples/README.md](samples/README.md)）。

### 予定を取り出す・明日の予定を知らせる

```bash
# 「行事予定」の書類から予定を取り出す（data/events.json にたまる）
docker compose run --rm tools python scripts/extract_events.py

# 明日の予定があれば知らせる（PUSHOVER_TOKEN が空なら、画面に出すだけ）
docker compose run --rm tools python scripts/notify_tomorrow.py
```

毎晩動かすなら、サーバーの cron に登録します（例：19:40 に取り出し、20:00 に知らせる）。

```cron
40 19 * * * cd /path/to/home-paper-ai-starter && docker compose run --rm tools python scripts/extract_events.py >> data/cron.log 2>&1
0 20 * * * cd /path/to/home-paper-ai-starter && docker compose run --rm tools python scripts/notify_tomorrow.py >> data/cron.log 2>&1
```

## 自分の家に合わせる

- `prompts/*.tmpl` の「世帯の前提」を、自分の家の家族・学校に書き換えます。**ここに書いた名前は AI のサービスに送られます。**
- 人のタグは `scripts/setup_paperless.py` の `PEOPLE` で決めます。「世帯の前提」とそろえてください。
- 書類の種類を増やすときは、`setup_paperless.py` の `DOCUMENT_TYPES` と `prompts/document_type_prompt.tmpl` の両方に足します。

## どこに何が送られるか

| 段階 | 送り先 | `private/` の書類 |
|---|---|---|
| 文字の読み取り（OCR） | 家の中（Paperless 標準の OCR） | 家の中 |
| 名付け・分類 | Gemini（読み取った文字だけ） | 送らない |
| 予定の取り出し | Gemini（PDF ごと） | 送らない |
| お知らせ | Pushover（予定の名前と持ち物） | — |

## テスト

偽の AI を立てて、取り込み → 名付け → 予定の取り出し → お知らせまでを通しで確かめます。GitHub Actions で、変更のたびに自動で動きます。

```bash
bash tests/smoke.sh
```

本物の API キーは使いません（`tests/ci.env` は作り物の値だけです）。

## 動作を確かめた版

| もの | 版 |
|---|---|
| Paperless-ngx | 3.4.1 |
| paperless-gpt | 0.31.0 |

## ライセンス

MIT
