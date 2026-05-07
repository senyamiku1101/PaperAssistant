# 个人文献检索工作流 实现计划

> **For Claude:** 使用 `superpowers:executing-plans` 技能逐任务实现。

**目标**: 构建混合架构的文献检索→筛选→审批→入库→笔记工作流，覆盖交互式搜索和每周自动监控。

**架构**: Claude Skill (CLAUDE.md) 作为交互层，Python 脚本处理 API 调用和数据处理，Windows 任务计划程序驱动每周监控。

**技术栈**: Python 3, PyYAML, requests, OpenAlex API, Zotero MCP, Obsidian MCP

---

### Task 1: 项目脚手架

**Files:**
- Create: `config/search_config.yaml`
- Create: `scripts/__init__.py`
- Create: `output/.gitkeep`

**Step 1: 创建 project scaffold**

```powershell
New-Item -ItemType Directory -Force -Path config, scripts, output
New-Item -ItemType File -Force -Path scripts/__init__.py
New-Item -ItemType File -Force -Path output/.gitkeep
```

**Step 2: 编写 search_config.yaml**

内容见 Task 1 配置模板。

**Step 3: 提交**

```bash
git add config/search_config.yaml scripts/__init__.py output/.gitkeep
git commit -m "chore: scaffold project structure and config"
```

---

### Task 2: search_openalex.py — OpenAlex API 查询

**Files:**
- Create: `scripts/search_openalex.py`
- Create: `tests/test_search_openalex.py`

**Step 1: 确认依赖**

```powershell
pip install pyyaml requests
```

**Step 2: 写测试**

```python
# tests/test_search_openalex.py
import pytest
import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scripts.search_openalex import build_query, parse_work

def test_build_query_basic():
    keywords = ["turbine cooling", "film cooling"]
    query = build_query(keywords, "2024-2026")
    assert "turbine+cooling" in query or "turbine" in query.lower()

def test_parse_work_extracts_fields():
    sample_work = {
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
    result = parse_work(sample_work)
    assert result["title"] == "Film Cooling in Turbines"
    assert result["doi"] == "https://doi.org/10.1234/example"
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
```

**Step 3: 运行测试验证失败**

```powershell
pytest tests/test_search_openalex.py -v
```
预期: 全部 FAIL (函数未定义)

**Step 4: 实现 search_openalex.py**

```python
"""OpenAlex API 文献搜索模块."""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Optional

import requests
import yaml


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_query(keywords: list[str], years: str) -> dict:
    """Build OpenAlex API query parameters."""
    search_terms = " OR ".join(f'"{kw}"' for kw in keywords)
    return {
        "search": search_terms,
        "filter": f"publication_year:{years}",
        "sort": "cited_by_count:desc",
        "per_page": 50,
    }


def parse_work(work: dict) -> dict:
    """Extract relevant fields from an OpenAlex work object."""
    doi = work.get("doi", "")
    if doi:
        doi = doi.replace("https://doi.org/", "")

    return {
        "title": work.get("title", ""),
        "doi": doi or None,
        "authors": [
            a.get("author", {}).get("display_name", "")
            for a in work.get("authorships", [])
        ],
        "abstract": "",  # abstract_inverted_index needs separate handling
        "year": work.get("publication_year"),
        "cited_by_count": work.get("cited_by_count", 0),
        "source": work.get("primary_location", {})
        .get("source", {})
        .get("display_name", ""),
        "type": work.get("type", ""),
        "openalex_id": work.get("id", ""),
        "url": f"https://openalex.org/{work.get('id', '').split('/')[-1]}" if work.get("id") else "",
    }


def search_openalex(
    keywords: list[str],
    years: str,
    email: str,
    max_results: int = 50,
) -> list[dict]:
    """Search OpenAlex for papers matching keywords and year range."""
    params = build_query(keywords, years)
    params["per_page"] = max_results
    params["mailto"] = email

    url = "https://api.openalex.org/works"
    results = []

    while url and len(results) < max_results:
        resp = requests.get(url, params=params if url == "https://api.openalex.org/works" else None)
        resp.raise_for_status()
        data = resp.json()

        for work in data.get("results", []):
            if len(results) >= max_results:
                break
            results.append(parse_work(work))

        url = data.get("meta", {}).get("next_cursor")
        if url:
            url = f"https://api.openalex.org/works?cursor={url}" if isinstance(url, str) else url
        else:
            break

        time.sleep(0.1)  # Rate limiting courtesy

    return results


def save_results(results: list[dict], output_dir: str, topic_name: str) -> str:
    """Save search results to JSON file."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = topic_name.replace(" ", "_").replace("/", "_")
    path = os.path.join(output_dir, f"search_{safe_topic}_{timestamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return path


def main():
    parser = argparse.ArgumentParser(description="Search OpenAlex for papers")
    parser.add_argument("--config", required=True, help="Path to search_config.yaml")
    parser.add_argument("--topic", required=True, help="Topic name from config")
    parser.add_argument("--output-dir", default="output", help="Output directory")
    args = parser.parse_args()

    config = load_config(args.config)

    topic_config = None
    for t in config.get("topics", []):
        if t["name"] == args.topic:
            topic_config = t
            break

    if not topic_config:
        print(f"Error: topic '{args.topic}' not found in config", file=sys.stderr)
        sys.exit(1)

    results = search_openalex(
        keywords=topic_config["keywords"],
        years=topic_config.get("years", "2023-2026"),
        email=config["openalex"]["email"],
        max_results=config["openalex"].get("max_results_per_query", 50),
    )

    output_path = save_results(results, args.output_dir, args.topic)
    print(f"{len(results)} results -> {output_path}")


if __name__ == "__main__":
    main()
```

**Step 5: 运行测试**

```powershell
pytest tests/test_search_openalex.py -v
```
预期: 全部 PASS

**Step 6: 手动验证真实 API 调用**

```powershell
python scripts/search_openalex.py --config config/search_config.yaml --topic "涡轮冷却"
```
预期: 输出 `N results -> output/search_涡轮冷却_...json`

**Step 7: 提交**

```bash
git add scripts/search_openalex.py tests/test_search_openalex.py
git commit -m "feat: add OpenAlex search with keyword query and result parsing"
```

---

### Task 3: compare_library.py — Zotero 库对比去重

**Files:**
- Create: `scripts/compare_library.py`
- Create: `tests/test_compare_library.py`

**依赖**: 需要一个 Zotero 库导出文件（CSV 格式，至少含 title, doi 列）。在 Task 8 提供导出说明。

**Step 1: 写测试**

```python
# tests/test_compare_library.py
import pytest
from scripts.compare_library import normalize_title, check_duplicate, compare_with_library

def test_normalize_title_removes_punctuation_and_case():
    assert normalize_title("Film Cooling in Turbines!") == "filmcoolinginturbines"
    assert normalize_title("Heat Transfer: A Review") == "heattransferareview"

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

def test_compare_with_library_removes_duplicates():
    library = [{"title": "Existing Paper", "doi": "10.1234/abcd"}]
    candidates = [
        {"title": "Existing Paper", "doi": "10.1234/abcd", "openalex_id": "W1"},
        {"title": "New Paper", "doi": "10.5678/efgh", "openalex_id": "W2"},
    ]
    filtered = compare_with_library(candidates, library)
    assert len(filtered) == 1
    assert filtered[0]["openalex_id"] == "W2"
```

**Step 2: 运行测试验证失败**

```powershell
pytest tests/test_compare_library.py -v
```

**Step 3: 实现 compare_library.py**

```python
"""Zotero 库对比去重模块."""

import argparse
import csv
import json
import os
import re
import sys


def normalize_title(title: str) -> str:
    """Normalize title for comparison: lowercase, remove non-alphanumeric."""
    return re.sub(r"[^a-z0-9]", "", title.lower())


def check_duplicate(candidate: dict, library: list[dict]) -> tuple[bool, str | None]:
    """Check if a candidate paper already exists in library."""
    cand_doi = (candidate.get("doi") or "").lower()
    cand_title = normalize_title(candidate.get("title", ""))

    for existing in library:
        # DOI exact match
        existing_doi = (existing.get("doi") or "").lower()
        if cand_doi and existing_doi and cand_doi == existing_doi:
            return True, "doi_match"

        # Title exact match (normalized)
        existing_title = normalize_title(existing.get("title", ""))
        if cand_title and existing_title and cand_title == existing_title:
            return True, "title_match"

    return False, None


def compare_with_library(
    candidates: list[dict], library: list[dict]
) -> list[dict]:
    """Filter candidates, removing those already in library."""
    filtered = []
    for c in candidates:
        is_dup, _ = check_duplicate(c, library)
        if not is_dup:
            filtered.append(c)
    return filtered


def load_library_csv(path: str) -> list[dict]:
    """Load Zotero library from CSV export file."""
    papers = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            papers.append(row)
    return papers


def main():
    parser = argparse.ArgumentParser(
        description="Compare search results with Zotero library"
    )
    parser.add_argument("--input", required=True, help="Search results JSON")
    parser.add_argument("--library", required=True, help="Zotero library CSV")
    parser.add_argument("--output", help="Output file path (default: stdout)")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    library = load_library_csv(args.library)
    filtered = compare_with_library(candidates, library)

    removed = len(candidates) - len(filtered)
    print(f"Removed {removed} duplicates, {len(filtered)} new papers remain", file=sys.stderr)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(filtered, f, ensure_ascii=False, indent=2)
        print(f"Saved to {args.output}")
    else:
        print(json.dumps(filtered, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

**Step 4: 运行测试**

```powershell
pytest tests/test_compare_library.py -v
```
预期: 全部 PASS

**Step 5: 提交**

```powershell
git add scripts/compare_library.py tests/test_compare_library.py
git commit -m "feat: add Zotero library dedup via DOI/title comparison"
```

---

### Task 4: score_papers.py — 多维度打分排序

**Files:**
- Create: `scripts/score_papers.py`
- Create: `tests/test_score_papers.py`

**Step 1: 写测试**

```python
# tests/test_score_papers.py
import pytest
from scripts.score_papers import (
    score_relevance,
    score_quality,
    score_recency,
    score_papers,
)

def test_score_relevance_full_match():
    paper = {"title": "Turbine cooling with film holes", "abstract": ""}
    keywords = ["turbine cooling", "film cooling"]
    score = score_relevance(paper, keywords)
    assert score > 0

def test_score_relevance_no_match():
    paper = {"title": "Astrophysics and dark matter", "abstract": ""}
    keywords = ["turbine cooling"]
    score = score_relevance(paper, keywords)
    assert score == 0

def test_score_quality_zero_citations():
    assert score_quality({"cited_by_count": 0}) == 0

def test_score_quality_high_citations():
    score = score_quality({"cited_by_count": 100})
    assert score == pytest.approx(100.0)

def test_score_recency_current_year():
    assert score_recency({"year": 2026}, current_year=2026) == 100

def test_score_recency_old():
    assert score_recency({"year": 2015}, current_year=2026) < 50

def test_score_papers_ranks_and_scores():
    papers = [
        {"title": "Hot topic turbine cooling", "cited_by_count": 50, "year": 2025, "openalex_id": "W1"},
        {"title": "Unrelated topic", "cited_by_count": 0, "year": 2018, "openalex_id": "W2"},
    ]
    keywords = ["turbine cooling"]
    weights = {"relevance_weight": 0.40, "quality_weight": 0.20, "novelty_weight": 0.25, "recency_weight": 0.15}
    # novelty_scores maps openalex_id to novelty score
    novelty = {"W1": 80, "W2": 50}

    result = score_papers(papers, keywords, weights, novelty)
    assert result[0]["openalex_id"] == "W1"  # Higher score first
    assert "scores" in result[0]
    assert "composite" in result[0]["scores"]
```

**Step 2: 运行测试验证失败**

```powershell
pytest tests/test_score_papers.py -v
```

**Step 3: 实现 score_papers.py**

```python
"""多维度论文打分排序模块."""

import argparse
import json
import math


def score_relevance(paper: dict, keywords: list[str]) -> float:
    """Score relevance based on keyword presence in title and abstract."""
    text = (
        paper.get("title", "") + " " + paper.get("abstract", "")
    ).lower()
    matches = sum(1 for kw in keywords if kw.lower() in text)
    return (matches / len(keywords)) * 100 if keywords else 0


def score_quality(paper: dict) -> float:
    """Score quality based on citation count (log scale)."""
    citations = paper.get("cited_by_count", 0) or 0
    if citations == 0:
        return 0
    return min(math.log10(citations) * 50, 100)


def score_recency(paper: dict, current_year: int = 2026) -> float:
    """Score recency based on publication year decay."""
    year = paper.get("year") or current_year
    age = current_year - year
    if age <= 1:
        return 100
    elif age <= 3:
        return 75
    elif age <= 5:
        return 50
    else:
        return 25


def score_papers(
    papers: list[dict],
    keywords: list[str],
    weights: dict,
    novelty_scores: dict[str, float],
) -> list[dict]:
    """Calculate composite scores and return ranked list."""
    rw = weights.get("relevance_weight", 0.40)
    qw = weights.get("quality_weight", 0.20)
    nw = weights.get("novelty_weight", 0.25)
    tw = weights.get("recency_weight", 0.15)

    for paper in papers:
        rel = score_relevance(paper, keywords)
        qual = score_quality(paper)
        rec = score_recency(paper)
        nov = novelty_scores.get(paper.get("openalex_id", ""), 50)

        composite = rel * rw + qual * qw + nov * nw + rec * tw

        paper["scores"] = {
            "relevance": round(rel, 1),
            "quality": round(qual, 1),
            "novelty": round(nov, 1),
            "recency": round(rec, 1),
            "composite": round(composite, 1),
        }

    papers.sort(key=lambda p: p["scores"]["composite"], reverse=True)
    return papers


def main():
    parser = argparse.ArgumentParser(description="Score and rank papers")
    parser.add_argument("--input", required=True, help="Filtered results JSON")
    parser.add_argument("--config", required=True, help="search_config.yaml")
    parser.add_argument("--topic", required=True, help="Topic name")
    parser.add_argument("--output", help="Output file (default: stdout)")
    args = parser.parse_args()

    import yaml

    with open(args.input, "r", encoding="utf-8") as f:
        papers = json.load(f)

    with open(args.config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    topic_config = next(
        (t for t in config.get("topics", []) if t["name"] == args.topic), None
    )
    if not topic_config:
        print(f"Error: topic '{args.topic}' not found")
        return

    weights = config.get("scoring", {})
    # novelty defaults to 50 when no novelty data available
    novelty = {}

    scored = score_papers(papers, topic_config["keywords"], weights, novelty)
    top_n = config["scoring"].get("top_n_candidates", 10)
    top = scored[:top_n]

    output = json.dumps(top, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Saved {len(top)} scored papers to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
```

**Step 4: 运行测试**

```powershell
pytest tests/test_score_papers.py -v
```
预期: 全部 PASS

**Step 5: 提交**

```bash
git add scripts/score_papers.py tests/test_score_papers.py
git commit -m "feat: add multi-dimensional paper scoring (relevance, quality, novelty, recency)"
```

---

### Task 5: monitor.py — 每周定时任务入口

**Files:**
- Create: `scripts/monitor.py`
- Create: `tests/test_monitor.py`

**Step 1: 写测试**

```python
# tests/test_monitor.py
import pytest
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

def test_get_week_label():
    import datetime
    # 2026-05-07 is a Thursday, ISO week 19
    label = get_week_label(datetime.date(2026, 5, 7))
    assert label == "2026-W19"

def test_generate_report_structure():
    topic_name = "涡轮冷却"
    scored = [
        {
            "title": "Paper A",
            "authors": ["Zhang"],
            "year": 2025,
            "doi": "10.1234/a",
            "source": "J. Turbo",
            "cited_by_count": 30,
            "scores": {"composite": 87, "relevance": 90, "quality": 70, "novelty": 80, "recency": 90},
        },
        {
            "title": "Paper B",
            "authors": ["Li"],
            "year": 2024,
            "doi": "10.1234/b",
            "source": "ASME",
            "cited_by_count": 5,
            "scores": {"composite": 62, "relevance": 60, "quality": 30, "novelty": 50, "recency": 75},
        },
    ]
    report = generate_report(topic_name, scored, new_count=8, pushed_count=4)
    assert "涡轮冷却" in report
    assert "Paper A" in report
    assert "87" in report or "87分" in report
    assert "Paper B" in report
    assert "## 阅读清单" in report or "高优先级" in report
```

**Step 2: 运行测试验证失败**

```powershell
pytest tests/test_monitor.py -v
```

**Step 3: 实现 monitor.py**

```python
"""每周文献监控入口模块."""

import argparse
import datetime
import json
import os
import sys
from typing import Optional

import yaml

from search_openalex import search_openalex
from compare_library import compare_with_library, load_library_csv
from score_papers import score_papers


def get_monitored_topics(config: dict) -> list[dict]:
    """Extract topics with monitor: true."""
    return [t for t in config.get("topics", []) if t.get("monitor", False)]


def get_week_label(date: Optional[datetime.date] = None) -> str:
    """Return ISO week label like '2026-W19'."""
    if date is None:
        date = datetime.date.today()
    iso = date.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def generate_report(
    topic_name: str,
    scored: list[dict],
    new_count: int = 0,
    pushed_count: int = 0,
) -> str:
    """Generate a markdown report section for one topic."""
    high = [p for p in scored if p["scores"]["composite"] >= 75]
    mid = [p for p in scored if 60 <= p["scores"]["composite"] < 75]
    low = [p for p in scored if p["scores"]["composite"] < 60]

    lines = []
    lines.append(f"### {topic_name}")
    lines.append(f"")
    lines.append(f"| 新增 | 筛选推送 | 本次推送 |")
    lines.append(f"|------|----------|----------|")
    lines.append(f"| {new_count} | {pushed_count} | {len(scored)} |")
    lines.append(f"")

    if high:
        lines.append("#### 🔴 高优先级")
        lines.append("")
        for p in high:
            lines.append(
                f"- {p['title']} — {p['scores']['composite']}分, "
                f"{p.get('source', '?')}, {p.get('year', '?')}"
            )
        lines.append("")

    if mid:
        lines.append("#### 🟡 中优先级")
        lines.append("")
        for p in mid:
            lines.append(
                f"- {p['title']} — {p['scores']['composite']}分, "
                f"{p.get('source', '?')}, {p.get('year', '?')}"
            )
        lines.append("")

    if low:
        lines.append("#### ⚪ 待定")
        lines.append("")
        for p in low:
            lines.append(
                f"- {p['title']} — {p['scores']['composite']}分, "
                f"{p.get('source', '?')}, {p.get('year', '?')}"
            )
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Weekly literature monitor")
    parser.add_argument(
        "--config", default="config/search_config.yaml", help="Config file path"
    )
    parser.add_argument(
        "--library", default="config/zotero_library.csv", help="Zotero library CSV"
    )
    parser.add_argument(
        "--output-dir", default="output", help="Output directory for reports"
    )
    args = parser.parse_args()

    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        args.config,
    )
    library_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        args.library,
    )
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        args.output_dir,
    )

    # Load config
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    topics = get_monitored_topics(config)
    if not topics:
        print("No monitored topics found. Set monitor: true in config.")
        return

    # Load library
    library = []
    if os.path.exists(library_path):
        library = load_library_csv(library_path)
        print(f"Loaded {len(library)} papers from library")
    else:
        print(f"Warning: library file not found at {library_path}")

    email = config["openalex"]["email"]
    weights = config.get("scoring", {})
    week_label = get_week_label()

    report_sections = []
    report_sections.append(f"## 文献监控")
    report_sections.append("")

    for topic in topics:
        print(f"Searching: {topic['name']}...")
        results = search_openalex(
            keywords=topic["keywords"],
            years=topic.get("years", "2023-2026"),
            email=email,
            max_results=config["openalex"].get("max_results_per_query", 50),
        )

        new_count = len(results)
        filtered = compare_with_library(results, library)
        novelty_scores = {}  # novelty computed during comparison when library available

        scored = score_papers(filtered, topic["keywords"], weights, novelty_scores)
        top_n = config["scoring"].get("top_n_candidates", 10)
        top = scored[:top_n]

        # Save detailed results for Claude to read later
        detail_path = os.path.join(
            output_dir, f"monitor_{topic['name'].replace(' ', '_')}_{week_label}.json"
        )
        os.makedirs(output_dir, exist_ok=True)
        with open(detail_path, "w", encoding="utf-8") as f:
            json.dump(top, f, ensure_ascii=False, indent=2)

        report_sections.append(
            generate_report(topic["name"], top, new_count, len(filtered))
        )
        report_sections.append(f"_详细数据: {detail_path}_")
        report_sections.append("")

    # Write report
    report_path = os.path.join(output_dir, f"weekly_report_{week_label}.md")
    os.makedirs(output_dir, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_sections))

    print(f"Report saved to {report_path}")


if __name__ == "__main__":
    main()
```

**Step 4: 运行测试**

```powershell
pytest tests/test_monitor.py -v
```
预期: 全部 PASS

**Step 5: 提交**

```bash
git add scripts/monitor.py tests/test_monitor.py
git commit -m "feat: add weekly monitor orchestrating search+compare+score pipeline"
```

---

### Task 6: CLAUDE.md — Skill 指令文件

**Files:**
- Create: `CLAUDE.md`

**Step 1: 编写 CLAUDE.md**

内容包含：
- Skill 的触发方式（用户说"搜索文献"、"文献监控"等）
- 交互式搜索流程（调用 Python 脚本 → 展示结果 → 审批 → MCP 入库）
- 审批后写 Obsidian 笔记的模板
- 读取周报的流程

**Step 2: 提交**

```bash
git add CLAUDE.md
git commit -m "feat: add Claude Skill instructions for literature workflow"
```

---

### Task 7: 配置与定时任务

**Step 1: 更新 search_config.yaml 为真实配置**

- 填入真实 OpenAlex email
- 确认关键词和研究课题
- 设置监控开关

**Step 2: Zotero 库导出**

在 Zotero 中：
1. 全选文献 → 文件 → 导出条目
2. 格式: CSV
3. 保存为 `config/zotero_library.csv`

**Step 3: 配置 Windows 任务计划程序**

```powershell
$action = New-ScheduledTaskAction -Execute "python" -Argument "D:\Documents\AIProjects\PaperAssistant\scripts\monitor.py"
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 9am
Register-ScheduledTask -TaskName "PaperAssistantMonitor" -Action $action -Trigger $trigger -Description "每周文献监控"
```

**Step 4: 提交**

```bash
git add config/search_config.yaml config/zotero_library.csv
git commit -m "chore: configure real search topics and Zotero library export"
```

---

### Task 8: 端到端验证

**Step 1: 交互式搜索验证**

在 Claude Code 中触发搜索，确认：
- Python 脚本正确执行
- 结果正确解析展示
- Zotero MCP 入库正常
- Obsidian 笔记格式正确

**Step 2: 监控模式验证**

```powershell
python scripts/monitor.py
```
确认生成 `output/weekly_report_*.md` 且内容完整。

**Step 3: 修复发现的问题并提交**
