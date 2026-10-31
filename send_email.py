"""Turn the checked digest into the morning email and send it with Gmail.

Run:  python send_email.py --preview    (writes data/<date>/email.html, sends nothing)
      python send_email.py              (sends today's email)

Needs GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env (or GitHub Secrets).
EMAIL_TO is optional; without it the email goes to GMAIL_ADDRESS.
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

from dotenv import load_dotenv

from common import load_config, log, run
from email_art import SPINES, banner_png, spine_label

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
WORDS = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"]
LEVELS = {"easy": 1, "medium": 2, "hard": 3}

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
    papers = digest["papers"]
    nums = {
        "picked": len(papers),
        "checked": sum(p.get("claims_checked") or 0 for p in papers),
        "proven": sum(p.get("claims_supported") or 0 for p in papers),
        "issue": sum(1 for d in Path(data_dir).glob("*/digest.json")  # days that had an email
                     if d.parent.name <= digest["date"] and json.loads(d.read_text(encoding="utf-8")).get("papers")),
    }
    stats = folder / "stats.json"
    if stats.exists():
        nums.update(json.loads(stats.read_text(encoding="utf-8")))
    elif (folder / "raw.json").exists():
        nums["matched"] = len(json.loads((folder / "raw.json").read_text(encoding="utf-8")))
    return nums


def struck_lines(digest):
    """Lines the checker refused today, with its reason."""
    out = []
    for p in digest["papers"]:
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
    topic = (p.get("matched_topics") or [""])[0]
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


def build_html(digest, config, nums, banner_src=None):
    em = config.get("email", {})
    papers = digest["papers"]
    day = nice_date(digest["date"], "%A, %d %B %Y")
    preheader = "Today: " + ", ".join(short_title(p["title"]) for p in papers) + ". Each one comes with a weekend project."
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
Good morning. {count_words(len(papers))} came off the press. Every line on the cards below was checked against the paper&rsquo;s own abstract, and each one comes with a project you can build this weekend.</td></tr>
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
<tr><td align="center" style="padding:16px 0 0;font-family:{DISPLAY};font-size:15px;font-style:italic;color:{GOLD};">See you tomorrow morning.</td></tr>
</table></td></tr></table>
</body></html>"""


def build_text(digest, config, nums):
    """Plain-text copy, for email apps that don't show HTML."""
    em = config.get("email", {})
    plain = lambda s: re.sub(r"\s+", " ", s or "").strip()
    head = f"No. {nums['issue']} · {nice_date(digest['date'], '%A, %d %B %Y')}"
    lines = ["THE SCHOLAR'S DESK", head, "",
             f"Good morning. {count_words(len(digest['papers']))}. Every line was checked against the paper's own abstract.", ""]
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
    template = config.get("email", {}).get("subject", "The Scholar's Desk · {date} · {count} papers")
    return template.format(date=nice_date(digest["date"], "%a %d %b"), count=len(digest["papers"]))


# ---------------------------------------------------------------- sending

def send(subject, text, body_html, config, banner=None):
    """Send through Gmail. Returns how many people it went to (addresses stay out of the logs)."""
    load_dotenv()
    sender = os.getenv("GMAIL_ADDRESS", "").strip()
    password = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "")  # Google shows it in groups of four
    to = [a.strip() for a in (os.getenv("EMAIL_TO") or sender).split(",") if a.strip()]
    if not sender or not password:
        raise SystemExit("GMAIL_ADDRESS or GMAIL_APP_PASSWORD is missing. Add them to .env (or GitHub Secrets).")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((config.get("email", {}).get("from_name", "The Scholar's Desk"), sender))
    msg["To"] = sender
    msg.set_content(text)
    msg.add_alternative(body_html, subtype="html")
    if banner:  # the picture travels inside the email, so it shows without loading anything
        msg.get_payload()[1].add_related(banner, "image", "png", cid="<banner>", filename="scholars-desk.png")

    for attempt in (1, 2):
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=30) as smtp:
                smtp.login(sender, password)
                smtp.send_message(msg, to_addrs=to)  # everyone else gets a blind copy
            return len(to)
        except smtplib.SMTPAuthenticationError:
            raise SystemExit("Gmail refused the login. GMAIL_APP_PASSWORD must be an App Password, not your normal password.")
        except (smtplib.SMTPException, OSError) as e:
            if attempt == 2:
                raise
            log.warning(f"Sending failed ({e}), trying again in 15 seconds")
            time.sleep(15)


def main():
    parser = argparse.ArgumentParser(description="Build the morning email from the checked digest and send it.")
    parser.add_argument("--date", help="YYYY-MM-DD (default: today in UTC)")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--preview", action="store_true", help="write email.html next to the digest and send nothing")
    args = parser.parse_args()

    date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    folder = Path(args.data_dir) / date
    digest_path = folder / "digest.json"
    if not digest_path.exists():
        raise SystemExit(f"{digest_path} not found. Run verify.py first.")
    with open(digest_path, encoding="utf-8") as f:
        digest = json.load(f)
    if not digest.get("papers"):
        print("No papers today, so no email was sent.")
        return

    config = load_config(args.config)
    nums = day_numbers(digest, folder, args.data_dir)
    n = len(digest["papers"])
    banner = banner_png(digest["papers"], nice_date(date, "%A · %d %B %Y"),
                        f"No. {nums['issue']} · {WORDS[n].lower() if n < len(WORDS) else n} papers, {WORDS[n].lower() if n < len(WORDS) else n} weekend projects")
    if not banner:
        log.warning("No picture today (Pillow or the fonts are missing), the email uses a text heading")
    subject = build_subject(digest, config)
    log.info(f"Subject: {subject}")

    if args.preview:
        if banner:
            (folder / "email-banner.png").write_bytes(banner)
        body_html = build_html(digest, config, nums, "email-banner.png" if banner else None)
        out = folder / "email.html"
        out.write_text(body_html, encoding="utf-8")
        print(f"Preview saved to {out} ({len(body_html.encode('utf-8')) // 1024} KB). Open it in your browser.")
        return

    body_html = build_html(digest, config, nums, "cid:banner" if banner else None)
    count = send(subject, build_text(digest, config, nums), body_html, config, banner)
    print(f"Sent the {date} email with {n} papers to {count} reader{'s' if count != 1 else ''}.")


if __name__ == "__main__":
    run(main)
