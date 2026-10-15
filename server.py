import socketio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn
import random, string

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = FastAPI()

# In-memory storage for active rooms
rooms = {}

@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")
    for code, room in list(rooms.items()):
        if sid in room["members"]:
            del room["members"][sid]
            # Notify peer disconnect for WebRTC cleanup
            await sio.emit("user_left_webrtc", {"sid": sid}, room=code)
            
            if not room["members"]:
                del rooms[code]
            else:
                if room["host_sid"] == sid:
                    new_host_sid = next(iter(room["members"]))
                    room["host_sid"] = new_host_sid
                    room["members"][new_host_sid]["is_host"] = True
                    await sio.emit("host_changed", {"new_host_sid": new_host_sid}, room=code)
                await update_room_members(code)

@sio.event
async def create_room(sid, data=None):
    room_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    rooms[room_code] = {
        "host_sid": sid,
        "members": {sid: {"username": "Host", "is_host": True}},
        "video_id": "Pw-Tr25wSyk",
        "time": 0,
        "is_playing": False,
        "timed_comments": []
    }
    
    sio.enter_room(sid, room_code)
    await sio.emit("room_created", {"room": room_code}, to=sid)
    await update_room_members(room_code)

@sio.event
async def join_room(sid, data):
    code = data.get("room", "").strip().upper()
    username = data.get("username", "Guest").strip() or "Guest"

    if code not in rooms:
        await sio.emit("room_error", {"message": "Invalid room code!"}, to=sid)
        return

    room = rooms[code]
    is_host = (sid == room["host_sid"])
    
    # Existing member IDs for WebRTC mesh signaling
    existing_peers = list(room["members"].keys())
    
    room["members"][sid] = {"username": username, "is_host": is_host}
    sio.enter_room(sid, code)
    
    await sio.emit("room_joined", {
        "room": code,
        "is_host": is_host,
        "video_id": room["video_id"],
        "current_time": room["time"],
        "is_playing": room["is_playing"],
        "existing_peers": existing_peers,
        "timed_comments": room["timed_comments"]
    }, to=sid)

    # Notify existing peers that a new WebRTC participant joined
    await sio.emit("user_joined_webrtc", {"sid": sid, "username": username}, room=code, skip_sid=sid)
    await update_room_members(code)

# --- WEBRTC PEER-TO-PEER SIGNALING ---
@sio.event
async def webrtc_offer(sid, data):
    await sio.emit("webrtc_offer", {"offer": data["offer"], "sender_sid": sid}, to=data["target_sid"])

@sio.event
async def webrtc_answer(sid, data):
    await sio.emit("webrtc_answer", {"answer": data["answer"], "sender_sid": sid}, to=data["target_sid"])

@sio.event
async def webrtc_ice_candidate(sid, data):
    await sio.emit("webrtc_ice_candidate", {"candidate": data["candidate"], "sender_sid": sid}, to=data["target_sid"])

# --- PLAYBACK & DRIFT SYNC ---
@sio.event
async def sync_action(sid, data):
    room_code = data.get("room")
    action = data.get("action")
    time = data.get("time", 0)

    if room_code in rooms:
        rooms[room_code]["time"] = time
        rooms[room_code]["is_playing"] = (action == "play")
        await sio.emit("sync_action", {"action": action, "time": time}, room=room_code, skip_sid=sid)

@sio.event
async def host_heartbeat(sid, data):
    room_code = data.get("room")
    time = data.get("time", 0)
    is_playing = data.get("is_playing", False)

    if room_code in rooms and rooms[room_code]["host_sid"] == sid:
        rooms[room_code]["time"] = time
        rooms[room_code]["is_playing"] = is_playing
        await sio.emit("drift_check", {"time": time, "is_playing": is_playing}, room=room_code, skip_sid=sid)

@sio.event
async def change_video(sid, data):
    room_code = data.get("room")
    video_id = data.get("video_id")

    if room_code in rooms:
        rooms[room_code]["video_id"] = video_id
        rooms[room_code]["time"] = 0
        rooms[room_code]["is_playing"] = True
        await sio.emit("video_changed", {"video_id": video_id}, room=room_code)

@sio.event
async def send_chat(sid, data):
    room_code = data.get("room")
    message = data.get("message")
    username = data.get("username", "User")

    if room_code in rooms:
        await sio.emit("chat_message", {"username": username, "message": message}, room=room_code)

# --- TIMED DANMAKU COMMENTS ---
@sio.event
async def send_timed_comment(sid, data):
    room_code = data.get("room")
    comment_data = {
        "username": data.get("username", "User"),
        "text": data.get("text"),
        "time": data.get("time", 0)
    }
    if room_code in rooms:
        rooms[room_code]["timed_comments"].append(comment_data)
        await sio.emit("new_timed_comment", comment_data, room=room_code)

@sio.event
async def send_reaction(sid, data):
    room_code = data.get("room")
    emoji = data.get("emoji")

    if room_code in rooms:
        await sio.emit("floating_emoji", {"emoji": emoji}, room=room_code)

async def update_room_members(room_code):
    if room_code in rooms:
        members_list = [
            {"sid": m_sid, "username": m_info["username"], "is_host": m_info["is_host"]}
            for m_sid, m_info in rooms[room_code]["members"].items()
        ]
        await sio.emit("members_updated", {"members": members_list}, room=room_code)

socket_app = socketio.ASGIApp(sio, app)
app.mount("/", StaticFiles(directory="public", html=True), name="public")

if __name__ == "__main__":
    uvicorn.run(socket_app, host="127.0.0.1", port=8000)