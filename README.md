# VoiceDesk

Self-hosted chat UI for n8n workflows. FastAPI + SQLite, single Docker container.

VoiceDesk acts as a bridge between users and [n8n](https://n8n.io) automation workflows — send text, audio recordings, or files through a clean chat interface, and receive processed responses back in real time.

## Features

- **Unlimited channels** — organize conversations by workflow or topic
- **Outgoing webhooks** — forward text, audio, and files to any n8n webhook endpoint
- **Incoming webhooks** — n8n can push messages back into any channel via POST
- **Persistent chat history** — all messages stored in SQLite
- **Browser audio recording** — record and send voice messages directly
- **File upload** — send documents and files to n8n for processing
- **Dark theme UI** — modern interface inspired by Rocket.Chat
- **Mobile responsive** — works on desktop and mobile devices
- **Single-file backend** — one Python file, one HTML template, zero complexity

## Quick Start

```bash
docker compose up --build
# → http://localhost:3010
```

1. Click **+ Channel** to create a channel
2. Set the **Outgoing Webhook** to your n8n webhook URL
3. Start chatting — messages are forwarded to n8n and responses appear in the chat

## Deployment

### Option A: Git Repo (Coolify / similar)

1. Push this repo to your Git host
2. In Coolify: **New Resource → Dockerfile**
3. Build context: repository root
4. Port: `3010`
5. Add a volume mount: `/data` → persistent storage

### Option B: Docker Image

```bash
docker build -t voicedesk .
docker tag voicedesk registry.example.com/voicedesk:latest
docker push registry.example.com/voicedesk:latest
```

Then deploy as a Docker image in your platform of choice.

### Basic Auth (Traefik / Coolify)

Under **Settings → Proxy / Traefik**, add:

```
traefik.http.middlewares.voicedesk-auth.basicauth.users=user:$$apr1$$...
traefik.http.routers.voicedesk.middlewares=voicedesk-auth
```

Generate a password hash: `htpasswd -nb user yourpassword`

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DB_PATH` | `/data/voicedesk.db` | Path to the SQLite database file |

## n8n Integration

### Outgoing (VoiceDesk → n8n)

Set the **Outgoing Webhook** URL in the channel settings to your n8n webhook endpoint.

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

**Expected response from n8n** (any of these fields work):
```json
{ "text": "response" }
{ "output": "response" }
{ "message": "response" }
{ "response": "response" }
```

Plain text responses are also accepted.

### Incoming (n8n → VoiceDesk)

n8n can push messages into any channel by POSTing to:

```
POST https://your-domain.com/incoming/{channel_id}
Content-Type: application/json

{ "text": "Message from n8n" }
```

The channel ID is shown in the channel edit dialog.

## Tech Stack

- **Backend:** FastAPI, Uvicorn, SQLite, httpx
- **Frontend:** Vanilla JS, Jinja2 templates, Inter font
- **Container:** Python 3.12-slim, single Dockerfile

## License

This project is released under the [MIT License](LICENSE) — free to use, modify, and distribute.
