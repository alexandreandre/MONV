"""Tests purs pour le parsing JSON des sorties LLM."""

from __future__ import annotations

import json

import pytest

from utils.llm import extract_first_json_object, parse_llm_json_text


def test_extract_first_json_object_nested():
    s = 'blah ```json\n{"a": {"b": 1}}\n``` tail'
    assert extract_first_json_object(s) == '{"a": {"b": 1}}'


def test_extract_first_json_object_respects_strings():
    s = r'{"x": "hello \"world\"", "y": 2}'
    out = extract_first_json_object(s)
    assert out is not None
    assert json.loads(out)["x"] == 'hello "world"'


def test_parse_llm_json_text_markdown_fence():
    raw = "```json\n{\"ok\": true}\n```"
    assert parse_llm_json_text(raw) == {"ok": True}


def test_parse_llm_json_text_prefix_noise():
    raw = "Voici le JSON :\n{\"a\": 1}\n fin"
    assert parse_llm_json_text(raw) == {"a": 1}


def test_parse_llm_json_text_invalid_raises():
    with pytest.raises(json.JSONDecodeError):
        parse_llm_json_text("pas du json")
