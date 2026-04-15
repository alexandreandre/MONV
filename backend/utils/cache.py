import json
import hashlib
from datetime import datetime, timezone, timedelta
from supabase import Client

from models.db import cache_delete, cache_get_row, cache_insert, cache_update
from models.entities import parse_timestamp
from config import settings


def make_cache_key(prefix: str, params: dict) -> str:
    raw = json.dumps(params, sort_keys=True)
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"{prefix}:{h}"


async def cache_get(client: Client, key: str) -> dict | None:
    row = await cache_get_row(client, key)
    if row is None:
        return None
    expires_at = parse_timestamp(row.get("expires_at"))
    if expires_at < datetime.now(timezone.utc):
        await cache_delete(client, key)
        return None
    return json.loads(row["value_json"])


async def cache_set(client: Client, key: str, value: dict, ttl_hours: int | None = None) -> None:
    ttl = ttl_hours or settings.CACHE_TTL_HOURS
    expires = datetime.now(timezone.utc) + timedelta(hours=ttl)
    expires_iso = expires.isoformat()
    payload_json = json.dumps(value, ensure_ascii=False)

    existing = await cache_get_row(client, key)
    if existing:
        await cache_update(
            client,
            key,
            {
                "value_json": payload_json,
                "expires_at": expires_iso,
            },
        )
    else:
        await cache_insert(
            client,
            {
                "key": key,
                "value_json": payload_json,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": expires_iso,
            },
        )
