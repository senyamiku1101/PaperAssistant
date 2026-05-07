import pytest
import datetime
import json
import os
from scripts.monitor import get_monitored_topics, get_week_label, generate_report


def test_get_monitored_topics():
    config = {
        "topics": [
            {"name": "涡轮冷却", "monitor": True},
            {"name": "燃烧", "monitor": False},
            {"name": "噪声", "monitor": True},
        ]
    }
    result = get_monitored_topics(config)
    assert len(result) == 2
    assert result[0]["name"] == "涡轮冷却"
    assert result[1]["name"] == "噪声"


def test_get_monitored_topics_none():
    config = {"topics": [{"name": "test", "monitor": False}]}
    assert get_monitored_topics(config) == []


def test_get_monitored_topics_no_monitor_key():
    config = {"topics": [{"name": "test"}]}
    assert get_monitored_topics(config) == []


def test_get_week_label():
    label = get_week_label(datetime.date(2026, 5, 7))
    assert label == "2026-W19"


def test_get_week_label_monday():
    label = get_week_label(datetime.date(2026, 1, 5))  # Monday
    assert label == "2026-W02"


def test_generate_report_structure():
    topic_name = "涡轮冷却"
    scored = [
        {
            "title": "Paper A on turbine cooling",
            "authors": ["Zhang"],
            "year": 2025,
            "doi": "10.1234/a",
            "source": "J. Turbomachinery",
            "cited_by_count": 30,
            "scores": {"composite": 87, "relevance": 90, "quality": 70, "novelty": 80, "recency": 90},
        },
        {
            "title": "Paper B marginal",
            "authors": ["Li"],
            "year": 2024,
            "doi": "10.1234/b",
            "source": "ASME",
            "cited_by_count": 5,
            "scores": {"composite": 62, "relevance": 60, "quality": 30, "novelty": 50, "recency": 75},
        },
        {
            "title": "Paper C low relevance",
            "authors": ["Wang"],
            "year": 2022,
            "doi": "10.1234/c",
            "source": "Other Journal",
            "cited_by_count": 2,
            "scores": {"composite": 45, "relevance": 30, "quality": 20, "novelty": 40, "recency": 50},
        },
    ]
    report = generate_report(topic_name, scored, new_count=15, pushed_count=8)
    assert "涡轮冷却" in report
    assert "Paper A" in report
    assert "Paper B" in report
    assert "Paper C" in report
    assert "15" in report
    assert "8" in report
    # Priority sections
    assert "高优先级" in report
    assert "中优先级" in report
    assert "待定" in report


def test_generate_report_empty():
    report = generate_report("test topic", [], new_count=0, pushed_count=0)
    assert "test topic" in report
    assert "0" in report


def test_generate_report_only_high():
    scored = [
        {"title": "Great Paper", "scores": {"composite": 90, "relevance": 95, "quality": 80, "novelty": 85, "recency": 95}}
    ]
    report = generate_report("topic", scored, 5, 3)
    assert "高优先级" in report
    assert "中优先级" not in report
    assert "待定" not in report
