"""Tests for compare_library.py."""

import json
import os
import tempfile

import pytest

from scripts.compare_library import (
    check_duplicate,
    compare_with_library,
    load_library_csv,
    normalize_title,
)


def test_normalize_title_removes_punctuation_and_case():
    assert normalize_title("Film Cooling in Turbines!") == "filmcoolinginturbines"
    assert normalize_title("Heat Transfer: A Review") == "heattransferareview"
    assert normalize_title("  Extra   Spaces  ") == "extraspaces"


def test_normalize_title_space_removal_behavior():
    """Document: normalize_title treats heat-transfer and heattransfer as equal."""
    assert normalize_title("heat transfer") == normalize_title("heattransfer")


def test_check_duplicate_doi_match():
    library = [{"title": "Old Paper", "doi": "10.1234/abcd"}]
    candidate = {"title": "Different Title", "doi": "10.1234/abcd"}
    is_dup, reason = check_duplicate(candidate, library)
    assert is_dup
    assert reason == "doi_match"


def test_check_duplicate_title_match():
    library = [{"title": "Film Cooling in Turbines", "doi": ""}]
    candidate = {"title": "Film Cooling in Turbines", "doi": ""}
    is_dup, reason = check_duplicate(candidate, library)
    assert is_dup
    assert reason == "title_match"


def test_check_duplicate_no_match():
    library = [{"title": "Old Paper", "doi": "10.1234/abcd"}]
    candidate = {"title": "Completely New Research", "doi": "10.5678/efgh"}
    is_dup, reason = check_duplicate(candidate, library)
    assert not is_dup


def test_check_duplicate_none_doi_handled():
    library = [{"title": "Paper A", "doi": None}]
    candidate = {"title": "Paper A", "doi": None}
    is_dup, reason = check_duplicate(candidate, library)
    assert is_dup
    assert reason == "title_match"


def test_compare_with_library_removes_duplicates():
    library = [{"title": "Existing Paper", "doi": "10.1234/abcd"}]
    candidates = [
        {"title": "Existing Paper", "doi": "10.1234/abcd", "openalex_id": "W1"},
        {"title": "New Paper", "doi": "10.5678/efgh", "openalex_id": "W2"},
    ]
    filtered = compare_with_library(candidates, library)
    assert len(filtered) == 1
    assert filtered[0]["openalex_id"] == "W2"


def test_compare_with_library_all_new():
    library = [{"title": "Old Paper", "doi": "10.1234/abcd"}]
    candidates = [
        {"title": "New Paper 1", "doi": "10.1111/a"},
        {"title": "New Paper 2", "doi": "10.2222/b"},
    ]
    filtered = compare_with_library(candidates, library)
    assert len(filtered) == 2


def test_compare_with_library_empty_library():
    candidates = [{"title": "Any Paper", "doi": "10.1234/x"}]
    filtered = compare_with_library(candidates, [])
    assert len(filtered) == 1


def test_load_library_csv(tmp_path):
    csv_content = (
        "title,doi,authors,year\n"
        "Film Cooling,10.1234/a,Zhang,2025\n"
        "Combustion,10.5678/b,Li,2024\n"
    )
    csv_path = tmp_path / "library.csv"
    csv_path.write_text(csv_content, encoding="utf-8")
    library = load_library_csv(str(csv_path))
    assert len(library) == 2
    assert library[0]["title"] == "Film Cooling"
    assert library[1]["doi"] == "10.5678/b"


def test_load_library_csv_missing_columns(tmp_path):
    # CSV with only some columns — still loads what's available
    csv_content = "title\nPaper A\n"
    csv_path = tmp_path / "minimal.csv"
    csv_path.write_text(csv_content, encoding="utf-8")
    library = load_library_csv(str(csv_path))
    assert len(library) == 1
    assert library[0]["title"] == "Paper A"


def test_check_duplicate_case_insensitive_doi():
    library = [{"title": "Paper", "doi": "10.1234/ABCD"}]
    candidate = {"title": "Different", "doi": "10.1234/abcd"}
    is_dup, reason = check_duplicate(candidate, library)
    assert is_dup
    assert reason == "doi_match"
