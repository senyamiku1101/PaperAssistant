"""OpenAlex API literature search module."""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

import requests
import yaml


def load_config(config_path: str) -> dict:
    """Load YAML configuration from a file path."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_config(config: dict) -> bool:
    """Validate configuration structure and print errors to stderr.

    Returns True if the config is valid, False otherwise.
    """
    valid = True

    # Check openalex.email
    email = config.get("openalex", {}).get("email")
    if not email:
        print("Error: config missing 'openalex.email'", file=sys.stderr)
        valid = False

    # Check topics list
    topics = config.get("topics")
    if not topics or not isinstance(topics, list) or len(topics) == 0:
        print("Error: config missing non-empty 'topics' list", file=sys.stderr)
        valid = False
    else:
        for i, t in enumerate(topics):
            if not isinstance(t, dict):
                print(f"Error: topics[{i}] is not a dict", file=sys.stderr)
                valid = False
                continue
            if not t.get("name"):
                print(f"Error: topics[{i}] missing 'name'", file=sys.stderr)
                valid = False
            if not t.get("keywords"):
                print(f"Error: topics[{i}] missing 'keywords'", file=sys.stderr)
                valid = False

    return valid


# Aerospace-related subfield display names (case-insensitive match)
AEROSPACE_KEYWORDS = [
    "aerospace", "aeronautic", "aviation", "aeroacoustic",
    "turbomachinery", "propulsion", "aerodynamic",
]


def build_query(keywords: list[str], years: str) -> dict:
    """Build OpenAlex API query params from keywords and year range.

    Subfield filtering is done post-hoc via filter_papers() so that
    aerospace-related papers outside subfield 2202 are not lost.
    """
    search_terms = " OR ".join(f'"{kw}"' for kw in keywords)
    return {
        "search": search_terms,
        "filter": f"publication_year:{years}",
        "sort": "cited_by_count:desc",
        "per_page": 50,
    }


def reconstruct_abstract(inverted_index):
    """Reconstruct abstract text from OpenAlex inverted_index format."""
    if not inverted_index or not isinstance(inverted_index, dict):
        return ""
    positioned = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            positioned[pos] = word
    return " ".join(positioned[i] for i in sorted(positioned))


def parse_work(work: dict) -> dict:
    """Parse a single OpenAlex work record into a flat dict."""
    doi = work.get("doi", "")
    if doi:
        doi = doi.replace("https://doi.org/", "")

    primary_topic = work.get("primary_topic") or {}
    subfield = primary_topic.get("subfield") or {}

    return {
        "title": work.get("title", ""),
        "doi": doi or None,
        "authors": [
            (a.get("author") or {}).get("display_name", "")
            for a in work.get("authorships", [])
        ],
        "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
        "year": work.get("publication_year"),
        "cited_by_count": work.get("cited_by_count", 0),
        "source": ((work.get("primary_location") or {}).get("source") or {}).get("display_name", ""),
        "type": work.get("type", ""),
        "openalex_id": work.get("id", ""),
        "url": f"https://openalex.org/{work.get('id', '').split('/')[-1]}" if work.get("id") else "",
        "subfield_id": subfield.get("id") or "",
        "subfield_name": subfield.get("display_name", ""),
    }


def is_aerospace_paper(paper: dict, target_subfield_id: str | None) -> bool:
    """Check if a paper is aerospace-related.

    Returns True if:
    - subfield_id matches the target (e.g. "2202")
    - subfield_name contains an aerospace-related keyword
    """
    subfield_id = paper.get("subfield_id", "")
    subfield_name = paper.get("subfield_name", "").lower()

    if target_subfield_id and subfield_id == target_subfield_id:
        return True

    for kw in AEROSPACE_KEYWORDS:
        if kw in subfield_name:
            return True

    return False


def filter_papers(papers: list[dict], subfield_id: str | None) -> tuple[list[dict], list[dict]]:
    """Split papers into aerospace and non-aerospace groups.

    Returns (aerospace_papers, excluded_papers).
    """
    if not subfield_id:
        return papers, []
    matched = [p for p in papers if is_aerospace_paper(p, subfield_id)]
    excluded = [p for p in papers if not is_aerospace_paper(p, subfield_id)]
    return matched, excluded


def search_openalex(
    keywords: list[str],
    years: str,
    email: str,
    max_results: int = 50,
    subfield_id: str | None = None,
) -> list[dict]:
    """Search OpenAlex API and return parsed work records.

    Handles pagination via cursor and retries failed requests up to
    2 times with a 1-second delay. On unrecoverable failure, returns
    partial results collected so far.

    If subfield_id is provided, results are post-filtered to only
    include aerospace-related papers (matching subfield_id or
    aerospace keywords in the subfield display name).
    """
    params = build_query(keywords, years)
    params["per_page"] = min(max_results, 200)
    params["mailto"] = email

    base_url = "https://api.openalex.org/works"
    url = base_url
    results: list[dict] = []
    is_first_page = True
    max_retries = 2

    while url and len(results) < max_results:
        for attempt in range(max_retries + 1):
            try:
                if is_first_page:
                    resp = requests.get(url, params=params, timeout=30)
                else:
                    resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                break
            except requests.RequestException as e:
                if attempt < max_retries:
                    print(
                        f"Request failed (attempt {attempt + 1}/{max_retries + 1}): {e}",
                        file=sys.stderr,
                    )
                    time.sleep(1)
                else:
                    print(
                        f"Request failed after {max_retries + 1} attempts: {e}",
                        file=sys.stderr,
                    )
                    return results
            except json.JSONDecodeError as e:
                print(
                    f"JSON decode error after {attempt + 1} attempt(s): {e}",
                    file=sys.stderr,
                )
                return results

        is_first_page = False

        for work in data.get("results", []):
            if len(results) >= max_results:
                break
            results.append(parse_work(work))

        next_cursor = data.get("meta", {}).get("next_cursor")
        if next_cursor:
            url = f"{base_url}?cursor={next_cursor}"
        else:
            break

        time.sleep(0.1)

    if subfield_id:
        results, excluded = filter_papers(results, subfield_id)
        if excluded:
            print(
                f"Post-filter: excluded {len(excluded)} non-aerospace papers "
                f"(e.g. {excluded[0].get('subfield_name', '?')})",
                file=sys.stderr,
            )

    return results


def save_results(results: list[dict], output_dir: str, topic_name: str) -> str:
    """Save search results to a timestamped JSON file.

    Returns the path of the written file.
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = re.sub(r'[<>:"/\\|?*]', '_', topic_name)
    safe_topic = safe_topic.replace(" ", "_")
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

    if not validate_config(config):
        sys.exit(1)

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
        subfield_id=config["openalex"].get("subfield_id"),
    )

    output_path = save_results(results, args.output_dir, args.topic)
    print(f"{len(results)} results -> {output_path}")


if __name__ == "__main__":
    main()
