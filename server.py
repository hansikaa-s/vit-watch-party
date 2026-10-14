import secrets
import string
from pathlib import Path

import socketio
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).parent

app = FastAPI()

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[]
)

socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

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
    rooms[code] = {sid}
    await sio.enter_room(sid, code)
    await sio.emit("room_created", {"room": code}, to=sid)


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

    rooms[code].add(sid)
    await sio.enter_room(sid, code)
    await sio.emit("room_joined", {"room": code}, to=sid)


@sio.event
async def disconnect(sid):
    for code in list(rooms):
        rooms[code].discard(sid)
        if not rooms[code]:
            del rooms[code]


if __name__ == "__main__":
    uvicorn.run(socket_app, host="127.0.0.1", port=8000)