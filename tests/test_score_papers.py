import pytest
from scripts.score_papers import (
    score_relevance,
    score_quality,
    score_recency,
    score_papers,
)


def test_score_relevance_full_match():
    paper = {"title": "Turbine cooling with film holes", "abstract": "Study of shaped hole geometry"}
    keywords = ["turbine cooling", "film cooling", "shaped hole"]
    score = score_relevance(paper, keywords)
    assert score > 60  # Multiple keyword matches


def test_score_relevance_partial_match():
    paper = {"title": "Turbine cooling research", "abstract": ""}
    keywords = ["turbine cooling", "film cooling", "combustion"]
    score = score_relevance(paper, keywords)
    assert 0 < score < 70  # Only 1 of 3 keywords matches


def test_score_relevance_no_match():
    paper = {"title": "Astrophysics and dark matter", "abstract": "Galaxy formation"}
    keywords = ["turbine cooling", "film cooling"]
    score = score_relevance(paper, keywords)
    assert score == 0


def test_score_relevance_empty_keywords():
    paper = {"title": "Anything", "abstract": ""}
    score = score_relevance(paper, [])
    assert score == 0


def test_score_quality_zero_citations():
    assert score_quality({"cited_by_count": 0}) == 0


def test_score_quality_none_citations():
    assert score_quality({"cited_by_count": None}) == 0


def test_score_quality_high_citations():
    score = score_quality({"cited_by_count": 100})
    assert score == pytest.approx(100.0)


def test_score_quality_moderate():
    score = score_quality({"cited_by_count": 10})
    assert 40 < score < 60  # log10(10)*50 = 50


def test_score_recency_current_year():
    assert score_recency({"year": 2026}, current_year=2026) == 100


def test_score_recency_one_year_old():
    assert score_recency({"year": 2025}, current_year=2026) == 100  # <=1 year


def test_score_recency_three_years_old():
    assert score_recency({"year": 2023}, current_year=2026) == 75


def test_score_recency_five_years_old():
    assert score_recency({"year": 2021}, current_year=2026) == 50


def test_score_recency_old():
    assert score_recency({"year": 2015}, current_year=2026) == 25


def test_score_recency_missing_year():
    # Missing year defaults to current year -> max recency
    assert score_recency({}, current_year=2026) == 100


def test_score_papers_ranks_by_composite():
    papers = [
        {"title": "Hot turbine cooling", "cited_by_count": 50, "year": 2025, "openalex_id": "W1"},
        {"title": "Unrelated", "cited_by_count": 0, "year": 2018, "openalex_id": "W2"},
    ]
    keywords = ["turbine cooling"]
    weights = {"relevance_weight": 0.40, "quality_weight": 0.20, "novelty_weight": 0.25, "recency_weight": 0.15}
    novelty = {"W1": 80, "W2": 50}
    result = score_papers(papers, keywords, weights, novelty)
    assert result[0]["openalex_id"] == "W1"  # Higher score first
    assert "scores" in result[0]
    assert "composite" in result[0]["scores"]


def test_score_papers_weights_sum_validation():
    papers = [{"title": "Paper", "cited_by_count": 10, "year": 2025, "openalex_id": "W1"}]
    keywords = ["Paper"]
    weights = {"relevance_weight": 1.0, "quality_weight": 0.0, "novelty_weight": 0.0, "recency_weight": 0.0}
    novelty = {"W1": 50}
    result = score_papers(papers, keywords, weights, novelty)
    assert result[0]["scores"]["composite"] > 0
    assert result[0]["scores"]["quality"] == 50.0  # raw score unaffected by zero weight
    # Verify composite uses weights: relevance=100*1.0 + quality=50*0.0 + novelty=50*0.0 + recency=100*0.0 = 100
    assert result[0]["scores"]["composite"] == 100.0


def test_score_papers_default_novelty():
    """Papers not in novelty dict get default 50."""
    papers = [{"title": "Paper", "cited_by_count": 10, "year": 2025, "openalex_id": "W1"}]
    keywords = ["test"]
    weights = {"relevance_weight": 0.40, "quality_weight": 0.20, "novelty_weight": 0.25, "recency_weight": 0.15}
    result = score_papers(papers, keywords, weights, {})
    assert result[0]["scores"]["novelty"] == 50
