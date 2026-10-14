import secrets
import string
import time
from pathlib import Path

import socketio
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).parent

app = FastAPI()

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*"
)

socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

# Track active rooms, hosts, video IDs, and playback states
rooms = {}

app.mount(
    "/",
    StaticFiles(directory=BASE_DIR / "public", html=True),
    name="public"
)


def make_room_code():
    while True:
        code = "".join(
            secrets.choice(string.ascii_uppercase + string.digits)
            for _ in range(6)
        )
        if code not in rooms:
            return code


@sio.event
async def connect(sid, environ, auth=None):
    print("Connected:", sid)


@sio.event
async def create_room(sid):
    code = make_room_code()
    rooms[code] = {
        "members": {sid},
        "host": sid,
        "video_id": "M7lc1UVf-VE",
        "current_time": 0,
        "is_playing": False,
        "last_update": time.time()
    }
    await sio.enter_room(sid, code)
    await sio.emit("room_created", {"room": code, "is_host": True}, to=sid)
    print("Room created:", code)


@sio.event
async def join_room(sid, data):
    code = str(data.get("room", "")).strip().upper()

    if code not in rooms:
        await sio.emit(
            "room_error",
            {"message": "Room not found. Check the code."},
            to=sid
        )
        return

    rooms[code]["members"].add(sid)
    await sio.enter_room(sid, code)
    
    # Send current room state to late joiners instantly
    room_data = rooms[code]
    await sio.emit("room_joined", {
        "room": code, 
        "is_host": (sid == room_data["host"]),
        "video_id": room_data["video_id"],
        "current_time": room_data["current_time"],
        "is_playing": room_data["is_playing"]
    }, to=sid)
    print("Joined room:", code)


@sio.event
async def change_video(sid, data):
    code = str(data.get("room", "")).strip().upper()
    video_id = str(data.get("video_id", "")).strip()

    if code not in rooms or sid not in rooms[code]["members"]:
        print("Video change rejected: user is not in that room.")
        return

    allowed_chars = string.ascii_letters + string.digits + "_-"
    if len(video_id) != 11 or any(c not in allowed_chars for c in video_id):
        print("Video change rejected: invalid video ID.")
        return

    rooms[code]["video_id"] = video_id
    rooms[code]["current_time"] = 0
    rooms[code]["is_playing"] = True
    print("VIDEO CHANGE:", code, video_id)

    await sio.emit(
        "video_changed",
        {"video_id": video_id},
        room=code
    )


# --- REAL-TIME PLAYBACK CONTROLS & DRIFT ENGINE ---

@sio.event
async def sync_action(sid, data):
    """Handles play, pause, and manual seek across room participants."""
    code = str(data.get("room", "")).strip().upper()
    action = data.get("action")  # 'play', 'pause'
    time_pos = data.get("time", 0)

    if code in rooms and sid in rooms[code]["members"]:
        rooms[code]["current_time"] = time_pos
        rooms[code]["is_playing"] = (action == "play")
        rooms[code]["last_update"] = time.time()
        
        # Broadcast play/pause/seek to all room members
        await sio.emit("sync_action", {
            "action": action,
            "time": time_pos,
            "sender": sid
        }, room=code, skip_sid=sid)


@sio.event
async def host_heartbeat(sid, data):
    """Host sends playback status every 2s for drift detection (<500ms)."""
    code = str(data.get("room", "")).strip().upper()
    time_pos = data.get("time", 0)
    is_playing = data.get("is_playing", False)

    if code in rooms and rooms[code]["host"] == sid:
        rooms[code]["current_time"] = time_pos
        rooms[code]["is_playing"] = is_playing
        rooms[code]["last_update"] = time.time()

        # Emit drift check payload to all clients
        await sio.emit("drift_check", {
            "time": time_pos,
            "is_playing": is_playing
        }, room=code, skip_sid=sid)


# --- LIVE CHAT & EMOJI REACTIONS ---

@sio.event
async def send_chat(sid, data):
    code = str(data.get("room", "")).strip().upper()
    msg = data.get("message", "").strip()
    username = data.get("username", "Guest")

    if code in rooms and msg:
        await sio.emit("chat_message", {
            "username": username,
            "message": msg
        }, room=code)


@sio.event
async def send_reaction(sid, data):
    code = str(data.get("room", "")).strip().upper()
    emoji = data.get("emoji", "❤️")

    if code in rooms:
        await sio.emit("floating_emoji", {"emoji": emoji}, room=code)


@sio.event
async def disconnect(sid):
    for code in list(rooms):
        if sid in rooms[code]["members"]:
            rooms[code]["members"].discard(sid)
            
            # Automatic host transfer if host leaves
            if rooms[code]["host"] == sid and rooms[code]["members"]:
                new_host = next(iter(rooms[code]["members"]))
                rooms[code]["host"] = new_host
                await sio.emit("host_transferred", {"new_host": new_host}, room=code)

            # Cleanup empty rooms
            if not rooms[code]["members"]:
                del rooms[code]


if __name__ == "__main__":
    uvicorn.run(socket_app, host="127.0.0.1", port=8000)