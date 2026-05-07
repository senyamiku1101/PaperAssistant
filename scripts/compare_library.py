"""Zotero library comparison and deduplication module."""

import argparse
import csv
import json
import os
import re
import sys


def normalize_title(title: str) -> str:
    """Normalize title for comparison: lowercase, strip non-alphanumeric."""
    if not title:
        return ""
    return re.sub(r"[^a-z0-9]", "", title.lower())


def check_duplicate(candidate: dict, library: list[dict]) -> tuple[bool, str | None]:
    """Check if candidate exists in library by DOI or normalized title."""
    cand_doi = (candidate.get("doi") or "").strip().lower()
    cand_title = normalize_title(candidate.get("title", ""))

    for existing in library:
        # DOI exact match (case-insensitive)
        existing_doi = (existing.get("doi") or "").strip().lower()
        if cand_doi and existing_doi and cand_doi == existing_doi:
            return True, "doi_match"

        # Title match after normalization
        existing_title = normalize_title(existing.get("title", ""))
        if cand_title and existing_title and cand_title == existing_title:
            return True, "title_match"

    return False, None


def compare_with_library(candidates: list[dict], library: list[dict]) -> list[dict]:
    """Filter candidates, removing those already present in the library."""
    filtered = []
    for c in candidates:
        is_dup, _ = check_duplicate(c, library)
        if not is_dup:
            filtered.append(c)
    return filtered


def load_library_csv(path: str) -> list[dict]:
    """Load Zotero library exported as CSV."""
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def main():
    parser = argparse.ArgumentParser(
        description="Compare search results with Zotero library"
    )
    parser.add_argument("--input", required=True, help="Search results JSON file")
    parser.add_argument("--library", required=True, help="Zotero library CSV file")
    parser.add_argument("--output", help="Output JSON file (default: print to stdout)")
    args = parser.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            candidates = json.load(f)
    except FileNotFoundError:
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in input file: {e}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(candidates, list):
        print(
            "Error: input JSON must contain a list of candidate papers",
            file=sys.stderr,
        )
        sys.exit(1)

    if not os.path.exists(args.library):
        print(
            f"Warning: library file '{args.library}' not found, skipping dedup",
            file=sys.stderr,
        )
        filtered = candidates
    else:
        library = load_library_csv(args.library)
        filtered = compare_with_library(candidates, library)
        removed = len(candidates) - len(filtered)
        print(
            f"Removed {removed} duplicates, {len(filtered)} new papers remain",
            file=sys.stderr,
        )

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(filtered, f, ensure_ascii=False, indent=2)
        print(f"Saved to {args.output}", file=sys.stderr)
    else:
        print(json.dumps(filtered, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
