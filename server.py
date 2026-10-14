
import socketio
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

BASE_DIR = Path(__file__).parent

app = FastAPI()
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[]
)

socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

app.mount(
    "/",
    StaticFiles(directory=BASE_DIR / "public", html=True),
    name="public"
)

if __name__ == "__main__":
    uvicorn.run(socket_app, host="127.0.0.1", port=8000)
