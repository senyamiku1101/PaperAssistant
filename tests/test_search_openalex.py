import pytest
import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scripts.search_openalex import build_query, parse_work

def test_build_query_basic():
    keywords = ["turbine cooling", "film cooling"]
    params = build_query(keywords, "2024-2026")
    assert "search" in params
    assert "turbine+cooling" in params["search"] or "turbine cooling" in params["search"]

def test_parse_work_extracts_fields():
    sample = {
        "id": "https://openalex.org/W123",
        "doi": "https://doi.org/10.1234/example",
        "title": "Film Cooling in Turbines",
        "authorships": [
            {"author": {"display_name": "Zhang, L."}},
            {"author": {"display_name": "Wang, M."}},
        ],
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
    assert result["cited_by_count"] == 0
