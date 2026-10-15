
import socketio
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

BASE_DIR = Path(__file__).parent

app = FastAPI(title="VIT Watch Party")
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[]
)

# Wrap FastAPI with Socket.IO
socket_app = socketio.ASGIApp(
    sio,
    other_asgi_app=app
)

# Serve our website from the public folder
app.mount(
    "/",
    StaticFiles(directory=BASE_DIR / "public", html=True),
    name="public"
)

# Temporary in-memory room storage
rooms = {}


@sio.event
async def connect(sid, environ, auth=None):
    print(f"Connected: {sid}")


@sio.event
async def disconnect(sid, reason=None):
    print(f"Disconnected: {sid}")


if __name__ == "__main__":
    uvicorn.run(
        "server:socket_app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
