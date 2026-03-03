# VoiceDesk

Self-hosted chat UI für n8n-Workflows. FastAPI + SQLite, ein Docker-Container.

## Features
- Beliebig viele Channels
- Outgoing Webhook (n8n empfängt Text, Audio, Dateien)
- Incoming Webhook (n8n kann per POST Antworten pushen)
- Chat-History persistent in SQLite
- Audio-Aufnahme direkt im Browser
- Datei-Upload an n8n

## Lokal testen

```bash
docker compose up --build
# → http://localhost:8000
```

## Coolify Deployment

### Option A: Git Repo
1. Repo pushen (oder ZIP hochladen)
2. In Coolify: **New Resource → Dockerfile**
3. Build Context: Root des Repos
4. Port: `8000`
5. Volume hinzufügen: `/data` → persistent storage

### Option B: Docker Image bauen & pushen
```bash
docker build -t voicedesk .
docker tag voicedesk registry.example.com/voicedesk:latest
docker push registry.example.com/voicedesk:latest
```
Dann in Coolify als Docker Image deployen.

### Basic Auth in Coolify
In Coolify unter **Settings → Proxy / Traefik**:
```
traefik.http.middlewares.voicedesk-auth.basicauth.users=user:$$apr1$$...
traefik.http.routers.voicedesk.middlewares=voicedesk-auth
```
Passwort-Hash generieren: `htpasswd -nb user yourpassword`

### Environment Variables
| Variable | Default | Beschreibung |
|---|---|---|
| `DB_PATH` | `/data/voicedesk.db` | Pfad zur SQLite-Datei |

## n8n Integration

### Outgoing (VoiceDesk → n8n)
- In Channel: **Outgoing Webhook** = dein n8n Webhook-URL
- Payload Text: `{ "type": "text", "text": "..." }`
- Payload Audio: `multipart/form-data`, Feld `file` + `type=audio`
- Payload Datei: `multipart/form-data`, Feld `file` + `type=file` + `filename`
- n8n antwortet mit JSON: `{ "text": "Antwort..." }` oder `{ "output": "..." }`

### Incoming (n8n → VoiceDesk)
- URL: `https://deine-domain.com/incoming/{channel_id}`
- n8n POST JSON: `{ "text": "Nachricht von n8n" }`
- Channel-ID steht im Edit-Dialog des Channels
