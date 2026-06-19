"""parse_json must survive the messy shapes a real model returns."""

import json

import pytest

from engine import llm


def test_plain_object():
    assert llm.parse_json('{"a": 1}') == {"a": 1}


def test_array_verbatim():
    assert llm.parse_json('[1, 2, 3]') == [1, 2, 3]


def test_json_fence_stripped():
    raw = "```json\n{\"a\": 1}\n```"
    assert llm.parse_json(raw) == {"a": 1}


def test_prose_around_object():
    raw = 'Конечно, вот результат:\n{"title": "x", "sections": []}\nГотово.'
    assert llm.parse_json(raw) == {"title": "x", "sections": []}


def test_first_span_broken_second_valid():
    # A malformed brace span before a valid one: the valid array must win.
    raw = 'note {oops not json} then [1, 2]'
    assert llm.parse_json(raw) == [1, 2]


def test_empty_raises_value_error():
    with pytest.raises(ValueError):
        llm.parse_json("")


def test_no_json_raises_value_error():
    with pytest.raises(ValueError):
        llm.parse_json("просто текст без структуры")


def test_all_spans_malformed_raises():
    with pytest.raises(ValueError):
        llm.parse_json("{broken} [also broken}")


def test_call_claude_dry_run_returns_stub():
    assert llm.call_claude("ignored", dry_run=True, stub='{"ok": true}') == '{"ok": true}'


def test_call_claude_dry_run_without_stub_raises():
    with pytest.raises(llm.LLMError):
        llm.call_claude("ignored", dry_run=True, stub=None)
