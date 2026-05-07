"""Tests for search_openalex.py."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
import requests

from scripts.search_openalex import (
    build_query,
    parse_work,
    reconstruct_abstract,
    save_results,
    search_openalex,
    validate_config,
)


# ---------------------------------------------------------------------------
# ISSUE 4: tightened build_query assertions
# ---------------------------------------------------------------------------
def test_build_query_basic():
    keywords = ["turbine cooling", "film cooling"]
    params = build_query(keywords, "2024-2026")

    assert params["search"] == '"turbine cooling" OR "film cooling"'
    assert params["filter"] == "publication_year:2024-2026"
    assert params["sort"] == "cited_by_count:desc"
    assert params["per_page"] == 50


# ---------------------------------------------------------------------------
# parse_work
# ---------------------------------------------------------------------------
def test_parse_work_extracts_fields():
    sample = {
        "id": "https://openalex.org/W123",
        "doi": "https://doi.org/10.1234/example",
        "title": "Film Cooling in Turbines",
        "authorships": [
            {"author": {"display_name": "Zhang, L."}},
            {"author": {"display_name": "Wang, M."}},
        ],
        "abstract_inverted_index": {
            "Film": [0],
            "cooling": [1],
            "is": [2],
            "effective": [3],
        },
        "publication_year": 2025,
        "cited_by_count": 15,
        "primary_location": {
            "source": {"display_name": "J. Turbomachinery"}
        },
        "type": "journal-article",
    }
    result = parse_work(sample)
    assert result["title"] == "Film Cooling in Turbines"
    assert result["doi"] == "10.1234/example"
    assert result["authors"] == ["Zhang, L.", "Wang, M."]
    assert result["abstract"] == "Film cooling is effective"
    assert result["year"] == 2025
    assert result["cited_by_count"] == 15
    assert result["source"] == "J. Turbomachinery"
    assert result["openalex_id"] == "https://openalex.org/W123"


def test_parse_work_missing_fields():
    sample = {"id": "https://openalex.org/W456"}
    result = parse_work(sample)
    assert result["title"] == ""
    assert result["doi"] is None
    assert result["authors"] == []
    assert result["abstract"] == ""
    assert result["cited_by_count"] == 0


# ---------------------------------------------------------------------------
# ISSUE 2: reconstruct_abstract tests
# ---------------------------------------------------------------------------
def test_reconstruct_abstract_valid():
    inverted = {
        "The": [0],
        "quick": [1],
        "brown": [2],
        "fox": [3],
    }
    assert reconstruct_abstract(inverted) == "The quick brown fox"


def test_reconstruct_abstract_multiple_positions():
    # words repeated at different positions
    inverted = {
        "hello": [0, 3],
        "world": [1],
        "goodbye": [2],
    }
    assert reconstruct_abstract(inverted) == "hello world goodbye hello"


def test_reconstruct_abstract_none():
    assert reconstruct_abstract(None) == ""


def test_reconstruct_abstract_empty_dict():
    assert reconstruct_abstract({}) == ""


def test_reconstruct_abstract_not_a_dict():
    assert reconstruct_abstract("not-a-dict") == ""
    assert reconstruct_abstract([]) == ""


# ---------------------------------------------------------------------------
# ISSUE 4: save_results test
# ---------------------------------------------------------------------------
def test_save_results(tmp_path):
    results = [{"title": "Test Paper", "year": 2025}]
    path = save_results(results, str(tmp_path), "turbine cooling")
    assert os.path.isfile(path)
    assert "search_" in path
    assert path.endswith(".json")

    with open(path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == results


def test_save_results_sanitizes_filename(tmp_path):
    """Ensure unsafe filename characters are replaced."""
    results = []
    path = save_results(results, str(tmp_path), 'test<name>:"bad"')
    basename = os.path.basename(path)
    # None of the unsafe chars should appear
    for ch in '<>:"/\\|?*':
        assert ch not in basename


# ---------------------------------------------------------------------------
# ISSUE 4: search_openalex mocked test
# ---------------------------------------------------------------------------
def _make_mock_response(data, status_code=200):
    """Helper to build a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(
            f"{status_code} Server Error"
        )
    return resp


def test_search_openalex_mocked_first_page_only():
    """Simulate a single-page API response (no cursor)."""
    mock_data = {
        "results": [
            {
                "id": "https://openalex.org/W1",
                "title": "Paper 1",
                "publication_year": 2025,
                "cited_by_count": 10,
                "authorships": [],
                "primary_location": {"source": {"display_name": "J. Test"}},
                "type": "journal-article",
            },
            {
                "id": "https://openalex.org/W2",
                "title": "Paper 2",
                "publication_year": 2025,
                "cited_by_count": 5,
                "authorships": [],
                "primary_location": {"source": {"display_name": "J. Test"}},
                "type": "journal-article",
            },
        ],
        "meta": {"next_cursor": None},
    }

    with patch("scripts.search_openalex.requests.get") as mock_get:
        mock_get.return_value = _make_mock_response(mock_data)
        results = search_openalex(
            keywords=["test"],
            years="2025-2025",
            email="test@example.com",
            max_results=10,
        )

    assert len(results) == 2
    assert results[0]["title"] == "Paper 1"
    assert results[1]["title"] == "Paper 2"
    mock_get.assert_called_once()


def test_search_openalex_mocked_pagination():
    """Simulate a two-page API response with cursor."""
    page1 = {
        "results": [
            {
                "id": "https://openalex.org/W1",
                "title": "Paper A",
                "publication_year": 2025,
                "cited_by_count": 10,
                "authorships": [],
                "primary_location": {"source": {"display_name": "Src"}},
                "type": "journal-article",
            },
        ],
        "meta": {"next_cursor": "abc123"},
    }
    page2 = {
        "results": [
            {
                "id": "https://openalex.org/W2",
                "title": "Paper B",
                "publication_year": 2025,
                "cited_by_count": 8,
                "authorships": [],
                "primary_location": {"source": {"display_name": "Src"}},
                "type": "journal-article",
            },
        ],
        "meta": {"next_cursor": None},
    }

    with patch("scripts.search_openalex.requests.get") as mock_get:
        mock_get.side_effect = [
            _make_mock_response(page1),
            _make_mock_response(page2),
        ]
        results = search_openalex(
            keywords=["test"],
            years="2025-2025",
            email="test@example.com",
            max_results=10,
        )

    assert len(results) == 2
    assert results[0]["title"] == "Paper A"
    assert results[1]["title"] == "Paper B"
    assert mock_get.call_count == 2


def test_search_openalex_mocked_request_error_returns_partial():
    """On repeated request failures, return partial results."""
    page1 = {
        "results": [
            {
                "id": "https://openalex.org/W1",
                "title": "Paper X",
                "publication_year": 2025,
                "cited_by_count": 3,
                "authorships": [],
                "primary_location": {"source": {"display_name": "Src"}},
                "type": "journal-article",
            },
        ],
        "meta": {"next_cursor": "xyz"},
    }

    with patch("scripts.search_openalex.requests.get") as mock_get:
        resp_ok = _make_mock_response(page1)
        resp_fail = _make_mock_response({}, 500)

        # first page ok, second page fails all 3 attempts
        mock_get.side_effect = [resp_ok, resp_fail, resp_fail, resp_fail]
        results = search_openalex(
            keywords=["test"],
            years="2025-2025",
            email="test@example.com",
            max_results=10,
        )

    # Should have the first page result, then break on second page failure
    assert len(results) == 1
    assert results[0]["title"] == "Paper X"


# ---------------------------------------------------------------------------
# ISSUE 5: validate_config tests
# ---------------------------------------------------------------------------
def test_validate_config_valid():
    config = {
        "openalex": {"email": "test@example.com"},
        "topics": [
            {"name": "topic1", "keywords": ["kw1", "kw2"]},
        ],
    }
    assert validate_config(config) is True


def test_validate_config_missing_email():
    config = {
        "openalex": {},
        "topics": [{"name": "t1", "keywords": ["k1"]}],
    }
    assert validate_config(config) is False


def test_validate_config_no_openalex_section():
    config = {
        "topics": [{"name": "t1", "keywords": ["k1"]}],
    }
    assert validate_config(config) is False


def test_validate_config_missing_name():
    config = {
        "openalex": {"email": "e@e.com"},
        "topics": [{"keywords": ["k1"]}],
    }
    assert validate_config(config) is False


def test_validate_config_missing_keywords():
    config = {
        "openalex": {"email": "e@e.com"},
        "topics": [{"name": "t1"}],
    }
    assert validate_config(config) is False


def test_validate_config_empty_topics():
    config = {
        "openalex": {"email": "e@e.com"},
        "topics": [],
    }
    assert validate_config(config) is False


def test_validate_config_topics_not_list():
    config = {
        "openalex": {"email": "e@e.com"},
        "topics": "not-a-list",
    }
    assert validate_config(config) is False
