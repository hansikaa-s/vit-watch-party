# Velvet Watch — Real-Time Synchronized Watch Party

Velvet Watch is a full-stack real-time watch party platform featuring synchronized video playback, live chat, interactive floating emoji reactions, custom display names, and dynamic YouTube Data API v3 search.

## 🚀 Key Features
- **Real-Time Playback Synchronization:** Bi-directional event broadcasting via Async Socket.IO.
- **Drift Auto-Correction ($\le 500\text{ms}$):** Host periodic heartbeat continuously monitors participant player states and automatically corrects playback drift.
- **Dynamic YouTube Search:** Integrated live search using YouTube Data API v3.
- **Interactive Lounge Chat & Reactions:** Chat using custom usernames and send floating overlay reactions across connected clients.

## 🛠️ Tech Stack
- **Backend:** Python, FastAPI, Async Socket.IO, Uvicorn
- **Frontend:** HTML5, Tailwind CSS, YouTube IFrame API, YouTube Data API v3

## ⚡ How to Run Locally
1. Install Python dependencies:
   ```bash
   pip install fastapi uvicorn python-socketio