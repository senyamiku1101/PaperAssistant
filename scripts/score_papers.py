"""Multi-dimensional paper scoring and ranking module."""

import argparse
import json
import math
import sys

import yaml


def score_relevance(paper: dict, keywords: list[str]) -> float:
    """Score based on keyword presence in title and abstract (0-100)."""
    if not keywords:
        return 0.0
    text = (paper.get("title", "") + " " + paper.get("abstract", "")).lower()
    matches = sum(1 for kw in keywords if kw.lower() in text)
    return (matches / len(keywords)) * 100


def score_quality(paper: dict) -> float:
    """Score based on citation count using log scale (0-100)."""
    citations = paper.get("cited_by_count") or 0
    if citations <= 0:
        return 0.0
    return min(math.log10(citations) * 50, 100)


def score_recency(paper: dict, current_year: int = 2026) -> float:
    """Score based on publication year decay."""
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
    """Calculate composite scores and return ranked list (descending)."""
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
    parser.add_argument("--input", required=True, help="Filtered search results JSON")
    parser.add_argument("--config", required=True, help="search_config.yaml path")
    parser.add_argument("--topic", required=True, help="Topic name from config")
    parser.add_argument("--output", help="Output JSON file (default: stdout)")
    args = parser.parse_args()

    # Load input papers
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            papers = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error: cannot read input '{args.input}': {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(papers, list):
        print("Error: input must be a JSON array", file=sys.stderr)
        sys.exit(1)

    # Load config
    try:
        with open(args.config, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError) as e:
        print(f"Error: cannot read config '{args.config}': {e}", file=sys.stderr)
        sys.exit(1)

    # Find topic
    topic_config = None
    for t in config.get("topics", []):
        if t.get("name") == args.topic:
            topic_config = t
            break

    if not topic_config:
        print(f"Error: topic '{args.topic}' not found in config", file=sys.stderr)
        sys.exit(1)

    weights = config.get("scoring", {})
    keywords = topic_config.get("keywords", [])
    top_n = config.get("scoring", {}).get("top_n_candidates", 10)

    # Score (novelty from comparison step not available here, use defaults)
    novelty = {}
    scored = score_papers(papers, keywords, weights, novelty)
    top = scored[:top_n]

    output = json.dumps(top, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Saved {len(top)} scored papers to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
