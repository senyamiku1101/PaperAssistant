"""Weekly literature monitor — orchestrates search + compare + score pipeline."""

import argparse
import datetime
import json
import os
import sys

# Allow importing sibling modules within scripts/ regardless of launch method
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml

from search_openalex import search_openalex
from compare_library import compare_with_library, load_library_csv
from score_papers import score_papers


def get_monitored_topics(config: dict) -> list[dict]:
    """Extract topics with monitor: true from config."""
    return [t for t in config.get("topics", []) if t.get("monitor", False)]


def get_week_label(date: datetime.date | None = None) -> str:
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

    lines = [f"### {topic_name}", ""]
    lines.append("| 新增 | 筛选推送 | 本次推送 |")
    lines.append("|------|----------|----------|")
    lines.append(f"| {new_count} | {pushed_count} | {len(scored)} |")
    lines.append("")

    if high:
        lines.append("#### 高优先级")
        lines.append("")
        for p in high:
            src = p.get("source", "?")
            yr = p.get("year", "?")
            lines.append(f"- {p['title']} — {p['scores']['composite']}分, {src}, {yr}")
        lines.append("")

    if mid:
        lines.append("#### 中优先级")
        lines.append("")
        for p in mid:
            src = p.get("source", "?")
            yr = p.get("year", "?")
            lines.append(f"- {p['title']} — {p['scores']['composite']}分, {src}, {yr}")
        lines.append("")

    if low:
        lines.append("#### 待定")
        lines.append("")
        for p in low:
            src = p.get("source", "?")
            yr = p.get("year", "?")
            lines.append(f"- {p['title']} — {p['scores']['composite']}分, {src}, {yr}")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Weekly literature monitor")
    parser.add_argument("--config", default="config/search_config.yaml",
                        help="Path to search_config.yaml")
    parser.add_argument("--library", default="config/zotero_library.csv",
                        help="Path to Zotero library CSV")
    parser.add_argument("--output-dir", default="output",
                        help="Directory for report output")
    args = parser.parse_args()

    # Resolve paths relative to project root (parent of scripts/)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_root, args.config)
    library_path = os.path.join(project_root, args.library)
    output_dir = os.path.join(project_root, args.output_dir)

    # Load config
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError) as e:
        print(f"Error: cannot read config '{config_path}': {e}", file=sys.stderr)
        sys.exit(1)

    topics = get_monitored_topics(config)
    if not topics:
        print("No monitored topics found. Set monitor: true in config to enable.")
        return

    # Load library
    library = []
    if os.path.exists(library_path):
        try:
            library = load_library_csv(library_path)
            print(f"Loaded {len(library)} papers from library")
        except Exception as e:
            print(f"Warning: failed to load library: {e}", file=sys.stderr)
    else:
        print(f"Warning: library file not found at {library_path}", file=sys.stderr)

    email = config.get("openalex", {}).get("email", "")
    if not email or email == "your-email@example.com":
        print("Warning: OpenAlex email not configured, using default", file=sys.stderr)

    weights = config.get("scoring", {})
    max_results = config.get("openalex", {}).get("max_results_per_query", 50)
    top_n = config.get("scoring", {}).get("top_n_candidates", 10)
    week_label = get_week_label()

    os.makedirs(output_dir, exist_ok=True)

    report_sections = ["# 文献监控报告", f"_生成日期: {week_label}_", ""]

    for topic in topics:
        print(f"\n=== Processing: {topic['name']} ===")
        years = topic.get("years", "2023-2026")
        keywords = topic.get("keywords", [])

        # Step 1: Search
        print(f"  Searching OpenAlex...")
        results = search_openalex(
            keywords=keywords,
            years=years,
            email=email,
            max_results=max_results,
            subfield_id=config.get("openalex", {}).get("subfield_id"),
        )

        new_count = len(results)

        # Step 2: Compare with library
        filtered = compare_with_library(results, library)
        print(f"  Found {new_count}, {len(filtered)} new after dedup")

        # Step 3: Score
        novelty_scores = {}
        scored = score_papers(filtered, keywords, weights, novelty_scores)
        top = scored[:top_n]

        # Save detailed results for Claude to use later
        safe_name = topic["name"].replace(" ", "_")
        detail_path = os.path.join(
            output_dir, f"monitor_{safe_name}_{week_label}.json"
        )
        with open(detail_path, "w", encoding="utf-8") as f:
            json.dump(top, f, ensure_ascii=False, indent=2)

        report_sections.append(
            generate_report(topic["name"], top, new_count, len(filtered))
        )
        report_sections.append(f"_详细数据: `{detail_path}`_")
        report_sections.append("")

    # Write report
    report_path = os.path.join(output_dir, f"weekly_report_{week_label}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_sections))

    print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    main()
