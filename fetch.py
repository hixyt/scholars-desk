#!/usr/bin/env python3
"""
Step 1: fetch new AI papers and keep the ones that match my topics.

Sources: the arXiv API (cs.AI, cs.CL, cs.HC, cs.LG) and Hugging Face Daily Papers.
No API keys needed. Saves data/YYYY-MM-DD/raw.json.

Why look back several days instead of only "yesterday"? arXiv publishes once a day
and not on weekends, so late and weekend papers show up a day or more later.
We look back days_back days and skip anything saved on an earlier day.
"""

import argparse
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from common import load_config, log

HEADERS = {"User-Agent": "TheScholarsDesk/1.0 (daily AI paper digest; mailto:scholars-desk@users.noreply.github.com)"}
ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}


def normalize_arxiv_id(raw_id):
    """'http://arxiv.org/abs/2401.12345v2' -> '2401.12345'"""
    match = re.search(r"(\d{4}\.\d{4,5}|[a-zA-Z\-]+/\d{7})", raw_id or "")
    if match:
        return match.group(1)
    return re.sub(r"v\d+$", "", (raw_id or "").split("/")[-1]).strip()


def normalize_title(title):
    """Lowercase letters and numbers only, so the same title from two sites matches."""
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", title or "").strip().lower())


def make_paper(paper_id, title, abstract, authors, published, source, categories=(), primary="cs.AI", hf=None):
    return {
        "id": paper_id,
        "title": " ".join(title.split()),
        "abstract": " ".join(abstract.split()),
        "authors": authors,
        "published": published,
        "url": f"https://arxiv.org/abs/{paper_id}",
        "pdf_url": f"https://arxiv.org/pdf/{paper_id}.pdf",
        "categories": list(categories),
        "primary_category": primary,
        "sources": [source],
        "huggingface": hf,
    }


def parse_arxiv_entry(entry):
    """Turn one <entry> of arXiv's XML reply into a paper dict."""
    text = lambda tag: (entry.findtext(tag, default="", namespaces=ARXIV_NS) or "").strip()
    categories = list(dict.fromkeys(c.get("term") for c in entry.findall("atom:category", ARXIV_NS) if c.get("term")))
    primary = entry.find("arxiv:primary_category", ARXIV_NS)
    return make_paper(
        normalize_arxiv_id(text("atom:id")),
        text("atom:title") or "Untitled",
        text("atom:summary"),
        [a.findtext("atom:name", default="", namespaces=ARXIV_NS).strip() for a in entry.findall("atom:author", ARXIV_NS)],
        text("atom:published"),
        "arxiv",
        categories,
        primary.get("term") if primary is not None else (categories[0] if categories else "cs.AI"),
    )


def fetch_arxiv_papers(start_date, end_date, categories, max_results, page_size, wait_seconds):
    """Papers submitted between start_date and end_date, one page at a time."""
    cats = " OR ".join(f"cat:{c}" for c in categories)
    query = f"({cats}) AND submittedDate:[{start_date:%Y%m%d}0000 TO {end_date:%Y%m%d}2359]"
    log.info(f"Asking arXiv for {start_date:%Y-%m-%d} to {end_date:%Y-%m-%d}")

    papers, retried = [], False
    while len(papers) < max_results:
        time.sleep(wait_seconds)  # arXiv asks for at least 3 seconds between requests
        params = {"search_query": query, "sortBy": "submittedDate", "sortOrder": "descending",
                  "start": len(papers), "max_results": min(page_size, max_results - len(papers))}
        try:
            response = requests.get("http://export.arxiv.org/api/query", params=params, headers=HEADERS, timeout=60)
            response.raise_for_status()
            root = ET.fromstring(response.text)
        except Exception as e:
            log.error(f"arXiv request failed: {e}")
            break

        total = int(root.findtext("opensearch:totalResults", default="0", namespaces=ARXIV_NS))
        entries = root.findall("atom:entry", ARXIV_NS)
        log.info(f"arXiv page: {len(entries)} papers ({len(papers) + len(entries)} of {total})")

        # arXiv sometimes sends an empty page by mistake, so try it once more
        if not entries and len(papers) < total and not retried:
            retried = True
            continue
        papers += [parse_arxiv_entry(e) for e in entries]
        if not entries or len(papers) >= total:
            break
    return papers


def fetch_huggingface_papers(day, api_url):
    """Hugging Face's daily list for this date, or the latest list if that day is empty."""
    try:
        response = requests.get(api_url, params={"date": f"{day:%Y-%m-%d}"}, headers=HEADERS, timeout=20)
        data = response.json() if response.ok else []
        if not data:
            log.info("No Hugging Face list for today yet, using the latest one")
            response = requests.get(api_url, headers=HEADERS, timeout=20)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        log.error(f"Hugging Face request failed: {e}")
        return []

    papers = []
    for item in data:
        p = item.get("paper", {})
        paper_id = normalize_arxiv_id(p.get("id") or item.get("id"))
        authors = [a["name"] if isinstance(a, dict) else a for a in p.get("authors", [])]
        hf = {"upvotes": p.get("upvotes", 0), "num_comments": item.get("numComments", 0),
              "discussion_id": p.get("discussionId")}
        papers.append(make_paper(paper_id, p.get("title") or item.get("title") or "Untitled",
                                 p.get("summary") or item.get("summary") or "", authors,
                                 p.get("publishedAt") or item.get("publishedAt") or "", "huggingface", hf=hf))
    return papers


def remove_seen_papers(papers, data_dir, today):
    """Drop papers saved on an earlier day (data/<date>/raw.json), so nothing repeats."""
    seen_ids, seen_titles = set(), set()
    for raw_file in Path(data_dir).glob("*/raw.json"):
        if raw_file.parent.name >= today:
            continue  # ignore today's own file, so a re-run gives the same result
        with open(raw_file, encoding="utf-8") as f:
            for p in json.load(f):
                if p["id"]:
                    seen_ids.add(p["id"])
                seen_titles.add(normalize_title(p["title"]))
    return [p for p in papers if p["id"] not in seen_ids and normalize_title(p["title"]) not in seen_titles]


def match_topics(paper, topics):
    """Which topics' keywords appear in the title or abstract, as whole words."""
    text = f"{paper['title']} {paper['abstract']}".lower()
    matched_topics, matched_keywords = [], []
    for topic, keywords in topics.items():
        # \b = word boundary, so "agent" doesn't match inside "reagent"
        hits = [kw for kw in keywords if re.search(r"\b" + re.escape(kw) + r"\b", text)]
        if hits:
            matched_topics.append(topic)
            matched_keywords += [kw for kw in hits if kw not in matched_keywords]
    return matched_topics, matched_keywords


def deduplicate_and_filter_papers(papers, topics):
    """Keep papers that match a topic, and merge the same paper coming from arXiv and Hugging Face."""
    merged, key_by_title = {}, {}
    for paper in papers:
        matched_topics, matched_keywords = match_topics(paper, topics)
        if not matched_topics:
            continue
        paper.update(matched_topics=matched_topics, matched_keywords=matched_keywords)

        title = normalize_title(paper["title"])
        key = paper["id"] if paper["id"] in merged else key_by_title.get(title, paper["id"] or title)
        if key not in merged:
            merged[key] = paper
            key_by_title[title] = key
            continue

        old = merged[key]
        for field in ("sources", "categories", "matched_topics", "matched_keywords"):
            old[field] += [x for x in paper[field] if x not in old[field]]
        if len(paper["abstract"]) > len(old["abstract"]):
            old["abstract"] = paper["abstract"]
        old["huggingface"] = old["huggingface"] or paper["huggingface"]
    return list(merged.values())


def main():
    parser = argparse.ArgumentParser(description="Fetch new AI papers and keep the ones that match my topics.")
    parser.add_argument("--date", help="YYYY-MM-DD (default: today in UTC)")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    today = datetime.strptime(args.date, "%Y-%m-%d") if args.date else datetime.now(timezone.utc)
    today_str = f"{today:%Y-%m-%d}"
    config = load_config(args.config)
    arxiv = config["settings"]["arxiv"]
    topics = {t["name"]: [k.lower() for k in t["keywords"]] for t in config["topics"]}

    start = today - timedelta(days=arxiv["days_back"])
    arxiv_papers = fetch_arxiv_papers(start, today, arxiv["categories"], arxiv["max_results"],
                                      arxiv["page_size"], arxiv["rate_limit_seconds"])
    hf_papers = fetch_huggingface_papers(today, config["settings"]["huggingface"]["daily_papers_url"])

    all_papers = arxiv_papers + hf_papers
    new_papers = remove_seen_papers(all_papers, args.data_dir, today_str)
    matched = deduplicate_and_filter_papers(new_papers, topics)

    folder = Path(args.data_dir) / today_str
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "raw.json", "w", encoding="utf-8") as f:
        json.dump(matched, f, indent=2, ensure_ascii=False)

    print(f"\narXiv ({start:%Y-%m-%d} to {today_str}): {len(arxiv_papers)} papers")
    print(f"Hugging Face: {len(hf_papers)} papers")
    print(f"Already seen on earlier days: {len(all_papers) - len(new_papers)}")
    print(f"Matched my topics: {len(matched)}")
    print(f"Saved to {folder / 'raw.json'}")


if __name__ == "__main__":
    main()
