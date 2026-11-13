"""Build the website (index.html) from the saved digests.

Run:  python build_site.py
It reads data/<date>/digest.json and stats.json, fills site/page.html and writes index.html,
and fills site/check.html (the claim checker) into check.html.
GitHub Pages serves both pages and the files in site/.
"""

import argparse
import hashlib
import html
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from common import load_config, log, run, tidy_title
from email_art import spine_label

WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
IST = timezone(timedelta(hours=5, minutes=30))


def roman(n):
    out = ""
    for value, sym in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
                       (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= value:
            out, n = out + sym, n - value
    return out


def day_text(d, fmt):
    return d.strftime(fmt).replace(" 0", " ").lstrip("0")


def load_days(data_dir):
    """Every day that had papers, oldest first."""
    days = []
    for path in sorted(Path(data_dir).glob("*/digest.json")):
        digest = json.loads(path.read_text(encoding="utf-8"))
        for p in digest.get("papers", []) + digest.get("left_out", []):
            p["title"] = tidy_title(p["title"])
        if digest.get("papers"):
            stats_path = path.parent / "stats.json"
            stats = json.loads(stats_path.read_text(encoding="utf-8")) if stats_path.exists() else {}
            days.append((digest, stats))
    return days


def page_paper(p, slugs=None):
    """A paper in the shape the page's scripts expect."""
    authors = p.get("authors") or []
    return {
        "id": p["id"],
        "title": p["title"],
        "topics": p.get("matched_topics") or [],
        "slugs": [slugs[t] for t in p.get("matched_topics") or [] if t in (slugs or {})],
        "cat": p.get("primary_category") or "",
        "authors": authors[:3],
        "more_authors": max(0, len(authors) - 3),
        "sources": p.get("sources") or [],
        "upvotes": (p.get("huggingface") or {}).get("upvotes") if isinstance(p.get("huggingface"), dict) else None,
        "url": p.get("url") or f"https://arxiv.org/abs/{p['id']}",
        "reason": p.get("ranking_reason") or "",
        "explanation": p.get("explanation") or "",
        "why": p.get("why_it_matters") or "",
        "project": p.get("project_idea") or {},
        "claims": [{"src": c.get("source"), "text": c.get("claim"), "ok": bool(c.get("supported")),
                    "evidence": c.get("evidence") or "", "note": c.get("reason") or ""} for c in p.get("claims") or []],
    }


def build(data_dir="data", config_path="config.yaml", template="site/page.html", out="index.html"):
    config = load_config(config_path)
    days = load_days(data_dir)
    if not days:
        raise SystemExit("No day with papers yet, so there is nothing to show.")

    digest, stats = days[-1]
    date = datetime.strptime(digest["date"], "%Y-%m-%d")
    papers = digest["papers"]
    left_out = digest.get("left_out") or []
    claims = [c for p in papers + left_out for c in p.get("claims") or []]
    proven = sum(1 for c in claims if c.get("supported"))
    count_word = WORDS[len(papers)] if len(papers) < len(WORDS) else str(len(papers))
    one = len(papers) == 1

    shelf = []
    for n, (d, _) in enumerate(days, 1):
        dd = datetime.strptime(d["date"], "%Y-%m-%d")
        shelf.append({
            "date": d["date"],
            "label": day_text(dd, "%a %d %b"),
            "weekday": dd.strftime("%A"),
            "short": day_text(dd, "%d %b"),
            "spine": day_text(dd, "%a · %d %b").upper(),
            "roman": roman(n),
            "year": roman(dd.year),
            "papers": [{"id": p["id"], "title": p["title"], "url": p.get("url") or f"https://arxiv.org/abs/{p['id']}"}
                       for p in d["papers"]],
        })
    next_days = [date + timedelta(days=k) for k in range(1, 5)]
    data = {
        "date": digest["date"],
        "dateLabel": day_text(date, "%d %b %Y"),
        "today": [page_paper(p, {t["name"]: t["slug"] for t in config["topics"]}) for p in papers],
        "topics": [{"slug": t["slug"], "label": t["label"], "name": t["name"]} for t in config["topics"]],
        "short": {p["id"]: spine_label(p["title"]) for p in papers},
        "days": shelf,
        "nextDays": [{"short": day_text(d, "%d %b"), "label": day_text(d, "%a %d %b")} for d in next_days],
    }
    site_cfg = config.get("site") or {}
    if site_cfg.get("supabase_url") and site_cfg.get("supabase_key"):
        data["seals"] = {"url": site_cfg["supabase_url"].strip(), "key": site_cfg["supabase_key"].strip()}
        data["desk"] = {"fn": site_cfg["supabase_url"].strip().rstrip("/") + "/functions/v1/desk",
                        "key": site_cfg["supabase_key"].strip(),
                        "subscribe": bool(site_cfg.get("subscribe")), "checker": bool(site_cfg.get("checker"))}

    def num(key):
        return f"{stats[key]:,}" if key in stats else "&mdash;"

    start = date - timedelta(days=config["settings"]["arxiv"]["days_back"])
    same_month = start.month == date.month
    arxiv_range = f"{day_text(start, '%d' if same_month else '%d %b')} to {day_text(date, '%d %b')}"
    run_time = "&mdash;"
    if digest.get("verified_at"):
        ran = datetime.fromisoformat(digest["verified_at"]).astimezone(IST)
        run_time = ran.strftime("%I:%M %p").lstrip("0") + " IST"
    long_date = day_text(date, "%A, %d %B %Y")
    picked_from = f" from {stats['matched']}" if stats.get("matched", 0) > len(papers) else ""

    site = Path(template).parent
    version = hashlib.sha1(b"".join((site / f).read_bytes() for f in ("hero.css", "chapters.css", "desk.css", "hero.js", "chapters.js", "desk.js", "check.css", "check.js") if (site / f).exists())).hexdigest()[:8]
    values = {
        "SD_DATA": json.dumps(data, ensure_ascii=False).replace("</", "<\\/"),
        "VERSION": version,
        "DESCRIPTION": html.escape(
            f"One new AI paper for {long_date}, explained in plain words and checked against its abstract, with a weekend project."
            if one else
            f"{count_word.capitalize()} new AI papers for {long_date}, each explained in plain words "
            "and checked against its abstract, with a weekend project for each one."),
        "COUNT_WORD_LOWER": "paper" if one else count_word,
        "FOLIO_DEK": html.escape(
            f"One paper this morning{picked_from}. Take it off the shelf to read it." if one else
            f"{count_word.capitalize()} papers picked{picked_from} this morning. Take one off the shelf to read it."),
        "LONG_DATE": html.escape(long_date),
        "ARXIV_RANGE": html.escape(arxiv_range),
        "RUN_TIME": run_time,
        "N_FETCHED": num("fetched"),
        "N_ARXIV": num("arxiv"),
        "N_HF": num("huggingface"),
        "N_SEEN": num("already_seen"),
        "N_MATCHED": num("matched"),
        "N_PICKED": str(len(papers)),
        "N_CHECKED": str(len(claims)),
        "N_PROVEN": str(proven),
        "N_STRUCK": str(len(claims) - proven),
    }
    page = Path(template).read_text(encoding="utf-8")
    for key, value in values.items():
        page = page.replace("{{" + key + "}}", value)
    if "{{" in page:
        raise SystemExit(f"The template still has an unfilled placeholder near: {page[page.index('{{'):][:40]}")
    Path(out).write_text(page, encoding="utf-8")

    # the claim checker's page (check.html), from site/check.html
    template2 = site / "check.html"
    if template2.exists():
        desk = data.get("desk") or {}
        page2 = template2.read_text(encoding="utf-8").replace("{{VERSION}}", version).replace(
            "{{SD_DESK}}", json.dumps({"fn": desk.get("fn", ""), "checker": bool(desk.get("checker"))}).replace("</", "<\\/"))
        name = "check.html" if Path(out).name == "index.html" else f"{Path(out).stem}-check.html"
        Path(out).with_name(name).write_text(page2, encoding="utf-8")
    return digest["date"], len(papers), len(days)


def wake_seal_book(config):
    """Read the Seal Book once. Free Supabase projects sleep after a quiet week; this daily visit keeps it awake."""
    site = config.get("site") or {}
    url, key = (site.get("supabase_url") or "").strip(), (site.get("supabase_key") or "").strip()
    if not url or not key:
        return
    try:
        r = requests.get(f"{url.rstrip('/')}/rest/v1/seals?select=id&limit=1", headers={"apikey": key}, timeout=20)
        if r.ok:
            log.info("The Seal Book is awake")
        else:
            log.warning(f"The Seal Book answered {r.status_code}")
    except requests.RequestException as e:
        log.warning(f"Could not reach the Seal Book: {e}")


def main():
    parser = argparse.ArgumentParser(description="Build index.html from the saved digests.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()
    date, count, n_days = build(args.data_dir, args.config)
    wake_seal_book(load_config(args.config))
    log.info(f"Website built for {date}: {count} papers on the desk, {n_days} days on the shelf")


if __name__ == "__main__":
    run(main)
