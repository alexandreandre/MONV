"""Compactage de l'historique LLM du Guard (router chat)."""

from datetime import datetime, timezone

import os

os.environ.setdefault("SKIP_DB_VERIFY_ON_STARTUP", "true")
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "placeholder-service-key")

from models.entities import Message  # noqa: E402
from routers.chat import _compact_messages_for_guard_llm  # noqa: E402


def _m(role: str, i: int, *, qcm: bool = False) -> Message:
    return Message(
        id=f"m{i}",
        conversation_id="c",
        role=role,
        content=f"c{i}",
        message_type="qcm" if qcm and role == "assistant" else "text",
        metadata_json=None,
        created_at=datetime.now(timezone.utc),
    )


def test_compact_keeps_short_list_unchanged():
    msgs = [_m("user", 0), _m("assistant", 1)]
    assert _compact_messages_for_guard_llm(msgs) == msgs


def test_compact_tail_when_no_qcm():
    msgs = [_m("user", i) if i % 2 == 0 else _m("assistant", i) for i in range(20)]
    out = _compact_messages_for_guard_llm(msgs)
    assert len(out) == 16
    assert out == msgs[-16:]


def test_compact_preserves_last_qcm_block():
    # 18 messages ; QCM à l'index 12 ; doit garder du contexte avant le QCM si besoin
    msgs: list[Message] = []
    for i in range(12):
        msgs.append(_m("user", i) if i % 2 == 0 else _m("assistant", i))
    msgs.append(_m("assistant", 12, qcm=True))
    msgs.append(_m("user", 13))
    msgs.append(_m("assistant", 14))
    msgs.append(_m("user", 15))
    msgs.append(_m("assistant", 16))
    msgs.append(_m("user", 17))
    out = _compact_messages_for_guard_llm(msgs)
    assert len(out) <= 16
    assert any(m.message_type == "qcm" for m in out)
    assert out[-1].role == "user"
    assert out[-1].content == "c17"
