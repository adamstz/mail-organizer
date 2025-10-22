from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List

from . import storage

app = FastAPI(title="organize-mail backend")

# Allow CORS from common dev server origins used by Vite.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/messages")
async def get_messages(limit: int = 50, offset: int = 0) -> List[dict]:
    """Return messages from storage as JSON-serializable dicts.

    Query params:
        - limit: max messages to return (default 50)
        - offset: skip this many results (default 0)
    """
    msgs = storage.list_messages_dicts(limit=limit, offset=offset)
    return msgs

