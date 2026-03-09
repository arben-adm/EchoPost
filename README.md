# EchoPost

Self-hosted chat UI with webhook integration. FastAPI + SQLite, single Docker container.

Send text, audio recordings, or files through a clean chat interface and receive processed responses back via webhooks.

## Features

- **Unlimited channels** — organize conversations by workflow or topic
- **Outgoing webhooks** — forward text, audio, and files to any webhook endpoint
- **Incoming webhooks** — external services can push messages back into any channel
- **Persistent chat history** — all messages stored in SQLite
- **Browser audio recording** — record and send voice messages directly
- **File upload** — send documents and files for processing
- **Dark theme UI** — minimal, modern interface
- **Mobile responsive** — works on desktop and mobile devices
- **Single-file backend** — one Python file, one HTML template

## Quick Start

```bash
docker compose up --build
# → http://localhost:3010
```

1. Click **+** to create a channel
2. Set the **Outgoing Webhook** URL
3. Start chatting — messages are forwarded and responses appear in the chat

## Deployment

### Option A: Git Repo (Coolify / similar)

1. Push this repo to your Git host
2. In Coolify: **New Resource → Dockerfile**
3. Build context: repository root
4. Port: `3010`
5. Add a volume mount: `/data` → persistent storage

### Option B: Docker Image

```bash
docker build -t echopost .
docker tag echopost registry.example.com/echopost:latest
docker push registry.example.com/echopost:latest
```

Then deploy as a Docker image in your platform of choice.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DB_PATH` | `/data/echopost.db` | Path to the SQLite database file |
| `APP_PASSWORD` | _(empty)_ | Optional login password |
| `APP_SECRET` | _(auto-generated)_ | Secret for session signing |
| `WEBHOOK_SECRET` | _(empty)_ | Shared secret for webhook authentication (recommended: 128-char hex) |

## Webhook Integration

### Outgoing (EchoPost → external)

Set the **Outgoing Webhook** URL in the channel settings.

**Text messages:**
```json
{ "type": "text", "text": "user message" }
```

**Audio recordings:**
```
multipart/form-data
  file: <binary audio>
  type: "audio"
```

**File uploads:**
```
multipart/form-data
  file: <binary file>
  type: "file"
  filename: "document.pdf"
```

**Expected response** (any of these fields work):
```json
{ "text": "response" }
{ "output": "response" }
{ "message": "response" }
{ "response": "response" }
```

Plain text responses are also accepted.

### Webhook Authentication

When `WEBHOOK_SECRET` is set, all outgoing webhook requests include the header `X-Webhook-Secret` with the secret value. Incoming webhook requests must also include the same header — requests with a missing or incorrect secret receive a `403` response.

Generate a secret: `python -c "import secrets; print(secrets.token_hex(64))"`

### Incoming (external → EchoPost)

Push messages into any channel by POSTing to:

```
POST https://your-domain.com/incoming/{channel_id}
Content-Type: application/json
X-Webhook-Secret: your-secret-here  # required if WEBHOOK_SECRET is set

{ "text": "Hello from external service" }
```

The channel ID is shown in the channel edit dialog.

## Tech Stack

- **Backend:** FastAPI, Uvicorn, SQLite, httpx
- **Frontend:** Vanilla JS, Jinja2 templates, Inter font
- **Container:** Python 3.12-slim, single Dockerfile

## License

This project is released under the [MIT License](LICENSE).
