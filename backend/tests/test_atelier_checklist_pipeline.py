"""Tests sans LLM pour le merge des lots de checklist Atelier."""

from services.atelier_coerce import merge_atelier_checklist_detail_chunks


def test_merge_detail_chunks_preserves_order_and_fills_from_chunks():
    outline = [
        {"id": "s01", "title": "A", "subtitle": None},
        {"id": "s02", "title": "B", "subtitle": "sub"},
    ]
    chunks = [
        {
            "sections": [
                {
                    "id": "s01",
                    "title": "A",
                    "subtitle": None,
                    "items": [{"label": "x", "guide": "gx"}],
                }
            ]
        },
        {
            "sections": [
                {
                    "id": "s02",
                    "title": "B",
                    "subtitle": "sub",
                    "items": [{"label": "y", "guide": "gy"}],
                }
            ]
        },
    ]
    merged = merge_atelier_checklist_detail_chunks(outline, chunks)
    assert len(merged) == 2
    assert merged[0]["title"] == "A"
    assert merged[0]["items"][0]["label"] == "x"
    assert merged[1]["items"][0]["label"] == "y"


def test_merge_detail_chunks_falls_back_to_skeleton_when_chunk_missing():
    outline = [{"id": "s01", "title": "Seule", "subtitle": None}]
    merged = merge_atelier_checklist_detail_chunks(outline, [{"sections": []}])
    assert len(merged) == 1
    assert merged[0]["title"] == "Seule"
    assert merged[0]["items"] == []
