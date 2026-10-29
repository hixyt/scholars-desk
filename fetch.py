#!/usr/bin/env python3
"""
The Scholar's Desk - Step 1: Research Paper Fetcher
===================================================
A daily automation script that:
1. Fetches papers from the last few days (days_back in config.yaml) from the arXiv API
   for cs.AI, cs.CL, cs.HC, and cs.LG, page by page.
2. Fetches today's curated papers from the Hugging Face Daily Papers API.
3. Skips any paper already saved on an earlier day, so nothing repeats.
4. Deduplicates papers and filters them based on keywords in config.yaml.
5. Saves matching papers into data/YYYY-MM-DD/raw.json.

Why a window of several days and not just "yesterday"?
arXiv publishes new papers once a day (Sunday to Thursday evening, US time) and
nothing on Friday or Saturday. A paper submitted late in the day shows up a day
later, and weekend papers show up on Monday. Asking only for "yesterday" missed
those papers forever. So we look back a few days and remember what we have seen.

This script uses only free public APIs with no API keys required.
arXiv rate limit (>= 3 seconds per request) is strictly enforced.
"""

import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET

import requests
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("scholars-desk.fetch")

# HTTP headers complying with arXiv API policy
ARXIV_USER_AGENT = "TheScholarsDesk/1.0 (Daily AI Digest Bot; mailto:scholars-desk@users.noreply.github.com)"
DEFAULT_HEADERS = {"User-Agent": ARXIV_USER_AGENT}


def load_config(config_path: str = "config.yaml") -> dict:
    """Load and parse topic keywords and settings from config.yaml."""
    path = Path(config_path)
    if not path.exists():
        logger.warning(f"Config file not found at {config_path}. Using default configuration.")
        return {
            "topics": {
                "AI tools for non-programmers": ["no-code", "low-code", "non-programmer", "accessible AI"],
                "LLM agents for everyday work": ["llm agent", "ai agent", "productivity", "workflow automation"]
            },
            "settings": {
                "arxiv": {"categories": ["cs.AI", "cs.CL", "cs.HC", "cs.LG"], "max_results": 500, "rate_limit_seconds": 3.0},
                "huggingface": {"daily_papers_url": "https://huggingface.co/api/daily_papers"}
            }
        }

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # Extract topic -> keywords mapping
    topics_dict = {}
    for item in data.get("topics", []):
        if isinstance(item, dict):
            name = item.get("name", "General")
            keywords = [k.strip().lower() for k in item.get("keywords", []) if k.strip()]
            topics_dict[name] = keywords
        elif isinstance(item, str):
            topics_dict[item] = [item.strip().lower()]

    settings = data.get("settings", {})
    return {
        "topics": topics_dict,
        "settings": settings
    }


def normalize_arxiv_id(raw_id: str) -> str:
    """Extract standard arXiv ID without version suffix (e.g. '2401.12345v2' -> '2401.12345')."""
    if not raw_id:
        return ""
    # Extract pattern like 2401.12345 or math/0102003
    match = re.search(r"(\d{4}\.\d{4,5}|[a-zA-Z\-]+/\d{7})", raw_id)
    if match:
        return match.group(1)
    # Clean URL parts or version tags if regex didn't match
    clean_id = raw_id.split("/")[-1]
    clean_id = re.sub(r"v\d+$", "", clean_id)
    return clean_id.strip()


def normalize_title(title: str) -> str:
    """Normalize a title for fuzzy duplicate detection."""
    clean = re.sub(r"\s+", " ", title or "").strip().lower()
    # Remove non-alphanumeric characters
    clean = re.sub(r"[^a-z0-9 ]", "", clean)
    return clean


def parse_arxiv_entry(entry, ns: dict) -> dict:
    """Turn one <entry> from arXiv's XML reply into a clean paper dictionary."""
    raw_id = entry.find("atom:id", ns)
    raw_id_text = raw_id.text.strip() if raw_id is not None else ""
    clean_id = normalize_arxiv_id(raw_id_text)

    title_el = entry.find("atom:title", ns)
    title = " ".join(title_el.text.strip().split()) if title_el is not None else "Untitled"

    summary_el = entry.find("atom:summary", ns)
    abstract = " ".join(summary_el.text.strip().split()) if summary_el is not None else ""

    published_el = entry.find("atom:published", ns)
    published = published_el.text.strip() if published_el is not None else ""

    # Extract authors
    authors = []
    for author_el in entry.findall("atom:author", ns):
        name_el = author_el.find("atom:name", ns)
        if name_el is not None and name_el.text:
            authors.append(name_el.text.strip())

    # Extract categories
    cats = []
    for cat_el in entry.findall("atom:category", ns):
        term = cat_el.attrib.get("term")
        if term and term not in cats:
            cats.append(term)

    # Primary category
    prim_cat_el = entry.find("arxiv:primary_category", ns)
    primary_cat = prim_cat_el.attrib.get("term") if prim_cat_el is not None else (cats[0] if cats else "cs.AI")

    return {
        "id": clean_id,
        "title": title,
        "abstract": abstract,
        "authors": authors,
        "published": published,
        "url": f"https://arxiv.org/abs/{clean_id}" if clean_id else raw_id_text,
        "pdf_url": f"https://arxiv.org/pdf/{clean_id}.pdf" if clean_id else "",
        "categories": cats,
        "primary_category": primary_cat,
        "sources": ["arxiv"],
        "huggingface": None
    }


def fetch_arxiv_papers(start_date: datetime, end_date: datetime, categories: list,
                       max_results: int = 4000, page_size: int = 1000,
                       rate_limit_seconds: float = 3.0) -> list:
    """
    Fetch papers submitted to arXiv between start_date and end_date (both days included).
    arXiv sends results in pages, so we ask for one page at a time.
    Respects arXiv's mandatory >= 3.0s wait before every request.
    """
    start_str = start_date.strftime("%Y%m%d0000")
    end_str = end_date.strftime("%Y%m%d2359")

    cat_query = " OR ".join([f"cat:{cat}" for cat in categories])
    query = f"({cat_query}) AND submittedDate:[{start_str} TO {end_str}]"

    url = "http://export.arxiv.org/api/query"
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
        "opensearch": "http://a9.com/-/spec/opensearch/1.1/"
    }

    logger.info(f"Querying arXiv for {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} "
                f"across categories {categories}...")

    papers = []
    offset = 0              # how many papers we have already received
    retried_empty_page = False

    while offset < max_results:
        logger.info(f"Respecting arXiv rate limit (waiting {rate_limit_seconds}s before request)...")
        time.sleep(rate_limit_seconds)

        params = {
            "search_query": query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "start": offset,
            "max_results": min(page_size, max_results - offset)
        }
        try:
            response = requests.get(url, params=params, headers={"User-Agent": ARXIV_USER_AGENT}, timeout=60)
            response.raise_for_status()
            root = ET.fromstring(response.text)
        except Exception as e:
            logger.error(f"Error fetching from arXiv API (page starting at {offset}): {e}")
            break

        total_el = root.find("opensearch:totalResults", ns)
        total = int(total_el.text) if total_el is not None and total_el.text else 0
        entries = root.findall("atom:entry", ns)
        logger.info(f"arXiv page {offset // page_size + 1}: {len(entries)} papers (total available: {total}).")

        # arXiv sometimes sends an empty page by mistake. Try that page once more.
        if not entries and offset < total and not retried_empty_page:
            retried_empty_page = True
            continue
        if not entries:
            break

        for entry in entries:
            papers.append(parse_arxiv_entry(entry, ns))

        offset += len(entries)
        if offset >= total:
            break

    logger.info(f"arXiv returned {len(papers)} candidate papers in total.")
    return papers


def fetch_huggingface_papers(today_date: datetime, api_url: str = "https://huggingface.co/api/daily_papers") -> list:
    """Fetch today's curated papers from Hugging Face Daily Papers API."""
    date_str = today_date.strftime("%Y-%m-%d")
    logger.info(f"Querying Hugging Face Daily Papers API for {date_str}...")

    # First try fetching for the specific date, fallback to default endpoint
    papers_data = []
    try:
        url_with_date = f"{api_url}?date={date_str}"
        response = requests.get(url_with_date, headers=DEFAULT_HEADERS, timeout=20)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                papers_data = data
                logger.info(f"Hugging Face returned {len(papers_data)} papers for date {date_str}.")

        # If date parameter gave empty results, fetch default daily list
        if not papers_data:
            logger.info("Falling back to default Hugging Face daily papers endpoint...")
            response = requests.get(api_url, headers=DEFAULT_HEADERS, timeout=20)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                papers_data = data
                logger.info(f"Hugging Face default endpoint returned {len(papers_data)} papers.")
    except Exception as e:
        logger.error(f"Error fetching from Hugging Face Daily Papers API: {e}")
        return []

    papers = []
    for item in papers_data:
        p = item.get("paper", {})
        raw_id = p.get("id") or item.get("id") or ""
        clean_id = normalize_arxiv_id(raw_id)

        title = p.get("title") or item.get("title") or "Untitled"
        title = " ".join(title.strip().split())

        abstract = p.get("summary") or item.get("summary") or ""
        abstract = " ".join(abstract.strip().split())

        published = p.get("publishedAt") or item.get("publishedAt") or ""

        # Extract authors
        authors = []
        for author in p.get("authors", []):
            if isinstance(author, dict) and "name" in author:
                authors.append(author["name"])
            elif isinstance(author, str):
                authors.append(author)

        hf_metadata = {
            "upvotes": p.get("upvotes", 0),
            "num_comments": item.get("numComments", 0),
            "discussion_id": p.get("discussionId")
        }

        paper = {
            "id": clean_id,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "published": published,
            "url": f"https://arxiv.org/abs/{clean_id}" if clean_id else f"https://huggingface.co/papers/{raw_id}",
            "pdf_url": f"https://arxiv.org/pdf/{clean_id}.pdf" if clean_id else "",
            "categories": [],
            "primary_category": "cs.AI",
            "sources": ["huggingface"],
            "huggingface": hf_metadata
        }
        papers.append(paper)

    return papers


def match_topics(paper: dict, topics_dict: dict) -> tuple:
    """
    Check if a paper matches any keyword in the configured topics.
    Searches both title and abstract using whole-word boundary matching.
    Returns (matched_topics_list, matched_keywords_list).
    """
    text = f"{paper.get('title', '')} {paper.get('abstract', '')}".lower()

    matched_topics = []
    matched_keywords = []

    for topic_name, keywords in topics_dict.items():
        topic_matched_kws = []
        for kw in keywords:
            # Word boundary matching to avoid partial word false positives
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, text):
                topic_matched_kws.append(kw)

        if topic_matched_kws:
            matched_topics.append(topic_name)
            matched_keywords.extend(topic_matched_kws)

    # Deduplicate keywords preserving order
    unique_kws = list(dict.fromkeys(matched_keywords))
    return matched_topics, unique_kws


def load_seen_papers(output_root: str, today_str: str) -> tuple:
    """
    Collect the IDs and titles of every paper saved on an EARLIER day
    (data/<earlier date>/raw.json), so the same paper is never shown twice.
    Today's folder is ignored, so running the script again today gives the same result.
    """
    seen_ids = set()
    seen_titles = set()
    root = Path(output_root)
    if not root.exists():
        return seen_ids, seen_titles

    for raw_file in sorted(root.glob("*/raw.json")):
        if raw_file.parent.name >= today_str:
            continue  # skip today and any later folder
        try:
            with open(raw_file, "r", encoding="utf-8") as f:
                for p in json.load(f):
                    if p.get("id"):
                        seen_ids.add(p["id"])
                    norm = normalize_title(p.get("title", ""))
                    if norm:
                        seen_titles.add(norm)
        except Exception as e:
            logger.warning(f"Could not read {raw_file}: {e}")

    logger.info(f"Loaded {len(seen_ids)} paper IDs seen on earlier days.")
    return seen_ids, seen_titles


def remove_seen_papers(papers: list, seen_ids: set, seen_titles: set) -> list:
    """Keep only papers we have NOT saved on an earlier day."""
    fresh = []
    for p in papers:
        if p.get("id") in seen_ids:
            continue
        if normalize_title(p.get("title", "")) in seen_titles:
            continue
        fresh.append(p)
    return fresh


def deduplicate_and_filter_papers(papers_list: list, topics_dict: dict) -> list:
    """
    1. Filters papers that match at least one keyword in config.yaml.
    2. Deduplicates papers across arXiv and Hugging Face by normalized arXiv ID or title.
    3. Merges metadata (sources, upvotes, longer abstract).
    """
    matched_papers = []
    for paper in papers_list:
        matched_topics, matched_kws = match_topics(paper, topics_dict)
        if matched_topics:
            paper["matched_topics"] = matched_topics
            paper["matched_keywords"] = matched_kws
            matched_papers.append(paper)

    logger.info(f"Total papers matching configured topics: {len(matched_papers)} (before deduplication)")

    # Deduplicate by arXiv ID or normalized title
    deduped = {}
    title_to_id = {}

    for paper in matched_papers:
        paper_id = paper.get("id")
        norm_title = normalize_title(paper.get("title", ""))

        # Check if we already have this paper
        existing_key = None
        if paper_id and paper_id in deduped:
            existing_key = paper_id
        elif norm_title in title_to_id:
            existing_key = title_to_id[norm_title]

        if existing_key:
            # Merge existing paper with new paper
            existing = deduped[existing_key]
            for src in paper.get("sources", []):
                if src not in existing["sources"]:
                    existing["sources"].append(src)

            # Combine categories
            for cat in paper.get("categories", []):
                if cat not in existing["categories"]:
                    existing["categories"].append(cat)

            # Combine matched topics and keywords
            for topic in paper.get("matched_topics", []):
                if topic not in existing["matched_topics"]:
                    existing["matched_topics"].append(topic)
            for kw in paper.get("matched_keywords", []):
                if kw not in existing["matched_keywords"]:
                    existing["matched_keywords"].append(kw)

            # Keep the longer abstract (arXiv typically has complete abstracts)
            if len(paper.get("abstract", "")) > len(existing.get("abstract", "")):
                existing["abstract"] = paper["abstract"]

            # Merge HF metadata if present
            if paper.get("huggingface") and not existing.get("huggingface"):
                existing["huggingface"] = paper["huggingface"]
        else:
            key = paper_id if paper_id else norm_title
            deduped[key] = paper
            if norm_title:
                title_to_id[norm_title] = key

    final_list = list(deduped.values())
    logger.info(f"Final deduplicated papers count: {len(final_list)}")
    return final_list


def save_raw_papers(papers: list, date_str: str, output_root: str = "data") -> Path:
    """Save the final list of papers to data/YYYY-MM-DD/raw.json."""
    output_dir = Path(output_root) / date_str
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "raw.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(papers, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {len(papers)} papers to {output_file.resolve()}")
    return output_file


def main():
    parser = argparse.ArgumentParser(description="Fetch and filter daily AI papers for The Scholar's Desk.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml file.")
    parser.add_argument("--date", default=None, help="Digest execution date in YYYY-MM-DD format (defaults to UTC today).")
    parser.add_argument("--output-dir", default="data", help="Root directory for saving raw papers.")
    args = parser.parse_args()

    # Determine dates
    if args.date:
        today_date = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        today_date = datetime.now(timezone.utc)

    # 1. Load config
    config = load_config(args.config)
    topics = config["topics"]
    settings = config.get("settings", {})

    arxiv_settings = settings.get("arxiv", {})
    categories = arxiv_settings.get("categories", ["cs.AI", "cs.CL", "cs.HC", "cs.LG"])
    days_back = arxiv_settings.get("days_back", 4)
    max_results = arxiv_settings.get("max_results", 4000)
    page_size = arxiv_settings.get("page_size", 1000)
    rate_limit = arxiv_settings.get("rate_limit_seconds", 3.0)

    # arXiv window: the last few days up to today (see the note at the top of this file)
    window_start = today_date - timedelta(days=days_back)
    today_str = today_date.strftime("%Y-%m-%d")
    window_str = f"{window_start.strftime('%Y-%m-%d')} to {today_str}"

    print("=" * 70)
    print("  The Scholar's Desk - Daily Research Paper Fetcher")
    print(f"  Target Run Date  : {today_str} (UTC)")
    print(f"  arXiv Window     : {window_str}")
    print("=" * 70)

    hf_settings = settings.get("huggingface", {})
    hf_url = hf_settings.get("daily_papers_url", "https://huggingface.co/api/daily_papers")

    print("\n[Topics Configured]:")
    for name, kws in topics.items():
        print(f"  * {name} ({len(kws)} keywords)")

    # 2. Fetch from arXiv
    print("\n--- 1. Fetching from arXiv API ---")
    arxiv_papers = fetch_arxiv_papers(
        start_date=window_start,
        end_date=today_date,
        categories=categories,
        max_results=max_results,
        page_size=page_size,
        rate_limit_seconds=rate_limit
    )
    print(f"-> Fetched {len(arxiv_papers)} papers from arXiv.")

    # 3. Fetch from Hugging Face
    print("\n--- 2. Fetching from Hugging Face Daily Papers API ---")
    hf_papers = fetch_huggingface_papers(today_date=today_date, api_url=hf_url)
    print(f"-> Fetched {len(hf_papers)} papers from Hugging Face.")

    # 4. Skip papers we already saved on an earlier day
    print("\n--- 3. Skipping Papers Seen on Earlier Days ---")
    all_papers = arxiv_papers + hf_papers
    seen_ids, seen_titles = load_seen_papers(args.output_dir, today_str)
    fresh_papers = remove_seen_papers(all_papers, seen_ids, seen_titles)
    skipped = len(all_papers) - len(fresh_papers)
    print(f"-> Skipped {skipped} already-seen papers. {len(fresh_papers)} are new.")

    # 5. Filter by keywords and deduplicate
    print("\n--- 4. Matching Keywords & Deduplicating ---")
    final_papers = deduplicate_and_filter_papers(fresh_papers, topics)

    # 6. Save to data/YYYY-MM-DD/raw.json
    print("\n--- 5. Saving Output ---")
    saved_path = save_raw_papers(final_papers, today_str, output_root=args.output_dir)

    print("\n" + "=" * 70)
    print("  Summary of Results")
    print("=" * 70)
    print(f"  Total Candidate Papers Fetched : {len(all_papers)}")
    print(f"    - From arXiv ({window_str}): {len(arxiv_papers)}")
    print(f"    - From Hugging Face ({today_str}): {len(hf_papers)}")
    print(f"  Skipped (seen on earlier days) : {skipped}")
    print(f"  Final Matched & Deduplicated   : {len(final_papers)}")
    print(f"  Saved File Location            : {saved_path}")
    print("=" * 70 + "\n")

    # Display preview of matched papers
    if final_papers:
        print("Sample Matched Papers:")
        for idx, p in enumerate(final_papers[:5], 1):
            src = ", ".join(p.get("sources", []))
            topics_matched = ", ".join(p.get("matched_topics", []))
            print(f"  {idx}. [{src.upper()}] {p['title']}")
            print(f"     ID     : {p.get('id')}")
            print(f"     Topics : {topics_matched}")
            print(f"     Matched: {', '.join(p.get('matched_keywords', [])[:4])}")
            print()


if __name__ == "__main__":
    main()
