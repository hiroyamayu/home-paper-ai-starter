# home-paper-ai-starter

[日本語](README.md) | English

A minimal, self-hosted setup that collects a family's paper (school flyers, appliance manuals, warranty cards) on a home server and turns it into something an AI can read and answer from.

It is the companion repository for a Japanese book on Zenn, [家の紙を全部 AI に読ませる](https://zenn.dev/hiroyamayu/books/home-ai-nas-for-families) ("Let AI read all the paper in your home").

What it does:

1. Ingests scanned or photographed documents into **Paperless-ngx** and makes them full-text searchable
2. Uses **paperless-gpt** and Gemini to give each document a title, type, correspondent, and tags
3. Extracts events and things-to-bring from school schedules and newsletters
4. Sends a **Pushover** notification the evening before if there is an event tomorrow

It also includes two optional parts: writing events to per-person Google Calendars, and an MCP server that lets Claude search the documents.

## Before you start: this is built for Japanese documents

- The prompts in `prompts/` and the calendar rules in `config/calendar_rules.md` are written in Japanese
- OCR is set to Japanese (`jpn+eng`), the time zone defaults to `Asia/Tokyo`, and paperless-gpt answers in Japanese
- The sample documents in `samples/` are made-up Japanese school flyers
- Code comments and script messages are in Japanese

To use it with another language, translate the prompts and the calendar rules, then change `PAPERLESS_OCR_LANGUAGES`, `PAPERLESS_OCR_LANGUAGE`, `LLM_LANGUAGE`, and `TZ` in `compose.yml` and `.env`. The pipeline itself does not depend on the language. I have only run it with Japanese documents.

## What you need

| Item | Example |
|---|---|
| A server that runs Docker (Docker Compose) | A NAS (UGREEN, Synology, QNAP) or a spare PC |
| A Gemini API key | Create one in Google AI Studio. Use a project **with billing enabled**: on the free tier, what you send may be used to improve the service |
| Pushover | Install the app on the phone that should get notifications (30-day trial, then a one-time purchase) |

## Getting started

```bash
git clone https://github.com/hiroyamayu/home-paper-ai-starter.git
cd home-paper-ai-starter
cp .env.example .env
# Replace the values in <> in .env

# 1. Start Paperless (the first start downloads Japanese OCR data and takes a few minutes)
docker compose up -d broker webserver

# 2. Create an API token and write it to PAPERLESS_API_TOKEN in .env
docker compose run --rm tools python scripts/get_token.py

# 3. Create the tags, document types, and workflows
docker compose run --rm tools python scripts/setup_paperless.py

# 4. Start paperless-gpt
docker compose up -d paperless-gpt
```

Open `http://<server IP>:8000` in a browser and log in as the admin user you set in `.env`.

### Adding documents

Put a PDF in `paperless/consume/` and it is ingested. A few minutes later, the AI adds a title and a type.

- Pointing your scanner's save folder at this directory (as a shared folder on the NAS) makes this automatic
- From a phone, you can upload with a Paperless-compatible app such as Paperless Mobile
- **Put documents the AI must not see in `paperless/consume/private/`.** They are not sent for titling or for event extraction

### Try it with the sample documents

`samples/` holds made-up documents: a grade newsletter, an event schedule, a school lunch menu, an appliance manual, and so on. You can try the whole flow with these before adding your own paper ([samples/README.md](samples/README.md), in Japanese).

### Extracting events and sending tomorrow's reminder

```bash
# Extract events from schedules and newsletters (stored in data/events.json)
docker compose run --rm tools python scripts/extract_events.py

# Notify if there is an event tomorrow (prints to the screen when PUSHOVER_TOKEN is empty)
# The same event found in several flyers is merged into one
docker compose run --rm tools python scripts/notify_tomorrow.py
```

To run this every evening, add it to the server's cron (for example, extract at 19:40 and notify at 20:00).

```cron
40 19 * * * cd /path/to/home-paper-ai-starter && docker compose run --rm tools python scripts/extract_events.py >> data/cron.log 2>&1
0 20 * * * cd /path/to/home-paper-ai-starter && docker compose run --rm tools python scripts/notify_tomorrow.py >> data/cron.log 2>&1
```

## Writing events to Google Calendar

Of the extracted events, only the ones that matter to the family are written to a per-person Google Calendar every evening.

1. Create a Google Cloud project and enable the Google Calendar API
2. Create a service account, download its key (JSON), and save it as `config/service-account.json` (it is ignored by Git)
3. In Google Calendar, create one calendar per person (for example: eldest daughter, elder son, younger son, family). In each calendar's "Settings and sharing" → "Share with specific people", add the service account's email address with "Make changes to events". Do not choose "Make changes and manage sharing", which also hands over sharing rights
4. Copy `config/calendars.example.json` to `config/calendars.json` and fill in the calendar IDs (under "Settings and sharing" → "Integrate calendar")
5. Rewrite the include/exclude rules in `config/calendar_rules.md` for your own family

```bash
# Show what would happen without writing anything
docker compose run --rm tools python scripts/sync_calendar.py --dry-run

# Write
docker compose run --rm tools python scripts/sync_calendar.py
```

- The script decides the event IDs (they start with `home`). Running it again does not create duplicates, and **it never touches events a person added by hand**
- If a person deletes an automatically added event, the next run notices and **never writes it again**. It is also left out of tomorrow's reminder
- Events the rules exclude are left out of the reminder as well
- The first run takes a little longer because the `tools` container is built
- Checked on a real server: 10 events from the sample documents were written to 2 calendars, a second run added nothing, and 1 event deleted by hand was not written back

To run it every evening, add it to cron between the extraction and the reminder.

```cron
50 19 * * * cd /path/to/home-paper-ai-starter && docker compose run --rm tools python scripts/sync_calendar.py >> data/cron.log 2>&1
```

## Searching the documents from an AI (MCP)

This lets Claude Desktop search the documents and events over MCP. The tools are read-only, and documents tagged `private` are always removed on the tool side, not by asking the AI to skip them.

| Tool | What it does |
|---|---|
| `search_documents` | Full-text search over the documents |
| `get_document_text` | Returns the text of one document |
| `search_events` | Searches the extracted events by date or keyword |

First, create a user that can only view documents, and write the token it prints to `PAPERLESS_READER_TOKEN` in `.env`. This avoids reusing the admin token.

```bash
docker compose run --rm tools python scripts/create_reader.py
```

If the `private` tag is not visible to that user, the MCP server stops instead of returning documents unfiltered. `create_reader.py` makes the tags visible; run it again after adding tags or correspondents.

Paperless sets the uploader as the owner of documents uploaded through the web UI or the API. Documents with an owner are not visible to the read-only user. Documents placed in the `consume/` folder have no owner, so they are visible.

### Option 1: run the server's container over SSH

If your PC can SSH into the server with a key, you do not need Python on the PC. Add this to Claude Desktop's config file (`claude_desktop_config.json`).

```json
{
  "mcpServers": {
    "home-docs": {
      "command": "ssh",
      "args": ["<SSH host name of the server>", "cd ~/home-paper-ai-starter && docker compose run --rm -T tools python scripts/mcp_server.py"]
    }
  }
}
```

### Option 2: run it with Python on the PC

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
        "PAPERLESS_URL": "http://<server IP>:8000",
        "PAPERLESS_READER_TOKEN": "<read-only token>",
        "DATA_DIR": "<path to the data folder, used for event search>"
      }
    }
  }
}
```

Restart Claude Desktop, and you can ask things like "What do the kids need to bring next week?" In a conversation that searches your documents, do not enable other connectors that can write: an instruction hidden in a document's text could be used to misuse them.

## Trying it on Gemini's free tier

The free tier has limits such as 15 requests per minute. paperless-gpt calls Gemini 5 times per document (title, tags, correspondent, type, date), so adding several documents at once hits the limit quickly. Set `LLM_REQUESTS_PER_MINUTE=10` in `.env`.

**On the free tier, what you send may be used to improve the service.** Only use the made-up documents in `samples/` there, and enable billing before adding your own paper. Check Google's current terms before relying on this.

## Adapting it to your household

- Rewrite the household section (世帯の前提) in `prompts/*.tmpl` with your own family and schools. **The names you write there are sent to the AI service.**
- People tags are set in `PEOPLE` in `scripts/setup_paperless.py`. Keep them in line with the household section.
- To add a document type, add it to both `DOCUMENT_TYPES` in `setup_paperless.py` and `prompts/document_type_prompt.tmpl`.

## What is sent where

| Step | Sent to | Documents in `private/` |
|---|---|---|
| Text recognition (OCR) | Stays at home (Paperless's built-in OCR) | Stays at home |
| Titling and classification | Gemini (recognized text only) | Not sent |
| Event extraction | Gemini (the whole PDF) | Not sent |
| Deciding what goes on the calendar | Gemini (event name, date, whose document it is, the calendar rules) | Not sent |
| Calendar | Google Calendar (event name, things to bring, title of the source document) | Not added |
| Reminder | Pushover (event name and things to bring) | — |
| Searching from an AI | Claude or similar (titles and text of the documents found) | Not returned |

## Tests

Instead of the real Gemini and Google Calendar, the tests start a small mock that returns fixed answers, and check the whole flow: ingest → titling → event extraction → reminder. GitHub Actions runs them on every change.

```bash
bash tests/smoke.sh
```

No real API keys are used (`tests/ci.env` holds made-up values only). The tests copy the repository to a temporary folder and run under a separate project name and port (18765), then clean up. They do not touch your `.env`, your ingested documents, or your settings, so you can run them next to a live Paperless.

## Versions tested

| Component | Version |
|---|---|
| Paperless-ngx | 3.4.1 |
| paperless-gpt | 0.31.0 |

## License

MIT
