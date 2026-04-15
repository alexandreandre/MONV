"""Entités domaine — lignes PostgREST / Supabase (plus d’ORM SQLAlchemy)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def gen_uuid() -> str:
    return str(uuid.uuid4())


def parse_timestamp(value: Any) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value
    s = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


@dataclass
class User:
    id: str
    email: str
    name: str
    hashed_password: str
    credits: int
    created_at: datetime

    @classmethod
    def from_row(cls, row: dict) -> User:
        return cls(
            id=row["id"],
            email=row["email"],
            name=row["name"],
            hashed_password=row["hashed_password"],
            credits=int(row.get("credits", 0)),
            created_at=parse_timestamp(row.get("created_at")),
        )

    def to_insert_row(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "hashed_password": self.hashed_password,
            "credits": self.credits,
            "created_at": _iso(self.created_at),
        }


@dataclass
class Conversation:
    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: dict) -> Conversation:
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            title=row.get("title") or "Nouvelle recherche",
            created_at=parse_timestamp(row.get("created_at")),
            updated_at=parse_timestamp(row.get("updated_at")),
        )

    def to_insert_row(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }


@dataclass
class Message:
    id: str
    conversation_id: str
    role: str
    content: str
    message_type: str
    metadata_json: str | None
    created_at: datetime

    @classmethod
    def from_row(cls, row: dict) -> Message:
        return cls(
            id=row["id"],
            conversation_id=row["conversation_id"],
            role=row["role"],
            content=row["content"],
            message_type=row.get("message_type") or "text",
            metadata_json=row.get("metadata_json"),
            created_at=parse_timestamp(row.get("created_at")),
        )

    def to_insert_row(self) -> dict:
        d: dict = {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "message_type": self.message_type,
            "created_at": _iso(self.created_at),
        }
        if self.metadata_json is not None:
            d["metadata_json"] = self.metadata_json
        return d


@dataclass
class SearchHistory:
    id: str
    user_id: str
    conversation_id: str | None
    query_text: str
    intent: str
    entities_json: str | None
    results_count: int
    credits_used: int
    results_json: str | None
    exported: bool
    export_path: str | None
    created_at: datetime

    @classmethod
    def from_row(cls, row: dict) -> SearchHistory:
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            conversation_id=row.get("conversation_id"),
            query_text=row["query_text"],
            intent=row["intent"],
            entities_json=row.get("entities_json"),
            results_count=int(row.get("results_count", 0)),
            credits_used=int(row.get("credits_used", 0)),
            results_json=row.get("results_json"),
            exported=bool(row.get("exported", False)),
            export_path=row.get("export_path"),
            created_at=parse_timestamp(row.get("created_at")),
        )

    def to_insert_row(self) -> dict:
        d: dict = {
            "id": self.id,
            "user_id": self.user_id,
            "query_text": self.query_text,
            "intent": self.intent,
            "results_count": self.results_count,
            "credits_used": self.credits_used,
            "exported": self.exported,
            "created_at": _iso(self.created_at),
        }
        if self.conversation_id is not None:
            d["conversation_id"] = self.conversation_id
        if self.entities_json is not None:
            d["entities_json"] = self.entities_json
        if self.results_json is not None:
            d["results_json"] = self.results_json
        if self.export_path is not None:
            d["export_path"] = self.export_path
        return d
