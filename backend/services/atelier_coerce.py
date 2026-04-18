"""
Coercion du dossier Atelier (JSON LLM → modèles Pydantic).

Sans dépendance au pipeline MONV ni aux LLM — importable pour tests / benchmark.
"""

from __future__ import annotations

from typing import Any

from models.schemas import (
    AgentSynthesis,
    AtelierChecklist,
    BusinessCanvas,
    ChecklistItem,
    ChecklistSection,
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

    def _opt_int(v: object) -> int | None:
        if v is None:
            return None
        try:
            x = int(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        if x < 0 or x > 2_000_000_000:
            return None
        return x

    hyp_raw = b.get("budget_hypotheses") or []
    budget_hypotheses = [
        str(x).strip()
        for x in (hyp_raw if isinstance(hyp_raw, list) else [])
        if str(x).strip()
    ][:12]

    brief = ProjectBrief(
        nom=str(b.get("nom") or "Mon projet").strip()[:60] or "Mon projet",
        tagline=str(b.get("tagline") or "").strip()[:140],
        secteur=str(b.get("secteur") or "").strip()[:140],
        localisation=str(b.get("localisation") or "").strip()[:140],
        cible=str(b.get("cible") or "B2C").strip(),
        budget=str(b.get("budget") or "").strip()[:400],
        modele_revenus=str(b.get("modele_revenus") or "").strip()[:140],
        ambition=str(b.get("ambition") or "").strip()[:140],
        budget_min_eur=_opt_int(b.get("budget_min_eur")),
        budget_max_eur=_opt_int(b.get("budget_max_eur")),
        budget_hypotheses=budget_hypotheses,
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
        if not query and not bool(s.get("out_of_scope")):
            continue
        oos = bool(s.get("out_of_scope"))
        oos_note = str(s.get("out_of_scope_note") or "").strip()[:400] or None
        segments.append(
            SegmentBrief(
                key=key,
                label=str(s.get("label") or key.replace("_", " ").title())[:80],
                description=str(s.get("description") or "").strip()[:240],
                mode=mode,
                query=(query[:400] if query else ""),
                icon=str(s.get("icon") or "building").strip()[:32],
                out_of_scope=oos,
                out_of_scope_note=oos_note,
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

    def _ordres_grandeur() -> list[str]:
        v = syn.get("ordres_grandeur") or syn.get("ordres_de_grandeur") or []
        if isinstance(v, str) and v.strip():
            return [v.strip()[:520]]
        if not isinstance(v, list):
            return []
        out: list[str] = []
        for x in v:
            s = str(x).strip()
            if s:
                out.append(s[:520])
            if len(out) >= 12:
                break
        return out

    def _parse_item(obj: object) -> ChecklistItem | None:
        if isinstance(obj, str):
            lab = obj.strip()
            return ChecklistItem(label=lab[:280], guide="") if lab else None
        if not isinstance(obj, dict):
            return None
        lab = str(obj.get("label") or obj.get("texte") or obj.get("action") or "").strip()
        if not lab:
            return None
        guide = str(obj.get("guide") or obj.get("aide") or obj.get("detail") or "").strip()
        return ChecklistItem(label=lab[:420], guide=guide[:2600])

    def _parse_checklist(raw_cl: object) -> AtelierChecklist | None:
        if not isinstance(raw_cl, dict):
            return None
        sections: list[ChecklistSection] = []
        raw_sections = (
            raw_cl.get("sections")
            or raw_cl.get("etapes")
            or raw_cl.get("phases")
            or []
        )
        for sec in raw_sections[:40]:
            if not isinstance(sec, dict):
                continue
            title = (
                str(sec.get("title") or sec.get("nom") or sec.get("phase") or "")
                .strip()[:220]
            )
            if not title:
                continue
            subtitle = (
                str(sec.get("subtitle") or sec.get("sous_titre") or "")
                .strip()[:200]
                or None
            )
            items: list[ChecklistItem] = []
            item_list = sec.get("items") or sec.get("actions") or sec.get("taches") or []
            for it in item_list[:60]:
                ci = _parse_item(it)
                if ci:
                    items.append(ci)
            if items:
                sections.append(
                    ChecklistSection(title=title, subtitle=subtitle, items=items)
                )
        pitfalls: list[ChecklistItem] = []
        for it in (raw_cl.get("pitfalls") or raw_cl.get("pieges") or [])[:18]:
            ci = _parse_item(it)
            if ci:
                pitfalls.append(ci)
        headline = str(raw_cl.get("headline") or raw_cl.get("titre") or "").strip()[:220]
        lede = str(raw_cl.get("lede") or raw_cl.get("intro") or "").strip()[:360] or None
        pitfalls_title = (
            str(raw_cl.get("pitfalls_title") or raw_cl.get("pieges_titre") or "")
            .strip()[:120]
            or None
        )
        if not sections and not pitfalls:
            return None
        return AtelierChecklist(
            headline=headline,
            lede=lede,
            sections=sections,
            pitfalls_title=pitfalls_title,
            pitfalls=pitfalls,
        )

    raw_checklist = syn.get("checklist")
    checklist = _parse_checklist(raw_checklist) if raw_checklist is not None else None

    synthesis = AgentSynthesis(
        forces=_lst2("forces"),
        risques=_lst2("risques"),
        prochaines_etapes=_lst2("prochaines_etapes", 12),
        kpis=_lst2("kpis"),
        budget_estimatif=(str(syn.get("budget_estimatif") or "").strip()[:140] or None),
        ordres_grandeur=_ordres_grandeur(),
        conseil_semaine=(
            str(syn.get("conseil_semaine") or syn.get("conseil_de_la_semaine") or "")
            .strip()[:900]
            or None
        ),
        checklist=checklist,
    )

    return brief, canvas, flows, segments, synthesis


def coerce_canvas_from_llm_dict(raw: dict[str, Any]) -> BusinessCanvas:
    """Extrait un `BusinessCanvas` depuis la sortie LLM (`{"canvas": {...}}` ou canvas racine)."""
    c = raw.get("canvas") if isinstance(raw.get("canvas"), dict) else raw
    if not isinstance(c, dict):
        c = {}

    def _lst(key: str) -> list[str]:
        v = c.get(key) or []
        return [str(x).strip() for x in v if str(x).strip()][:6]

    return BusinessCanvas(
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


def coerce_flows_from_llm_dict(raw: dict[str, Any], valid_segment_keys: set[str]) -> FlowMap:
    """Extrait un `FlowMap` depuis la sortie LLM ; `valid_segment_keys` filtre les `segment_key`."""
    f = raw.get("flows") if isinstance(raw.get("flows"), dict) else raw
    if not isinstance(f, dict):
        f = {}

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

    lay = str(f.get("layout") or f.get("disposition") or "").strip().lower()[:16] or None
    if lay not in ("radial", "horizontal", "vertical", None):
        lay = None
    return FlowMap(
        acteurs=_parse_acteurs(f),
        flux_valeur=_edges("flux_valeur"),
        flux_financiers=_edges("flux_financiers"),
        flux_information=_edges("flux_information"),
        diagram_title=str(f.get("diagram_title") or f.get("titre") or "").strip()[:120] or None,
        layout=lay,
        flow_insight=str(f.get("flow_insight") or f.get("lecture_en_bref") or "").strip()[:280]
        or None,
    )
