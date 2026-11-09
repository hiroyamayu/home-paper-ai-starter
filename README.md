# home-paper-ai-starter

家の紙（学校のプリント、説明書、保証書…）を NAS に集めて、AI が読める形に整理する仕組みの、いちばん小さな形です。Zenn の本「家の紙を全部 AI に読ませる」の 1 章「週末で動かす最短ルート」で使います。

できること：

1. スキャンした書類やスマホで撮った書類を **Paperless-ngx** に取り込み、全文検索できるようにする
2. **paperless-gpt** と Gemini で、書類にタイトル・種類・発信元・タグを付ける
3. 「行事予定」と「お便り」の書類から、予定と持ち物を取り出してためる
4. 明日の予定があれば、前の晩に **Pushover** でスマホに知らせる

あわせて、本の 3 章の「Google カレンダーへの書き込み」と、6 章の「Claude から家の書類を引く（MCP）」も入っています（下の節）。

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
# 「行事予定」「お便り」の書類から予定を取り出す（data/events.json にたまる）
docker compose run --rm tools python scripts/extract_events.py

# 明日の予定があれば知らせる（PUSHOVER_TOKEN が空なら、画面に出すだけ）
# 同じ行事が複数のプリントに書いてあれば 1 つにまとめる
docker compose run --rm tools python scripts/notify_tomorrow.py
```

毎晩動かすなら、サーバーの cron に登録します（例：19:40 に取り出し、20:00 に知らせる）。

```cron
40 19 * * * cd /path/to/home-paper-ai-starter && docker compose run --rm tools python scripts/extract_events.py >> data/cron.log 2>&1
0 20 * * * cd /path/to/home-paper-ai-starter && docker compose run --rm tools python scripts/notify_tomorrow.py >> data/cron.log 2>&1
```

## 予定を Google カレンダーに入れる（本の 3 章）

取り出した予定のうち、家に関係するものだけを、人ごとの Google カレンダーに毎晩書き込みます。

1. Google Cloud でプロジェクトを作り、「Google Calendar API」を有効にする
2. サービスアカウントを作り、鍵（JSON）をダウンロードして `config/service-account.json` に置く（Git には入りません）
3. Google カレンダーで、人ごとのカレンダー（長女・長男・次男・家族など）を作る。それぞれの「設定と共有」→「特定のユーザーとの共有」に、サービスアカウントのメールアドレスを「すべての予定の詳細の変更や表示ができます」で追加する（その下の「予定の変更および共有の管理」は、共有の権限まで渡すので選ばない）
4. `config/calendars.example.json` を `config/calendars.json` に写し、カレンダー ID を書く（「設定と共有」→「カレンダーの統合」にあります）
5. `config/calendar_rules.md` の「入れる・外す」の決まりを、自分の家に合わせて書き換える

```bash
# 書き込まずに、何をするかだけ見る
docker compose run --rm tools python scripts/sync_calendar.py --dry-run

# 書き込む
docker compose run --rm tools python scripts/sync_calendar.py
```

- 予定の ID はスクリプトが決めます（`home` で始まる）。何度動かしても予定は増えず、**人が手で入れた予定には触りません**
- 自動で入れた予定を人が消すと、次に動かしたときに気づいて、**二度と書き込みません**。明日のお知らせにも出しません
- 決まりで「外す」とした予定も、お知らせに出しません
- 初めて動かすとき、スクリプト用のコンテナ（`tools`）が作られるので少し時間がかかります
- 実機で確かめた結果：作り物のプリントから 10 件を 2 つのカレンダーに書き込み、2 回目は増えず、手で消した 1 件は書き戻されなかった

毎晩動かすなら、cron の予定の取り出しとお知らせの間に足します。

```cron
50 19 * * * cd /path/to/home-paper-ai-starter && docker compose run --rm tools python scripts/sync_calendar.py >> data/cron.log 2>&1
```

## AI から家の書類を引く（本の 6 章）

Claude Desktop から、家の書類と予定を引けるようにします（MCP）。道具は読み取り専用で、`private` の書類は道具の側で必ず除きます。

| 道具 | すること |
|---|---|
| `search_documents` | 書類を本文の言葉で探す |
| `get_document_text` | 書類 1 件の本文を読む |
| `search_events` | 取り出した行事予定を、日付や言葉で探す |

まず、書類を見ることだけができるユーザーを作り、出たトークンを `.env` の `PAPERLESS_READER_TOKEN` に書きます。管理者のトークンを使い回さないためです。

```bash
docker compose run --rm tools python scripts/create_reader.py
```

Paperless は、画面や API でアップロードした書類の持ち主を、アップロードした人にします。持ち主のいる書類は、閲覧用のユーザーからは見えません。`consume/` フォルダーに置いた書類は持ち主がいないので見えます。

### つなぎ方 1：PC から SSH でサーバーのコンテナを動かす

PC からサーバーに鍵で SSH できるなら、PC に Python を入れる必要はありません。Claude Desktop の設定ファイル（`claude_desktop_config.json`）に足します。

```json
{
  "mcpServers": {
    "home-docs": {
      "command": "ssh",
      "args": ["<サーバーの SSH の名前>", "cd ~/home-paper-ai-starter && docker compose run --rm -T tools python scripts/mcp_server.py"]
    }
  }
}
```

### つなぎ方 2：PC の Python で動かす

```bash
pip install -r tools/requirements.txt
```

```json
{
  "mcpServers": {
    "home-docs": {
      "command": "python",
      "args": ["C:\\path\\to\\home-paper-ai-starter\\scripts\\mcp_server.py"],
      "env": {
        "PAPERLESS_URL": "http://<サーバーの IP>:8000",
        "PAPERLESS_READER_TOKEN": "<閲覧用のトークン>",
        "DATA_DIR": "<data フォルダーの場所。予定を引くときに使う>"
      }
    }
  }
}
```

Claude Desktop を再起動すると、チャットから「来週の持ち物は？」のように聞けます。家の書類を引く会話では、書き込みのできるほかのコネクタを一緒に使わないでください（書類の本文に紛れた指示で悪用される余地があるため。本の 6 章）。

## Gemini の無料枠で試すとき

無料枠には「1 分間に 15 回まで」のような上限があります。paperless-gpt は 1 つの書類で 5 回（タイトル・タグ・発信元・種類・日付）Gemini を呼ぶので、何枚もまとめて入れるとすぐに上限に当たります。`.env` の `LLM_REQUESTS_PER_MINUTE=10` にしてください。

**無料枠は、送った内容がサービスの改善に使われます。**試すのは `samples/` の作り物のプリントだけにして、家の書類を入れるのは課金を有効にしてからにしてください。

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
| カレンダーに入れるかの判定 | Gemini（予定の名前・日付・どの子の書類か、カレンダーの決まり） | 送らない |
| カレンダー | Google カレンダー（予定の名前・持ち物・原本のタイトル） | 入れない |
| お知らせ | Pushover（予定の名前と持ち物） | — |
| AI から書類を引く | Claude など（探した書類のタイトルと本文） | 返さない |

## テスト

偽の AI を立てて、取り込み → 名付け → 予定の取り出し → お知らせまでを通しで確かめます。GitHub Actions で、変更のたびに自動で動きます。

```bash
bash tests/smoke.sh
```

本物の API キーは使いません（`tests/ci.env` は作り物の値だけです）。テストは、ひな形を一時フォルダーに写して、別のプロジェクト名と別のポート（18765）で動かし、終わったら消します。いまの `.env`・取り込んだ書類・設定には触れないので、動かしている Paperless と並べて走らせても大丈夫です。

## 動作を確かめた版

| もの | 版 |
|---|---|
| Paperless-ngx | 3.4.1 |
| paperless-gpt | 0.31.0 |

## ライセンス

MIT
