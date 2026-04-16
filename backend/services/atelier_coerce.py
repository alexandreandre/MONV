"""
Coercion du dossier Atelier (JSON LLM → modèles Pydantic).

Sans dépendance au pipeline MONV ni aux LLM — importable pour tests / benchmark.
"""

from __future__ import annotations

from typing import Any

from models.schemas import (
    AgentSynthesis,
    BusinessCanvas,
    FlowActor,
    FlowEdge,
    FlowMap,
    ProjectBrief,
    SegmentBrief,
)


def coerce_dossier(raw: dict[str, Any]) -> tuple[
    ProjectBrief, BusinessCanvas, FlowMap, list[SegmentBrief], AgentSynthesis
]:
    """Valide et nettoie la réponse LLM pour la rendre sûre à consommer.

    Toute clé manquante est remplacée par un défaut silencieux : l'Atelier
    doit toujours produire *quelque chose*, même si le LLM a été bavard.
    """
    b = raw.get("brief") or {}
    brief = ProjectBrief(
        nom=str(b.get("nom") or "Mon projet").strip()[:60] or "Mon projet",
        tagline=str(b.get("tagline") or "").strip()[:140],
        secteur=str(b.get("secteur") or "").strip()[:140],
        localisation=str(b.get("localisation") or "").strip()[:140],
        cible=str(b.get("cible") or "B2C").strip(),
        budget=str(b.get("budget") or "").strip()[:80],
        modele_revenus=str(b.get("modele_revenus") or "").strip()[:140],
        ambition=str(b.get("ambition") or "").strip()[:140],
    )

    c = raw.get("canvas") or {}

    def _lst(key: str) -> list[str]:
        v = c.get(key) or []
        return [str(x).strip() for x in v if str(x).strip()][:6]

    canvas = BusinessCanvas(
        proposition_valeur=_lst("proposition_valeur"),
        segments_clients=_lst("segments_clients"),
        canaux=_lst("canaux"),
        relation_client=_lst("relation_client"),
        sources_revenus=_lst("sources_revenus"),
        ressources_cles=_lst("ressources_cles"),
        activites_cles=_lst("activites_cles"),
        partenaires_cles=_lst("partenaires_cles"),
        structure_couts=_lst("structure_couts"),
    )

    segments_raw = raw.get("segments") or []
    segments: list[SegmentBrief] = []
    seen_keys: set[str] = set()
    _allowed_modes: set[str] = {"prospection", "sous_traitant", "rachat"}
    for s in segments_raw:
        if not isinstance(s, dict):
            continue
        mode = str(s.get("mode") or "prospection").strip()
        if mode not in _allowed_modes:
            mode = "prospection"
        key = str(s.get("key") or "").strip().lower()[:40] or f"segment_{len(segments)+1}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        query = str(s.get("query") or "").strip()
        if not query:
            continue
        segments.append(
            SegmentBrief(
                key=key,
                label=str(s.get("label") or key.replace("_", " ").title())[:80],
                description=str(s.get("description") or "").strip()[:240],
                mode=mode,
                query=query[:400],
                icon=str(s.get("icon") or "building").strip()[:32],
            )
        )
        if len(segments) >= 5:
            break

    valid_segment_keys = {s.key for s in segments}

    f = raw.get("flows") or {}

    def _parse_acteurs(flows_dict: dict[str, Any]) -> list[FlowActor]:
        out: list[FlowActor] = []
        raw_actors = flows_dict.get("acteurs") or []
        for item in raw_actors[:14]:
            if isinstance(item, str):
                lab = item.strip()
                if lab:
                    out.append(FlowActor(label=lab[:60], segment_key=None))
                continue
            if not isinstance(item, dict):
                continue
            lab = str(item.get("label") or item.get("nom") or "").strip()
            if not lab:
                continue
            sk_raw = item.get("segment_key")
            sk: str | None = None
            if sk_raw is not None and str(sk_raw).strip():
                cand = str(sk_raw).strip().lower()[:40]
                if cand in valid_segment_keys:
                    sk = cand
            aid = str(item.get("actor_id") or item.get("id") or "").strip()[:40] or None
            role = str(item.get("role") or "").strip()[:48] or None
            hint = str(item.get("hint") or "").strip()[:140] or None
            em = str(item.get("emphasis") or "").strip().lower()[:12] or None
            if em not in ("primary", "secondary", None):
                em = None
            out.append(
                FlowActor(
                    label=lab[:60],
                    segment_key=sk,
                    actor_id=aid,
                    role=role,
                    hint=hint,
                    emphasis=em,
                )
            )
        return out

    def _edges(key: str) -> list[FlowEdge]:
        out: list[FlowEdge] = []
        for e in (f.get(key) or []):
            if not isinstance(e, dict):
                continue
            o = str(e.get("origine") or e.get("from") or "").strip()
            d = str(e.get("destination") or e.get("to") or "").strip()
            lbl = str(e.get("label") or "").strip()
            det = str(e.get("detail") or "").strip()[:400] or None
            pat = str(e.get("pattern") or "").strip().lower()[:12] or None
            if pat not in ("solid", "dashed", None):
                pat = None
            if o and d:
                out.append(
                    FlowEdge(
                        origine=o[:60],
                        destination=d[:60],
                        label=lbl[:80],
                        detail=det,
                        pattern=pat,
                    )
                )
        return out[:14]

    fd = f if isinstance(f, dict) else {}
    lay = str(fd.get("layout") or fd.get("disposition") or "").strip().lower()[:16] or None
    if lay not in ("radial", "horizontal", "vertical", None):
        lay = None
    flows = FlowMap(
        acteurs=_parse_acteurs(fd),
        flux_valeur=_edges("flux_valeur"),
        flux_financiers=_edges("flux_financiers"),
        flux_information=_edges("flux_information"),
        diagram_title=str(fd.get("diagram_title") or fd.get("titre") or "").strip()[:120] or None,
        layout=lay,
        flow_insight=str(fd.get("flow_insight") or fd.get("lecture_en_bref") or "").strip()[:280]
        or None,
    )

    syn = raw.get("synthesis") or {}

    def _lst2(key: str, lim: int = 6) -> list[str]:
        v = syn.get(key) or []
        return [str(x).strip() for x in v if str(x).strip()][:lim]

    synthesis = AgentSynthesis(
        forces=_lst2("forces"),
        risques=_lst2("risques"),
        prochaines_etapes=_lst2("prochaines_etapes", 7),
        kpis=_lst2("kpis"),
        budget_estimatif=(str(syn.get("budget_estimatif") or "").strip()[:140] or None),
    )

    return brief, canvas, flows, segments, synthesis
