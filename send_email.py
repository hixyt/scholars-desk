"""Turn the checked digest into the morning email and send it with Gmail.

Run:  python send_email.py --preview                      (writes data/<date>/email.html, sends nothing)
      python send_email.py --preview --topics health,trust (a subscriber's copy with only those topics)
      python send_email.py                                (sends today's email)

Needs GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env (or GitHub Secrets).
EMAIL_TO is optional; without it the email goes to GMAIL_ADDRESS. Those addresses get every paper.
With SUPABASE_SECRET_KEY set, confirmed subscribers get their own copy too, with only the
papers on the topics they chose and their own links to change topics or unsubscribe.
"""

import argparse
import html
import json
import os
import re
import smtplib
import ssl
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

import requests
from dotenv import load_dotenv

from common import load_config, log, run, tidy_title
from email_art import SPINES, banner_png, spine_label

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
WORDS = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"]
LEVELS = {"easy": 1, "medium": 2, "hard": 3}
LABELS = {}  # topic name -> short label, filled from config.yaml in main()

# Same colours as the website. Email apps ignore most CSS, so nearly every style is inline.
INK, INK_2, PAGE, PAGE_2, TEXT, MUTED = "#0B0907", "#15100C", "#EFE6D0", "#E7DCC2", "#2B2118", "#6B5A45"
GOLD, GOLD_HI, PARCHMENT, DIM, RED, LINE = "#CFAE6B", "#EBD29B", "#EDE3CC", "#A3957E", "#A3342A", "#2E251C"
SERIF = "Georgia, 'Times New Roman', serif"
DISPLAY = "'Playfair Display', Georgia, 'Times New Roman', serif"
CAPS = "Cinzel, Georgia, 'Times New Roman', serif"
TABLE = 'role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"'


def esc(text):
    return html.escape(str(text or ""))


def with_notes(text):
    """Escape the text and make the [plain-English notes] quieter than the sentence around them."""
    return re.sub(r"\[([^\]]+)\]", rf'<span style="color:{MUTED};font-style:italic;">[\1]</span>', esc(text))


def short_authors(authors):
    last = [a.split()[-1] for a in (authors or []) if a.strip()]
    if len(last) <= 4:
        return ", ".join(last)
    return f"{', '.join(last[:3])} and {len(last) - 3} more"


def count_words(n):
    word = WORDS[n] if n < len(WORDS) else str(n)
    return f"{word} new AI paper{'s' if n != 1 else ''}"


def left_out_note(digest):
    n = len(digest.get("left_out") or [])
    if not n:
        return ""
    return (f" {WORDS[n] if n < len(WORDS) else n} more paper{'s were' if n != 1 else ' was'} picked today but left out,"
            f" because none of {'their' if n != 1 else 'its'} summary could be proven.")


def short_title(title):
    return title.split(":")[0].strip()


def nice_date(day, fmt):
    return datetime.strptime(day, "%Y-%m-%d").strftime(fmt).replace(" 0", " ")


def dots(difficulty):
    n = LEVELS.get(str(difficulty or "").strip().lower())
    return "" if n is None else "&#9679;" * n + "&#9675;" * (3 - n)


def kicker(text, color=MUTED, size=11):
    return (f'<div style="font-family:{CAPS};font-size:{size}px;letter-spacing:2px;text-transform:uppercase;'
            f'color:{color};">{text}</div>')


# ---------------------------------------------------------------- the numbers

def day_numbers(digest, folder, data_dir):
    """What the email can honestly count for this day."""
    nums = {"issue": sum(1 for d in Path(data_dir).glob("*/digest.json")  # days that had an email
                         if d.parent.name <= digest["date"] and json.loads(d.read_text(encoding="utf-8")).get("papers"))}
    stats = folder / "stats.json"
    if stats.exists():
        nums.update(json.loads(stats.read_text(encoding="utf-8")))
    elif (folder / "raw.json").exists():
        nums["matched"] = len(json.loads((folder / "raw.json").read_text(encoding="utf-8")))
    return numbers_for(nums, digest)


def numbers_for(nums, digest):
    """The picked and proven counts for this copy of the email (a subscriber's copy has fewer papers)."""
    claims = [c for p in digest["papers"] + digest.get("left_out", []) for c in p.get("claims") or []]
    return dict(nums, picked=len(digest["papers"]), checked=len(claims),
                proven=sum(1 for c in claims if c.get("supported")))


# ---------------------------------------------------------------- readers and their topics

def topic_names(config, slugs):
    """Topic names for a subscriber's chosen slugs. Nothing chosen means every topic."""
    by_slug = {t["slug"]: t["name"] for t in config["topics"]}
    return {by_slug[s] for s in slugs or [] if s in by_slug} or set(by_slug.values())


def topic_labels(config, slugs):
    chosen = set(slugs or []) & {t["slug"] for t in config["topics"]}
    return [t["label"] for t in config["topics"] if not chosen or t["slug"] in chosen]


def supabase_headers(key):
    headers = {"apikey": key}
    if key.count(".") == 2:  # an old-style JWT key also goes in the Authorization header
        headers["Authorization"] = f"Bearer {key}"
    return headers


def fetch_subscribers(config):
    """Confirmed subscribers from Supabase. Empty when SUPABASE_SECRET_KEY isn't set."""
    key = (os.getenv("SUPABASE_SECRET_KEY") or "").strip()
    url = ((config.get("site") or {}).get("supabase_url") or "").strip().rstrip("/")
    if not key or not url:
        log.info("No SUPABASE_SECRET_KEY, so only EMAIL_TO gets the email")
        return []
    try:
        r = requests.get(f"{url}/rest/v1/subscribers", headers=supabase_headers(key), timeout=30,
                         params={"select": "email,topics,token", "confirmed": "is.true", "order": "id"})
        r.raise_for_status()
        return [s for s in r.json() if s.get("email") and s.get("token")]
    except Exception as e:  # never stop the owner's email because of the list
        log.warning(f"Could not read the subscribers, so only EMAIL_TO gets the email: {e}")
        return []


def edition(digest, papers):
    """The digest cut down to some of its papers. Left-out papers only show in the full copy."""
    return dict(digest, papers=papers, left_out=[])


def reader_links(config, sub):
    """The bottom lines of a subscriber's copy: their topics and their own links. (html, text, unsubscribe url)"""
    site = (config.get("email", {}).get("site_url") or "").rstrip("/") + "/"
    manage, leave = f"{site}?manage={sub['token']}", f"{site}?unsub={sub['token']}"
    labels = " &middot; ".join(esc(x) for x in topic_labels(config, sub.get("topics")))
    html_part = (f'You chose: {labels}<br><a href="{esc(manage)}" style="color:{GOLD};">Change topics</a>'
                 f' &middot; <a href="{esc(leave)}" style="color:{GOLD};">Unsubscribe</a>')
    text_part = (f"You chose: {', '.join(topic_labels(config, sub.get('topics')))}\n"
                 f"Change topics: {manage}\nUnsubscribe: {leave}")
    fn = ((config.get("site") or {}).get("supabase_url") or "").rstrip("/")
    return html_part, text_part, (f"{fn}/functions/v1/desk?unsub={sub['token']}" if fn else leave)


def struck_lines(digest):
    """Lines the checker refused today, with its reason."""
    out = []
    for p in digest["papers"] + digest.get("left_out", []):
        for c in p.get("claims") or []:
            if not c.get("supported") and not c.get("no_verdict") and c.get("reason"):
                out.append((spine_label(p["title"]), c["claim"], c["reason"]))
    return out


# ---------------------------------------------------------------- HTML pieces

def ledger_row(nums):
    cells = []
    if nums.get("fetched"):
        cells.append((f"{nums['fetched']:,}", "read"))
    if nums.get("matched"):
        cells.append((f"{nums['matched']:,}", "on topic"))
    cells.append((str(nums["picked"]), "picked"))
    if nums["checked"]:
        cells.append((f"{nums['proven']}/{nums['checked']}", "lines proven"))
    if len(cells) < 4:
        cells.append(("&#8377;0", "cost"))
    tds = "".join(
        f'<td align="center" width="{100 // len(cells)}%" style="padding:16px 4px;{"border-left:1px solid " + LINE + ";" if i else ""}">'
        f'<div style="font-family:{DISPLAY};font-size:26px;font-style:italic;color:{GOLD_HI};">{value}</div>'
        f'<div style="padding-top:4px;font-family:{CAPS};font-size:10px;letter-spacing:2px;text-transform:uppercase;color:{DIM};">{label}</div></td>'
        for i, (value, label) in enumerate(cells))
    return (f'<tr><td style="padding:0 0 26px;"><table {TABLE} style="background:{INK_2};border:1px solid {LINE};'
            f'border-radius:4px;"><tr>{tds}</tr></table></td></tr>')


def contents(papers):
    rows = ""
    for n, p in enumerate(papers):
        proj = p.get("project_idea") or {}
        border = f"border-top:1px solid {LINE};" if n else ""
        rows += (
            f'<tr><td width="38" valign="top" style="padding:12px 0;{border}font-family:{DISPLAY};font-size:17px;font-style:italic;color:{GOLD};">{ROMAN[n]}</td>'
            f'<td style="padding:12px 8px 12px 0;{border}"><div style="font-family:{SERIF};font-size:16px;color:{PARCHMENT};">{esc(short_title(p["title"]))}</div>'
            f'<div style="padding-top:2px;font-family:{SERIF};font-size:13px;font-style:italic;color:{DIM};">{esc(proj.get("title") or "")}</div></td>'
            f'<td align="right" valign="top" style="padding:13px 0;{border}white-space:nowrap;font-family:{SERIF};font-size:12px;color:{GOLD};">'
            f'{dots(proj.get("difficulty"))}<div style="padding-top:3px;color:{DIM};">{esc(proj.get("time_estimate") or "")}</div></td></tr>'
        )
    return (f'<tr><td style="padding:0 6px 6px;">{kicker("In this issue", GOLD, 12)}</td></tr>'
            f'<tr><td style="padding:0 6px 30px;"><table {TABLE}>{rows}</table></td></tr>')


def paper_block(n, p):
    proj = p.get("project_idea") or {}
    topic = p.get("shown_topic") or (p.get("matched_topics") or [""])[0]
    topic = LABELS.get(topic, topic)
    spine = SPINES[n % len(SPINES)]
    url = esc(p.get("url"))
    hf = (f' &middot; <span style="color:{RED};">trending on Hugging Face</span>'
          if "huggingface" in (p.get("sources") or []) else "")

    head = (
        f'<table {TABLE}><tr>'
        f'<td width="56" valign="top"><table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td width="48" height="48" align="center" valign="middle" style="width:48px;height:48px;border-radius:50%;background:{spine};'
        f'border:2px solid {GOLD};font-family:{DISPLAY};font-size:19px;font-style:italic;font-weight:bold;color:{GOLD_HI};">{ROMAN[n]}</td>'
        f'</tr></table></td>'
        f'<td valign="top" style="padding-left:10px;">{kicker(esc(topic), RED)}'
        f'<div style="padding:6px 0 0;font-family:{DISPLAY};font-size:23px;line-height:1.28;font-style:italic;">'
        f'<a href="{url}" style="color:{TEXT};text-decoration:none;">{esc(p.get("title"))}</a></div></td>'
        f'</tr></table>'
        f'<div style="padding:10px 0 18px;font-family:{SERIF};font-size:13px;color:{MUTED};">'
        f'{esc(short_authors(p.get("authors")))} &middot; arXiv {esc(p.get("id"))}{hf}</div>'
    )
    body = ""
    if p.get("explanation"):
        body += (f'<table {TABLE}><tr><td style="border-left:3px solid {GOLD};padding:2px 0 2px 16px;">'
                 f'{kicker("What they did")}<div style="padding-top:6px;font-family:{SERIF};font-size:18px;line-height:1.6;color:{TEXT};">'
                 f'{with_notes(p["explanation"])}</div></td></tr></table>')
    for name, key in (("Why I picked it", "ranking_reason"), ("Why it matters to you", "why_it_matters")):
        if p.get(key):
            body += (f'<div style="padding:20px 0 0;">{kicker(name)}<div style="padding-top:6px;font-family:{SERIF};'
                     f'font-size:15.5px;line-height:1.65;color:{TEXT};">{with_notes(p[key])}</div></div>')

    ticket = ""
    if proj.get("title"):
        words = " &middot; ".join(esc(x) for x in (proj.get("difficulty"), proj.get("time_estimate")) if x)
        level = dots(proj.get("difficulty"))
        meta = (f'<span style="color:{GOLD};">{level}</span>&nbsp; ' if level else "") + words
        no_code = ""
        if proj.get("no_code_version"):
            no_code = (f'<div style="margin-top:12px;padding-top:12px;border-top:1px dashed #C2AD82;font-family:{SERIF};font-size:14px;'
                       f'line-height:1.55;font-style:italic;color:{MUTED};"><b style="font-style:normal;color:{TEXT};">No code?</b> '
                       f'{with_notes(proj["no_code_version"])}</div>')
        ticket = (
            f'<table {TABLE} style="margin-top:22px;background:{PAGE_2};border:1px dashed #B79F6E;border-radius:3px;"><tr><td style="padding:16px 18px;">'
            f'<table {TABLE}><tr><td>{kicker("&#10022; Weekend project", RED)}</td>'
            f'<td align="right" style="font-family:{SERIF};font-size:12px;color:{MUTED};white-space:nowrap;">{meta}</td></tr></table>'
            f'<div style="padding:8px 0 6px;font-family:{DISPLAY};font-size:20px;font-weight:bold;color:{TEXT};">{esc(proj["title"])}</div>'
            f'<div style="font-family:{SERIF};font-size:15px;line-height:1.6;color:{TEXT};">{with_notes(proj.get("description"))}</div>'
            f'{no_code}</td></tr></table>'
        )

    checked, proven = p.get("claims_checked"), p.get("claims_supported")
    stamp = ""
    if checked:
        ok = proven == checked
        color = "#3E6B4A" if ok else RED
        stamp = (f'<td valign="middle"><span style="display:inline-block;padding:5px 9px;border:1.5px solid {color};border-radius:3px;'
                 f'font-family:{CAPS};font-size:10px;letter-spacing:1.5px;text-transform:uppercase;color:{color};">'
                 f'&#10003; {proven} of {checked} lines proven</span></td>')
    pdf = (f'&nbsp;<a href="{esc(p["pdf_url"])}" style="display:inline-block;padding:9px 12px;border:1px solid {TEXT};border-radius:3px;'
           f'font-family:{CAPS};font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:{TEXT};text-decoration:none;">PDF</a>'
           if p.get("pdf_url") else "")
    actions = (f'<table {TABLE} style="margin-top:22px;"><tr>{stamp}<td align="right" valign="middle" style="white-space:nowrap;">'
               f'<a href="{url}" style="display:inline-block;padding:10px 14px;background:{TEXT};border-radius:3px;font-family:{CAPS};font-size:11px;'
               f'letter-spacing:1.5px;text-transform:uppercase;color:{PAGE};text-decoration:none;">Read it &rarr;</a>{pdf}</td></tr></table>')

    return (f'<tr><td style="padding:0 0 22px;"><table {TABLE} style="background:{PAGE};border-radius:4px;">'
            f'<tr><td height="6" style="height:6px;line-height:6px;font-size:6px;background:{spine};border-radius:4px 4px 0 0;">&nbsp;</td></tr>'
            f'<tr><td class="card" style="padding:24px 26px 24px;">{head}{body}{ticket}{actions}</td></tr></table></td></tr>')


def struck_block(lines):
    if not lines:
        return ""
    items = "".join(
        f'<tr><td style="padding:14px 0;{"border-top:1px solid " + LINE + ";" if i else ""}">'
        f'<div style="font-family:{SERIF};font-size:15.5px;line-height:1.55;font-style:italic;color:#D98A7E;text-decoration:line-through;">'
        f'&ldquo;{esc(claim)}&rdquo;</div>'
        f'<div style="padding-top:6px;font-family:{SERIF};font-size:13.5px;line-height:1.55;color:{DIM};">'
        f'<span style="font-family:{CAPS};font-size:10px;letter-spacing:1.5px;color:{GOLD};">{esc(name)}</span> &nbsp;{esc(reason)}</div></td></tr>'
        for i, (name, claim, reason) in enumerate(lines))
    return (f'<tr><td style="padding:12px 0 26px;"><table {TABLE} style="border:1px solid {LINE};border-radius:4px;background:{INK_2};">'
            f'<tr><td style="padding:22px 24px 10px;">{kicker("Struck in red ink", "#D98A7E", 12)}'
            f'<div style="padding:6px 0 4px;font-family:{SERIF};font-size:14px;line-height:1.55;font-style:italic;color:{DIM};">'
            f'The checker refused these lines today. They never made it into the cards above.</div>'
            f'<table {TABLE}>{items}</table></td></tr></table></td></tr>')


READER_SLOT = "<!--reader-links-->"


def build_html(digest, config, nums, banner_src=None, for_subscriber=False):
    em = config.get("email", {})
    papers = digest["papers"]
    day = nice_date(digest["date"], "%A, %d %B %Y")
    preheader = "Today: " + ", ".join(short_title(p["title"]) for p in papers) + (". It comes with a weekend project." if len(papers) == 1 else ". Each one comes with a weekend project.")
    links = [f'<a href="{esc(em.get("repo_url"))}" style="color:{GOLD};">Source on GitHub</a>'] if em.get("repo_url") else []
    if em.get("site_url"):
        links.insert(0, f'<a href="{esc(em["site_url"])}" style="color:{GOLD};">The website</a>')

    if banner_src:
        top = (f'<tr><td style="padding:0 0 22px;"><img src="{esc(banner_src)}" width="600" alt="The Scholar&rsquo;s Desk, {esc(day)}" '
               f'style="display:block;width:100%;max-width:600px;height:auto;border:0;border-radius:4px;"></td></tr>')
    else:  # no picture: a text masthead
        top = (f'<tr><td align="center" style="padding:6px 0 4px;font-family:{CAPS};font-size:13px;letter-spacing:4px;text-transform:uppercase;color:{GOLD};">The Scholar&rsquo;s Desk</td></tr>'
               f'<tr><td align="center" style="padding:0 0 22px;font-family:{DISPLAY};font-size:28px;font-style:italic;color:{PARCHMENT};">{esc(day)}</td></tr>')

    signed = esc(em.get("signed_by") or "")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark"><meta name="supported-color-schemes" content="dark">
<title>{esc(em.get("from_name", "The Scholar's Desk"))}</title>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600&amp;family=Playfair+Display:ital,wght@1,500;1,700&amp;display=swap" rel="stylesheet">
<style>
  @media (max-width: 480px) {{
    .card {{ padding: 20px 18px 20px !important; }}
    .wrap {{ padding: 16px 8px 30px !important; }}
  }}
</style></head>
<body style="margin:0;padding:0;background:{INK};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{esc(preheader)}</div>
<table {TABLE} style="background:{INK};">
<tr><td class="wrap" align="center" style="padding:26px 12px 40px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;">
{top}
<tr><td align="center" style="padding:0 0 6px;">{kicker(f"No. {nums['issue']} &nbsp;&middot;&nbsp; {esc(day)}", GOLD, 11)}</td></tr>
<tr><td align="center" style="padding:6px 16px 24px;font-family:{SERIF};font-size:16px;line-height:1.65;font-style:italic;color:{DIM};">
Good morning. {count_words(len(papers))}{" on your topics" if for_subscriber else ""} came off the press. The summaries below were checked line by line against each paper&rsquo;s own abstract, and every paper comes with a project you can build this weekend.{left_out_note(digest)}</td></tr>
{ledger_row(nums)}
{contents(papers)}
{"".join(paper_block(n, p) for n, p in enumerate(papers))}
{struck_block(struck_lines(digest))}
<tr><td align="center" style="padding:14px 0 18px;"><table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
<td width="90" style="border-top:1px solid {GOLD};font-size:1px;line-height:1px;">&nbsp;</td>
<td style="padding:0 12px;font-family:{SERIF};font-size:11px;line-height:11px;color:{GOLD};">&#9670;</td>
<td width="90" style="border-top:1px solid {GOLD};font-size:1px;line-height:1px;">&nbsp;</td></tr></table></td></tr>
<tr><td align="center" style="padding:0 24px 6px;font-family:{DISPLAY};font-size:20px;font-style:italic;color:{PARCHMENT};">Build one this weekend.</td></tr>
<tr><td align="center" style="padding:0 24px 26px;font-family:{SERIF};font-size:14.5px;line-height:1.6;font-style:italic;color:{DIM};">Pick a project from today&rsquo;s cards. Small builds add up.</td></tr>
<tr><td align="center" style="padding:0 0 18px;"><table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
<td width="34" height="34" align="center" valign="middle" style="width:34px;height:34px;border-radius:50%;background:#7A2620;border:2px solid #62201B;font-family:{DISPLAY};font-size:13px;font-style:italic;font-weight:bold;color:{GOLD_HI};">SD</td>
</tr></table></td></tr>
<tr><td align="center" style="padding:0 20px;font-family:{SERIF};font-size:12.5px;line-height:1.7;color:{DIM};">
Picked and written by Gemini, checked line by line by Groq, sent by a small robot for &#8377;0.<br>{" &middot; ".join(x for x in [signed and f"Made by {signed}"] + links if x)}</td></tr>
{f'<tr><td align="center" style="padding:14px 20px 0;font-family:{SERIF};font-size:12.5px;line-height:1.7;color:{DIM};">{READER_SLOT}</td></tr>' if for_subscriber else ""}
<tr><td align="center" style="padding:16px 0 0;font-family:{DISPLAY};font-size:15px;font-style:italic;color:{GOLD};">See you tomorrow morning.</td></tr>
</table></td></tr></table>
</body></html>"""


def build_text(digest, config, nums):
    """Plain-text copy, for email apps that don't show HTML."""
    em = config.get("email", {})
    plain = lambda s: re.sub(r"\s+", " ", s or "").strip()
    head = f"No. {nums['issue']} · {nice_date(digest['date'], '%A, %d %B %Y')}"
    lines = ["THE SCHOLAR'S DESK", head, "",
             f"Good morning. {count_words(len(digest['papers']))}. The summaries were checked line by line against each paper's own abstract."
             + html.unescape(left_out_note(digest)), ""]
    for n, p in enumerate(digest["papers"]):
        proj = p.get("project_idea") or {}
        lines += [f"{ROMAN[n]}. {p['title']}", f"   {short_authors(p.get('authors'))} · {p.get('url', '')}"]
        for name, key in (("What they did", "explanation"), ("Why I picked it", "ranking_reason"), ("Why it matters", "why_it_matters")):
            if p.get(key):
                lines.append(f"   {name}: {plain(p[key])}")
        if proj.get("title"):
            meta = ", ".join(x for x in (proj.get("difficulty"), proj.get("time_estimate")) if x)
            lines.append(f"   Weekend project{f' ({meta})' if meta else ''}: {proj['title']}. {plain(proj.get('description'))}")
            if proj.get("no_code_version"):
                lines.append(f"   No code? {plain(proj['no_code_version'])}")
        if p.get("claims_checked"):
            lines.append(f"   Proof: {p['claims_supported']} of {p['claims_checked']} lines found in the abstract.")
        lines.append("")
    struck = struck_lines(digest)
    if struck:
        lines.append("STRUCK IN RED INK (the checker refused these):")
        lines += [f"   - \"{plain(c)}\" ({name}): {plain(r)}" for name, c, r in struck]
        lines.append("")
    lines += ["Build one this weekend. Pick a project from today's cards. Small builds add up.", "",
              "Picked and written by Gemini, checked line by line by Groq, sent by a small robot for Rs 0."]
    if em.get("repo_url"):
        lines.append(f"Source: {em['repo_url']}")
    return "\n".join(lines)


def build_subject(digest, config):
    template = config.get("email", {}).get("subject", "The Scholar's Desk · {date} · {count} {papers}")
    n = len(digest["papers"])
    return template.format(date=nice_date(digest["date"], "%a %d %b"), count=n, papers="paper" if n == 1 else "papers")


# ---------------------------------------------------------------- sending

def make_message(subject, text, body_html, config, sender, banner=None, unsubscribe=None, to=None):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((config.get("email", {}).get("from_name", "The Scholar's Desk"), sender))
    msg["To"] = to or sender  # the full copy shows the sender here; the readers get blind copies
    if unsubscribe:  # lets Gmail show its own "Unsubscribe" button, which works in one click
        msg["List-Unsubscribe"] = f"<{unsubscribe}>, <mailto:{sender}?subject=unsubscribe>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg.set_content(text)
    msg.add_alternative(body_html, subtype="html")
    if banner:  # the picture travels inside the email, so it shows without loading anything
        msg.get_payload()[1].add_related(banner, "image", "png", cid="<banner>", filename="scholars-desk.png")
    return msg


def gmail_login():
    load_dotenv()
    sender = os.getenv("GMAIL_ADDRESS", "").strip()
    password = "".join(os.getenv("GMAIL_APP_PASSWORD", "").split())  # no spaces or line breaks; Google shows it in groups of four
    missing = [name for name, value in (("GMAIL_ADDRESS", sender), ("GMAIL_APP_PASSWORD", password)) if not value]
    if missing:
        raise SystemExit(f"{' and '.join(missing)} {'is' if len(missing) == 1 else 'are'} missing. Add {'it' if len(missing) == 1 else 'them'} to .env (or GitHub Secrets).")
    return sender, password


def send_all(batch, sender, password):
    """Send (message, recipients) pairs over one Gmail connection. Returns (people reached, people missed).
    Addresses stay out of the logs."""
    smtp, reached, missed = None, 0, 0
    try:
        for n, (msg, to) in enumerate(batch):
            for attempt in (1, 2):
                try:
                    if smtp is None:
                        smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=30)
                        smtp.login(sender, password)
                    smtp.send_message(msg, to_addrs=to)  # with several addresses, everyone gets a blind copy
                    reached += len(to)
                    break
                except smtplib.SMTPAuthenticationError:
                    raise SystemExit("Gmail refused the login. GMAIL_APP_PASSWORD must be an App Password, not your normal password.")
                except (smtplib.SMTPException, OSError) as e:
                    try:
                        smtp and smtp.quit()
                    except Exception:
                        pass
                    smtp = None
                    if attempt == 2:
                        if n == 0:  # the owner's copy has to arrive, so this one fails the run
                            raise
                        missed += len(to)
                        log.warning(f"Could not send one copy ({e})")
                    else:
                        log.warning(f"Sending failed ({e}), trying again in 15 seconds")
                        time.sleep(15)
            if len(batch) > 2:
                time.sleep(0.4)  # Gmail is happier with a short pause between many emails
    finally:
        if smtp:
            try:
                smtp.quit()
            except Exception:
                pass
    return reached, missed


def main():
    parser = argparse.ArgumentParser(description="Build the morning email from the checked digest and send it.")
    parser.add_argument("--date", help="YYYY-MM-DD (default: today in UTC)")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--preview", action="store_true", help="write email.html next to the digest and send nothing")
    parser.add_argument("--topics", help="with --preview: topic slugs, comma separated, to see a subscriber's copy")
    args = parser.parse_args()

    date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    folder = Path(args.data_dir) / date
    digest_path = folder / "digest.json"
    if not digest_path.exists():
        raise SystemExit(f"{digest_path} not found. Run verify.py first.")
    with open(digest_path, encoding="utf-8") as f:
        digest = json.load(f)
    for p in digest.get("papers", []) + digest.get("left_out", []):
        p["title"] = tidy_title(p["title"])
    if not digest.get("papers"):
        print("No papers today, so no email was sent.")
        return

    config = load_config(args.config)
    nums = day_numbers(digest, folder, args.data_dir)
    day_label = nice_date(date, "%A · %d %B %Y")

    def issue_line(n):
        return f"No. {nums['issue']} · " + ("one paper, one weekend project" if n == 1 else
                f"{WORDS[n].lower() if n < len(WORDS) else n} papers, {WORDS[n].lower() if n < len(WORDS) else n} weekend projects")

    LABELS.update({t["name"]: t["label"] for t in config["topics"]})

    def papers_for(slugs):
        """Today's papers on these topics, each tagged with the chosen topic it matched first."""
        names = topic_names(config, slugs)
        return [dict(p, shown_topic=next(t for t in p["matched_topics"] if t in names))
                for p in digest["papers"] if names & set(p.get("matched_topics") or [])]

    if args.preview:
        slugs = [s.strip() for s in (args.topics or "").split(",") if s.strip()]
        copy = edition(digest, papers_for(slugs)) if slugs else digest
        if not copy["papers"]:
            raise SystemExit("No paper today is on those topics.")
        banner = banner_png(copy["papers"], day_label, issue_line(len(copy["papers"])))
        if banner:
            (folder / "email-banner.png").write_bytes(banner)
        body_html = build_html(copy, config, numbers_for(nums, copy), "email-banner.png" if banner else None, for_subscriber=bool(slugs))
        if slugs:
            body_html = body_html.replace(READER_SLOT, reader_links(config, {"token": "PREVIEW", "topics": slugs})[0])
        out = folder / "email.html"
        out.write_text(body_html, encoding="utf-8")
        log.info(f"Subject: {build_subject(copy, config)}")
        print(f"Preview saved to {out} ({len(body_html.encode('utf-8')) // 1024} KB). Open it in your browser.")
        return

    sender, password = gmail_login()
    owners = [a.strip() for a in (os.getenv("EMAIL_TO") or sender).split(",") if a.strip()]

    # 1. the full copy, for EMAIL_TO (one email, blind copies)
    banner = banner_png(digest["papers"], day_label, issue_line(len(digest["papers"])))
    if not banner:
        log.warning("No picture today (Pillow or the fonts are missing), the email uses a text heading")
    log.info(f"Subject: {build_subject(digest, config)}")
    batch = [(make_message(build_subject(digest, config), build_text(digest, config, nums),
                           build_html(digest, config, nums, "cid:banner" if banner else None), config, sender, banner), owners)]

    # 2. one copy per subscriber, with only their topics; people with the same topics share one build
    limit = config.get("email", {}).get("max_subscriber_emails", 450)  # Gmail allows about 500 a day
    subs = [s for s in fetch_subscribers(config) if s["email"].strip().lower() not in {o.lower() for o in owners}]
    if len(subs) > limit:
        log.warning(f"{len(subs)} subscribers but Gmail allows about 500 emails a day, so only the first {limit} get today's email")
        subs = subs[:limit]
    builds, skipped = {}, 0
    for sub in subs:
        papers = papers_for(sub.get("topics"))
        if not papers:
            skipped += 1  # nothing on their topics today
            continue
        key = tuple(p["id"] for p in papers)
        if key not in builds:
            copy = edition(digest, papers)
            art = banner_png(papers, day_label, issue_line(len(papers)))
            copy_nums = numbers_for(nums, copy)
            builds[key] = (copy, art, build_html(copy, config, copy_nums, "cid:banner" if art else None, for_subscriber=True),
                           build_text(copy, config, copy_nums))
        copy, art, body_html, text = builds[key]
        link_html, link_text, unsubscribe = reader_links(config, sub)
        batch.append((make_message(build_subject(copy, config), f"{text}\n\n{link_text}", body_html.replace(READER_SLOT, link_html),
                                   config, sender, art, unsubscribe, to=sub["email"].strip()), [sub["email"].strip()]))

    reached, missed = send_all(batch, sender, password)
    n = len(digest["papers"])
    extra = f", {len(batch) - 1} of them subscribers" if len(batch) > 1 else ""
    print(f"Sent the {date} email with {n} paper{'s' if n != 1 else ''} to {reached} reader{'s' if reached != 1 else ''}{extra}.")
    if skipped:
        log.info(f"{skipped} subscriber{'s' if skipped != 1 else ''} had no paper on their topics today")
    if missed:
        log.warning(f"{missed} subscriber cop{'ies' if missed != 1 else 'y'} could not be sent")


if __name__ == "__main__":
    run(main)
