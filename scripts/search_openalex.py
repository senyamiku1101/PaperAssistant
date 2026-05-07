"""OpenAlex API literature search module."""

import argparse
import json
import os
import sys
import time
from datetime import datetime

import requests
import yaml


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_query(keywords: list[str], years: str) -> dict:
    search_terms = " OR ".join(f'"{kw}"' for kw in keywords)
    return {
        "search": search_terms,
        "filter": f"publication_year:{years}",
        "sort": "cited_by_count:desc",
        "per_page": 50,
    }


def parse_work(work: dict) -> dict:
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
        "abstract": "",
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
    params = build_query(keywords, years)
    params["per_page"] = max_results
    params["mailto"] = email

    url = "https://api.openalex.org/works"
    results = []

    while url and len(results) < max_results:
        resp = requests.get(
            url,
            params=params if url == "https://api.openalex.org/works" else None,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        for work in data.get("results", []):
            if len(results) >= max_results:
                break
            results.append(parse_work(work))

        next_cursor = data.get("meta", {}).get("next_cursor")
        if next_cursor:
            url = f"https://api.openalex.org/works?cursor={next_cursor}"
        else:
            break

        time.sleep(0.1)

    return results


def save_results(results: list[dict], output_dir: str, topic_name: str) -> str:
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
