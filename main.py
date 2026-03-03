import os
import json
import httpx
import sqlite3
from datetime import datetime
from contextlib import contextmanager
from typing import Optional

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ─── Config ──────────────────────────────────────────────────────────────────
DB_PATH = os.environ.get("DB_PATH", "voicedesk.db")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")  # optional simple gate

app = FastAPI(title="VoiceDesk")
templates = Jinja2Templates(directory="templates")

# ─── Database ─────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT NOT NULL,
                description TEXT DEFAULT '',
                webhook_out TEXT DEFAULT '',
                webhook_in  TEXT DEFAULT '',
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                msg_type   TEXT DEFAULT 'text',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE
            )
        """)
        conn.commit()

init_db()

# ─── Helpers ──────────────────────────────────────────────────────────────────
def db_channels():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM channels ORDER BY name").fetchall()
    return [dict(r) for r in rows]

def db_channel(channel_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM channels WHERE id=?", (channel_id,)).fetchone()
    return dict(row) if row else None

def db_messages(channel_id: int):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE channel_id=? ORDER BY created_at",
            (channel_id,)
        ).fetchall()
    return [dict(r) for r in rows]

# ─── Routes: Pages ────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    channels = db_channels()
    first = channels[0] if channels else None
    return templates.TemplateResponse("index.html", {
        "request": request,
        "channels": channels,
        "current": first,
        "messages": db_messages(first["id"]) if first else [],
    })

@app.get("/channel/{channel_id}", response_class=HTMLResponse)
async def channel_view(request: Request, channel_id: int):
    channels = db_channels()
    current = db_channel(channel_id)
    if not current:
        return RedirectResponse("/")
    return templates.TemplateResponse("index.html", {
        "request": request,
        "channels": channels,
        "current": current,
        "messages": db_messages(channel_id),
    })

# ─── Routes: Channel CRUD ─────────────────────────────────────────────────────
@app.post("/channel/create")
async def channel_create(
    name: str = Form(...),
    description: str = Form(""),
    webhook_out: str = Form(""),
    webhook_in: str = Form(""),
):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO channels (name, description, webhook_out, webhook_in) VALUES (?,?,?,?)",
            (name.strip(), description.strip(), webhook_out.strip(), webhook_in.strip())
        )
        conn.commit()
        new_id = cur.lastrowid
    return RedirectResponse(f"/channel/{new_id}", status_code=303)

@app.post("/channel/{channel_id}/update")
async def channel_update(
    channel_id: int,
    name: str = Form(...),
    description: str = Form(""),
    webhook_out: str = Form(""),
    webhook_in: str = Form(""),
):
    with get_db() as conn:
        conn.execute(
            "UPDATE channels SET name=?, description=?, webhook_out=?, webhook_in=? WHERE id=?",
            (name.strip(), description.strip(), webhook_out.strip(), webhook_in.strip(), channel_id)
        )
        conn.commit()
    return RedirectResponse(f"/channel/{channel_id}", status_code=303)

@app.post("/channel/{channel_id}/delete")
async def channel_delete(channel_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM channels WHERE id=?", (channel_id,))
        conn.commit()
    return RedirectResponse("/", status_code=303)

@app.post("/channel/{channel_id}/clear")
async def channel_clear(channel_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM messages WHERE channel_id=?", (channel_id,))
        conn.commit()
    return RedirectResponse(f"/channel/{channel_id}", status_code=303)

# ─── Routes: Messaging ────────────────────────────────────────────────────────
@app.post("/channel/{channel_id}/send")
async def send_message(channel_id: int, request: Request):
    """Send text message → forward to outgoing webhook → store response."""
    channel = db_channel(channel_id)
    if not channel:
        raise HTTPException(404)

    body = await request.json()
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(400, "Empty message")

    # Store user message
    with get_db() as conn:
        conn.execute(
            "INSERT INTO messages (channel_id, role, content, msg_type) VALUES (?,?,?,?)",
            (channel_id, "user", text, "text")
        )
        conn.commit()

    # Forward to n8n webhook
    webhook = channel.get("webhook_out", "").strip()
    if not webhook:
        return JSONResponse({"error": "no_webhook", "message": "Kein ausgehender Webhook konfiguriert."})

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(webhook, json={"type": "text", "text": text})
        resp.raise_for_status()

        ct = resp.headers.get("content-type", "")
        if "application/json" in ct:
            data = resp.json()
            reply = (
                data.get("text") or data.get("output") or data.get("message") or
                data.get("response") or
                (data[0].get("text") or data[0].get("output") if isinstance(data, list) else None) or
                json.dumps(data, ensure_ascii=False, indent=2)
            )
        else:
            reply = resp.text

        with get_db() as conn:
            conn.execute(
                "INSERT INTO messages (channel_id, role, content, msg_type) VALUES (?,?,?,?)",
                (channel_id, "assistant", reply, "text")
            )
            conn.commit()

        return JSONResponse({"ok": True, "reply": reply})

    except httpx.HTTPError as e:
        err = f"Webhook-Fehler: {e}"
        with get_db() as conn:
            conn.execute(
                "INSERT INTO messages (channel_id, role, content, msg_type) VALUES (?,?,?,?)",
                (channel_id, "error", err, "text")
            )
            conn.commit()
        return JSONResponse({"error": "http_error", "message": err})


@app.post("/channel/{channel_id}/send-audio")
async def send_audio(channel_id: int, file: UploadFile = File(...)):
    """Forward audio blob to outgoing webhook, store result."""
    channel = db_channel(channel_id)
    if not channel:
        raise HTTPException(404)

    audio_bytes = await file.read()
    filename = file.filename or "recording.webm"
    label = f"🎙 {filename}"

    with get_db() as conn:
        conn.execute(
            "INSERT INTO messages (channel_id, role, content, msg_type) VALUES (?,?,?,?)",
            (channel_id, "user", label, "audio")
        )
        conn.commit()

    webhook = channel.get("webhook_out", "").strip()
    if not webhook:
        return JSONResponse({"error": "no_webhook", "message": "Kein ausgehender Webhook konfiguriert."})

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                webhook,
                files={"file": (filename, audio_bytes, file.content_type or "audio/webm")},
                data={"type": "audio"},
            )
        resp.raise_for_status()

        ct = resp.headers.get("content-type", "")
        if "application/json" in ct:
            data = resp.json()
            reply = (
                data.get("text") or data.get("output") or data.get("message") or
                data.get("response") or
                (data[0].get("text") or data[0].get("output") if isinstance(data, list) else None) or
                json.dumps(data, ensure_ascii=False, indent=2)
            )
        else:
            reply = resp.text

        with get_db() as conn:
            conn.execute(
                "INSERT INTO messages (channel_id, role, content, msg_type) VALUES (?,?,?,?)",
                (channel_id, "assistant", reply, "text")
            )
            conn.commit()

        return JSONResponse({"ok": True, "reply": reply})

    except httpx.HTTPError as e:
        err = f"Webhook-Fehler: {e}"
        with get_db() as conn:
            conn.execute(
                "INSERT INTO messages (channel_id, role, content, msg_type) VALUES (?,?,?,?)",
                (channel_id, "error", err, "text")
            )
            conn.commit()
        return JSONResponse({"error": "http_error", "message": err})


@app.post("/channel/{channel_id}/upload")
async def upload_file(channel_id: int, file: UploadFile = File(...)):
    """Upload file → forward to outgoing webhook."""
    channel = db_channel(channel_id)
    if not channel:
        raise HTTPException(404)

    file_bytes = await file.read()
    filename = file.filename or "upload"

    webhook = channel.get("webhook_out", "").strip()
    label = f"📎 {filename}"

    with get_db() as conn:
        conn.execute(
            "INSERT INTO messages (channel_id, role, content, msg_type) VALUES (?,?,?,?)",
            (channel_id, "user", label, "file")
        )
        conn.commit()

    if not webhook:
        return JSONResponse({"error": "no_webhook", "message": "Kein ausgehender Webhook konfiguriert."})

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                webhook,
                files={"file": (filename, file_bytes, file.content_type or "application/octet-stream")},
                data={"type": "file", "filename": filename},
            )
        resp.raise_for_status()

        ct = resp.headers.get("content-type", "")
        if "application/json" in ct:
            data = resp.json()
            reply = (
                data.get("text") or data.get("output") or data.get("message") or
                data.get("response") or
                (data[0].get("text") or data[0].get("output") if isinstance(data, list) else None) or
                json.dumps(data, ensure_ascii=False, indent=2)
            )
        else:
            reply = resp.text

        with get_db() as conn:
            conn.execute(
                "INSERT INTO messages (channel_id, role, content, msg_type) VALUES (?,?,?,?)",
                (channel_id, "assistant", reply, "text")
            )
            conn.commit()

        return JSONResponse({"ok": True, "reply": reply})

    except httpx.HTTPError as e:
        err = f"Upload-Fehler: {e}"
        with get_db() as conn:
            conn.execute(
                "INSERT INTO messages (channel_id, role, content, msg_type) VALUES (?,?,?,?)",
                (channel_id, "error", err, "text")
            )
            conn.commit()
        return JSONResponse({"error": "http_error", "message": err})


# ─── Incoming webhook endpoint ────────────────────────────────────────────────
@app.post("/incoming/{channel_id}")
async def incoming_webhook(channel_id: int, request: Request):
    """n8n can POST back to this endpoint to push messages into a channel."""
    channel = db_channel(channel_id)
    if not channel:
        raise HTTPException(404)
    try:
        body = await request.json()
    except Exception:
        body = {}
    content = body.get("text") or body.get("message") or body.get("output") or json.dumps(body)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO messages (channel_id, role, content, msg_type) VALUES (?,?,?,?)",
            (channel_id, "assistant", content, "text")
        )
        conn.commit()
    return JSONResponse({"ok": True})
