"""Storage layer: debates + turns.

Two backends behind one interface:
- LocalStorage: JSON files under DATA_DIR (dev/test, zero external deps)
- SupabaseStorage: PostgREST against the `debates` and `turns` tables
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .config import settings

DEBATE_STATUSES = ("scheduled", "running", "completed", "failed")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Storage:
    def create_debate(self, topic: str, status: str = "running") -> str: ...
    def append_turn(self, debate_id: str, speaker: str, text: str, tokens: int, position: int) -> None: ...
    def finish_debate(self, debate_id: str, winner: Optional[str], status: str = "completed") -> None: ...
    def list_debates(self, limit: int = 20) -> List[dict]: ...
    def get_debate(self, debate_id: str) -> Optional[dict]: ...
    def get_turns(self, debate_id: str) -> List[dict]: ...
    def delete_older_than(self, hours: int) -> int: ...
    def touch_debate(self, debate_id: str) -> None: ...


class LocalStorage(Storage):
    """File-based storage: data_dir/debates/<id>.json"""

    def __init__(self, data_dir: str):
        self.root = os.path.join(data_dir, "debates")
        os.makedirs(self.root, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, debate_id: str) -> str:
        return os.path.join(self.root, f"{debate_id}.json")

    def create_debate(self, topic: str, status: str = "running") -> str:
        with self._lock:
            debate_id = str(uuid.uuid4())
            rec = {"id": debate_id, "topic": topic, "status": status, "winner": None, "turns": [], "created_at": utcnow(), "updated_at": utcnow()}
            with open(self._path(debate_id), "w", encoding="utf-8") as f:
                json.dump(rec, f, indent=1)
            return debate_id

    def _load(self, debate_id: str) -> Optional[dict]:
        try:
            with open(self._path(debate_id), encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return None

    def append_turn(self, debate_id: str, speaker: str, text: str, tokens: int, position: int) -> None:
        with self._lock:
            rec = self._load(debate_id)
            if rec is None:
                raise KeyError(debate_id)
            rec["turns"].append({"speaker": speaker, "text": text, "tokens": tokens, "position": position})
            rec["updated_at"] = utcnow()
            with open(self._path(debate_id), "w", encoding="utf-8") as f:
                json.dump(rec, f, indent=1)

    def finish_debate(self, debate_id: str, winner: Optional[str], status: str = "completed") -> None:
        with self._lock:
            rec = self._load(debate_id)
            if rec is None:
                raise KeyError(debate_id)
            rec["winner"] = winner
            rec["status"] = status
            rec["ended_at"] = utcnow()
            rec["updated_at"] = utcnow()
            with open(self._path(debate_id), "w", encoding="utf-8") as f:
                json.dump(rec, f, indent=1)

    def touch_debate(self, debate_id: str) -> None:
        with self._lock:
            rec = self._load(debate_id)
            if rec is None:
                return
            rec["updated_at"] = utcnow()
            with open(self._path(debate_id), "w", encoding="utf-8") as f:
                json.dump(rec, f, indent=1)

    def list_debates(self, limit: int = 20) -> List[dict]:
        with self._lock:
            out = []
            for name in os.listdir(self.root):
                if not name.endswith(".json"):
                    continue
                rec = json.load(open(self._path(name[:-5]), encoding="utf-8"))
                out.append(self._public(rec))
            out.sort(key=lambda r: r["created_at"], reverse=True)
            return out[:limit]

    def get_debate(self, debate_id: str) -> Optional[dict]:
        rec = self._load(debate_id)
        return self._public(rec) if rec else None

    def get_turns(self, debate_id: str) -> List[dict]:
        rec = self._load(debate_id)
        return rec["turns"] if rec else []

    @staticmethod
    def _public(rec: dict) -> dict:
        out = {k: v for k, v in rec.items() if k != "turns"}
        out["turns"] = rec.get("turns", [])
        return out

    def delete_older_than(self, hours: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        deleted = 0
        with self._lock:
            for name in os.listdir(self.root):
                if not name.endswith(".json"):
                    continue
                rec = json.load(open(self._path(name[:-5]), encoding="utf-8"))
                try:
                    created = datetime.fromisoformat(rec["created_at"])
                except (KeyError, ValueError):
                    continue
                if created < cutoff:
                    os.remove(self._path(name[:-5]))
                    deleted += 1
        return deleted


class SupabaseStorage(Storage):
    """PostgREST-backed storage. Table schema lives in supabase/migrations."""

    def __init__(self, url: str, key: str):
        from supabase import create_client

        self._client = create_client(url, key)

    def create_debate(self, topic: str, status: str = "running") -> str:
        row = {"topic": topic, "status": status, "created_at": utcnow()}
        res = self._client.table("debates").insert(row).execute()
        return res.data[0]["id"]

    def append_turn(self, debate_id: str, speaker: str, text: str, tokens: int, position: int) -> None:
        self._client.table("turns").insert(
            {"debate_id": debate_id, "speaker": speaker, "text": text, "tokens": tokens, "position": position}
        ).execute()

    def finish_debate(self, debate_id: str, winner: Optional[str], status: str = "completed") -> None:
        self._client.table("debates").update({"winner": winner, "status": status, "ended_at": utcnow()}).eq("id", debate_id).execute()

    def touch_debate(self, debate_id: str) -> None:
        self._client.table("debates").update({"updated_at": utcnow()}).eq("id", debate_id).execute()

    def list_debates(self, limit: int = 20) -> List[dict]:
        res = self._client.table("debates").select("*").order("created_at", desc=True).limit(limit).execute()
        return [dict(r) for r in res.data]

    def get_debate(self, debate_id: str) -> Optional[dict]:
        res = self._client.table("debates").select("*").eq("id", debate_id).execute()
        return dict(res.data[0]) if res.data else None

    def get_turns(self, debate_id: str) -> List[dict]:
        res = self._client.table("turns").select("*").eq("debate_id", debate_id).order("position").execute()
        return [dict(r) for r in res.data]

    def delete_older_than(self, hours: int) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        res = self._client.table("debates").delete().lt("created_at", cutoff).execute()
        return len(res.data)


def make_storage() -> Storage:
    if settings.storage_mode == "local":
        return LocalStorage(settings.data_dir)
    return SupabaseStorage(settings.supabase_url, settings.supabase_key)