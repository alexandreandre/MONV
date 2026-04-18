"""
Mutations du dossier Atelier : dédup inter-segments, totaux, parse JSON message.

Sans import depuis `services.agent` (évite les cycles d'import).
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from models.schemas import BusinessDossier, ProjectBrief, SegmentBrief, SegmentResult


def preview_row_dedup_key(row: dict[str, Any]) -> str:
    """Clé alignée sur `api_engine._dedup_key` pour lignes déjà sérialisées."""
    s = str(row.get("siren") or "").strip()
    if s:
        return f"siren:{s}"
    nom = (str(row.get("nom") or "")).lower().strip()
    ville = (str(row.get("ville") or "")).lower().strip()
    return f"name:{nom}|{ville}"


def merge_atelier_cross_segment_tags(segments: list[SegmentResult]) -> None:
    """Sur chaque ligne de `preview`, remplit `segments` avec toutes les clés de segment
    qui partagent la même entreprise (dédup SIREN prioritaire)."""
    key_to_keys: dict[str, set[str]] = defaultdict(set)
    for seg in segments:
        if seg.out_of_scope:
            continue
        for row in seg.preview:
            dk = str(row.get("_dedup_key") or preview_row_dedup_key(row)).strip()
            if dk in ("name:|", "siren:"):
                continue
            key_to_keys[dk].add(seg.key)
    for seg in segments:
        for row in seg.preview:
            dk = str(row.get("_dedup_key") or preview_row_dedup_key(row)).strip()
            tags = key_to_keys.get(dk) or {seg.key}
            row["segments"] = sorted(tags)


def atelier_dossier_rollup_fields(segments: list[SegmentResult]) -> dict[str, int]:
    """Totaux dossier : somme des `total` segment, uniques SIREN/nom, pertinents (ok+warning)."""
    total_raw = sum(s.total for s in segments)
    total_credits = sum(s.credits_required for s in segments)
    keys_all: set[str] = set()
    keys_relevant: set[str] = set()
    for s in segments:
        if s.out_of_scope:
            continue
        for row in s.preview:
            dk = str(row.get("_dedup_key") or preview_row_dedup_key(row)).strip()
            if dk in ("name:|", "siren:"):
                continue
            keys_all.add(dk)
            flg = row.get("relevance_flag")
            if flg in ("ok", "warning"):
                keys_relevant.add(dk)
    return {
        "total_raw": total_raw,
        "total_unique": len(keys_all),
        "total_relevant": len(keys_relevant),
        "total_credits": total_credits,
    }


def business_dossier_from_metadata_json(metadata_json: str | None) -> BusinessDossier | None:
    if not metadata_json or not str(metadata_json).strip():
        return None
    try:
        d = json.loads(metadata_json)
    except json.JSONDecodeError:
        return None
    d = {k: v for k, v in d.items() if k != "mode"}
    try:
        return BusinessDossier.model_validate(d)
    except Exception:
        return None


def segment_result_to_brief(seg: SegmentResult) -> SegmentBrief:
    return SegmentBrief(
        key=seg.key,
        label=seg.label,
        description=seg.description,
        mode=seg.mode,
        query=seg.query,
        icon=seg.icon,
        out_of_scope=seg.out_of_scope,
        out_of_scope_note=seg.out_of_scope_note,
    )


def dossier_with_replaced_segment(dossier: BusinessDossier, key: str, new_seg: SegmentResult) -> BusinessDossier:
    nk = key.lower().strip()
    segs = [new_seg if s.key.lower().strip() == nk else s for s in dossier.segments]
    return dossier.model_copy(update={"segments": segs})


def dossier_after_segment_list_refresh(dossier: BusinessDossier) -> BusinessDossier:
    """Recalcule tags inter-segments, totaux, incrémente la version."""
    segs = list(dossier.segments)
    merge_atelier_cross_segment_tags(segs)
    roll = atelier_dossier_rollup_fields(segs)
    return dossier.model_copy(
        update={
            "segments": segs,
            "total_raw": roll["total_raw"],
            "total_unique": roll["total_unique"],
            "total_relevant": roll["total_relevant"],
            "total_credits": roll["total_credits"],
            "version": (dossier.version or 1) + 1,
            "generated_at": datetime.now(timezone.utc),
        }
    )


def dossier_with_brief_only(dossier: BusinessDossier, brief: ProjectBrief) -> BusinessDossier:
    if not isinstance(brief, ProjectBrief):
        brief = ProjectBrief.model_validate(brief)
    return dossier.model_copy(
        update={
            "brief": brief,
            "version": (dossier.version or 1) + 1,
            "generated_at": datetime.now(timezone.utc),
        }
    )
