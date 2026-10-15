# Velvet Watch — Real-Time Synchronized Watch Party

Velvet Watch is a full-stack watch party web app. Friends join a shared room and watch a YouTube video in sync, with live chat, floating emoji reactions, group polls, and a shared queue.

## Key Features

- **Real-time playback sync:** the host's play, pause and seek actions are broadcast to everyone in the room over Socket.IO.
- **Drift auto-correction:** the host sends its playback position every 2 seconds, and viewers automatically re-sync if they drift by more than 0.5 seconds.
- **Rooms with invite links:** create a room, share the 6-character code or a copyable invite link. Rooms hold up to 10 people.
- **Load any YouTube video:** paste a YouTube link (watch, youtu.be, embed or shorts) and everyone's player updates.
- **Movie discovery:** browse a built-in catalogue with Fuse.js fuzzy search and category filters. Play a title instantly or add it to the queue.
- **Live chat:** chat with custom display names. Messages are HTML-escaped to prevent XSS.
- **Floating emoji reactions:** reactions float across everyone's video in real time.
- **Group polls:** create a poll, and each person gets one vote per poll.
- **Shared queue:** add videos to a room playlist and play any item.
- **Host management:** if the host leaves, a new host is chosen automatically. The host can also hand over control manually.

## Tech Stack

- **Backend:** Python, FastAPI, python-socketio (async), Uvicorn
- **Frontend:** HTML5, Tailwind CSS, Socket.IO client, YouTube IFrame API, Fuse.js

## Project Structure

```
watch_party/
├── server.py          # FastAPI + Socket.IO backend
├── requirements.txt
└── public/
    └── index.html     # Frontend (served statically)
```

## How to Run Locally

1. Install dependencies:
```bash
   pip install -r requirements.txt
```
2. Start the server:
```bash
   python server.py
```
3. Open `http://127.0.0.1:8000` in your browser.

## How to Test Sync

1. Open the app in one tab and click **Create Room**.
2. Open a second tab (or an incognito window) and enter the room code, then click **Join**.
3. In the first tab, load a video and press play. The second tab follows along.
4. Try chat, reactions, polls and the queue from either tab.

## Notes

- Only the host controls playback. Anyone in the room can load a new video.
- Some YouTube videos have embedding disabled by their owners and won't play in the embedded player.
- Rooms are stored in memory, so they reset when the server restarts.
