import secrets
import string
from pathlib import Path


import socketio
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


BASE = Path(__file__).resolve().parent
PUBLIC = BASE / "public"


app = FastAPI()
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")


rooms = {}
sid_rooms = {}


ALLOWED_EMOJIS = ["❤️", "🔥", "😭", "😮", "💀", "😂", "👏", "🎉"]




def make_code():
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(6))




def snapshot(code):
    r = rooms[code]
    poll = None
    if r["poll"]:
        poll = {"question": r["poll"]["question"], "options": r["poll"]["options"]}
    return {
        "code": code,
        "host": r["host"],
        "video_id": r["video_id"],
        "playlist": r["playlist"],
        "poll": poll,
        "members": [
            {"id": sid, "name": m["name"], "host": sid == r["host"]}
            for sid, m in r["members"].items()
        ],
    }




async def update_snapshot(code):
    if code in rooms:
        await sio.emit("room_snapshot", snapshot(code), room=code)




async def remove_from_room(sid, code):
    """Remove a user from a room, promote a new host if needed."""
    if code not in rooms:
        return
    r = rooms[code]
    r["members"].pop(sid, None)
    await sio.leave_room(sid, code)
    if not r["members"]:
        del rooms[code]
        return
    if r["host"] == sid:
        r["host"] = next(iter(r["members"]))
        await sio.emit("notice", "The host left; a new host was selected.", room=code)
    await update_snapshot(code)




@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")




@sio.event
async def create_room(sid, data=None):
    data = data or {}


    # leave any previous room first
    old = sid_rooms.pop(sid, None)
    if old:
        await remove_from_room(sid, old)


    code = make_code()
    while code in rooms:
        code = make_code()


    await sio.enter_room(sid, code)
    sid_rooms[sid] = code
    rooms[code] = {
        "host": sid,
        "members": {sid: {"name": str(data.get("username") or "Host")[:24]}},
        "video_id": None,
        "time": 0,
        "playing": False,
        "playlist": [],
        "poll": None,
    }
    await sio.emit("room_created", {"code": code}, to=sid)
    await update_snapshot(code)




@sio.event
async def join_room(sid, data=None):
    data = data or {}
    code = str(data.get("code", "")).strip().upper()
    if code not in rooms:
        await sio.emit("room_error", "Room code not found. Check the code and try again.", to=sid)
        return
    if sid in rooms[code]["members"]:
        await sio.emit("room_joined", {"code": code, "host": rooms[code]["host"] == sid}, to=sid)
        await update_snapshot(code)
        return
    if len(rooms[code]["members"]) >= 10:
        await sio.emit("room_error", "This room is full (10 people maximum).", to=sid)
        return


    old = sid_rooms.pop(sid, None)
    if old and old != code:
        await remove_from_room(sid, old)


    await sio.enter_room(sid, code)
    sid_rooms[sid] = code
    rooms[code]["members"][sid] = {"name": str(data.get("username") or "Guest")[:24]}


    await sio.emit("room_joined", {"code": code, "host": rooms[code]["host"] == sid}, to=sid)
    await update_snapshot(code)


    r = rooms[code]
    if r["video_id"]:
        await sio.emit(
            "video_changed",
            {"video_id": r["video_id"], "time": r["time"], "playing": r["playing"]},
            to=sid,
        )




@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")
    code = sid_rooms.pop(sid, None)
    if code:
        await remove_from_room(sid, code)




@sio.event
async def change_video(sid, data=None):
    code = sid_rooms.get(sid)
    if not code or code not in rooms:
        await sio.emit("room_error", "Create or join a room before loading a video.", to=sid)
        return
    video_id = str((data or {}).get("video_id", "")).strip()
    if not video_id or len(video_id) > 20:
        await sio.emit("room_error", "That YouTube video ID looks invalid.", to=sid)
        return
    r = rooms[code]
    r.update(video_id=video_id, time=0, playing=True)
    await sio.emit("video_changed", {"video_id": video_id, "time": 0, "playing": True}, room=code)
    await update_snapshot(code)




@sio.event
async def playback_update(sid, data=None):
    code = sid_rooms.get(sid)
    if not code or code not in rooms or sid != rooms[code]["host"]:
        return
    data = data or {}
    try:
        rooms[code]["time"] = max(0, float(data.get("time", 0)))
    except (TypeError, ValueError):
        return
    rooms[code]["playing"] = bool(data.get("playing", False))
    await sio.emit(
        "playback_update",
        {"time": rooms[code]["time"], "playing": rooms[code]["playing"]},
        room=code,
        skip_sid=sid,
    )




@sio.event
async def chat_message(sid, data=None):
    code = sid_rooms.get(sid)
    if not code or code not in rooms:
        await sio.emit("room_error", "Join a room before chatting.", to=sid)
        return
    message = str((data or {}).get("message", "")).strip()[:500]
    if message:
        name = rooms[code]["members"].get(sid, {}).get("name", "Guest")
        await sio.emit("chat_message", {"name": name, "message": message}, room=code)




@sio.event
async def reaction(sid, data=None):
    code = sid_rooms.get(sid)
    if code in rooms:
        emoji = str((data or {}).get("emoji", "❤️"))
        if emoji not in ALLOWED_EMOJIS:
            emoji = "❤️"
        await sio.emit("reaction", {"emoji": emoji}, room=code)




@sio.event
async def add_to_playlist(sid, data=None):
    code = sid_rooms.get(sid)
    if code not in rooms:
        return
    item = (data or {}).get("item") or {}
    video_id = str(item.get("id", "")).strip()
    if not video_id or len(video_id) > 20:
        return
    rooms[code]["playlist"].append({
        "id": video_id,
        "title": str(item.get("title", "Untitled"))[:80],
        "poster": str(item.get("poster", ""))[:300],
    })
    rooms[code]["playlist"] = rooms[code]["playlist"][-30:]
    await update_snapshot(code)




@sio.event
async def create_poll(sid, data=None):
    code = sid_rooms.get(sid)
    if code not in rooms:
        return
    data = data or {}
    question = str(data.get("question", "")).strip()[:120]
    options = [str(o).strip()[:60] for o in (data.get("options") or []) if str(o).strip()]
    if not question or len(options) < 2:
        return
    rooms[code]["poll"] = {
        "question": question,
        "options": [{"text": o, "votes": 0} for o in options[:6]],
        "voted": set(),
    }
    await update_snapshot(code)




@sio.event
async def vote_poll(sid, data=None):
    code = sid_rooms.get(sid)
    if code not in rooms:
        return
    poll = rooms[code]["poll"]
    if not poll or sid in poll["voted"]:
        return
    try:
        idx = int((data or {}).get("option_index"))
    except (TypeError, ValueError):
        return
    if 0 <= idx < len(poll["options"]):
        poll["options"][idx]["votes"] += 1
        poll["voted"].add(sid)
        await update_snapshot(code)




@sio.event
async def transfer_host(sid, data=None):
    code = sid_rooms.get(sid)
    if code not in rooms or rooms[code]["host"] != sid:
        return
    target = (data or {}).get("target")
    if target in rooms[code]["members"]:
        rooms[code]["host"] = target
        await sio.emit("notice", "Host was transferred.", room=code)
        await update_snapshot(code)




@sio.event
async def request_snapshot(sid):
    code = sid_rooms.get(sid)
    if code in rooms:
        await sio.emit("room_snapshot", snapshot(code), to=sid)




app.mount("/", StaticFiles(directory=PUBLIC, html=True), name="public")
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)


if __name__ == "__main__":
    uvicorn.run(socket_app, host="127.0.0.1", port=8000)
