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

from common import load_config, log

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
WORDS = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"]

# Same colours as the website. Email apps ignore most CSS, so every style is inline.
INK, PAGE, PAGE_2, TEXT, MUTED = "#0B0907", "#EFE6D0", "#E5D8BB", "#2B2118", "#6B5A45"
GOLD, GOLD_HI, PARCHMENT, DIM, RED, RULE = "#CFAE6B", "#EBD29B", "#EDE3CC", "#A3957E", "#A3342A", "#D8CBAE"
SERIF = "Georgia, 'Times New Roman', serif"


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


def label(text, extra=""):
    """Small capital heading. `extra` is HTML that is already escaped."""
    return (f'<div style="padding:0 0 4px;font-family:{SERIF};font-size:11px;letter-spacing:2px;'
            f'text-transform:uppercase;color:{MUTED};">{esc(text)}{extra}</div>')


def para(text, size=16):
    return f'<div style="padding:0 0 16px;font-family:{SERIF};font-size:{size}px;line-height:1.6;color:{TEXT};">{text}</div>'


def paper_block(n, p):
    proj = p.get("project_idea") or {}
    topic = (p.get("matched_topics") or [""])[0]
    parts = [
        f'<div style="font-family:{SERIF};font-size:11px;letter-spacing:2px;text-transform:uppercase;color:{RED};">'
        f'{ROMAN[n]} &middot; {esc(topic)}</div>',
        f'<div style="padding:8px 0 6px;font-family:{SERIF};font-size:22px;line-height:1.3;font-style:italic;">'
        f'<a href="{esc(p.get("url"))}" style="color:{TEXT};text-decoration:none;">{esc(p.get("title"))}</a></div>',
        f'<div style="font-family:{SERIF};font-size:13px;color:{MUTED};">{esc(short_authors(p.get("authors")))}'
        f' &middot; arXiv {esc(p.get("id"))}</div>',
        f'<div style="height:1px;line-height:1px;font-size:1px;background:{RULE};margin:16px 0 16px;">&nbsp;</div>',
    ]
    if p.get("ranking_reason"):
        parts += [label("Why I picked it"), para(with_notes(p["ranking_reason"]))]
    if p.get("explanation"):
        parts += [label("What they did"), para(with_notes(p["explanation"]))]
    if p.get("why_it_matters"):
        parts += [label("Why it matters to you"), para(with_notes(p["why_it_matters"]))]
    if proj.get("title"):
        meta = " &middot; ".join(esc(x) for x in (proj.get("difficulty"), proj.get("time_estimate")) if x)
        no_code = ""
        if proj.get("no_code_version"):
            no_code = (f'<div style="padding:8px 0 0;font-family:{SERIF};font-size:14px;line-height:1.55;'
                       f'font-style:italic;color:{MUTED};">No code? {with_notes(proj["no_code_version"])}</div>')
        parts.append(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="background:{PAGE_2};border-left:3px solid {GOLD};"><tr><td style="padding:14px 16px;">'
            + label("Weekend project", f" &middot; {meta}" if meta else "")
            + f'<div style="padding:2px 0 6px;font-family:{SERIF};font-size:17px;font-weight:bold;color:{TEXT};">{esc(proj["title"])}</div>'
            + f'<div style="font-family:{SERIF};font-size:15px;line-height:1.6;color:{TEXT};">{with_notes(proj.get("description"))}</div>'
            + no_code + "</td></tr></table>"
        )
    checked, proven = p.get("claims_checked"), p.get("claims_supported")
    proof = f"&#10003; {proven} of {checked} lines proven by the abstract &nbsp;&middot;&nbsp; " if checked else ""
    parts.append(
        f'<div style="padding:16px 0 0;font-family:{SERIF};font-size:13px;color:{MUTED};">{proof}'
        f'<a href="{esc(p.get("url"))}" style="color:{RED};">Read the paper</a>'
        + (f' &nbsp;&middot;&nbsp; <a href="{esc(p["pdf_url"])}" style="color:{RED};">PDF</a>' if p.get("pdf_url") else "")
        + "</div>"
    )
    return (f'<tr><td style="padding:0 0 18px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'border="0" style="background:{PAGE};border-radius:3px;"><tr><td style="padding:26px 26px 24px;">'
            + "".join(parts) + "</td></tr></table></td></tr>")


def build_html(digest, config):
    em = config.get("email", {})
    papers = digest["papers"]
    day = nice_date(digest["date"], "%A, %d %B %Y")
    preheader = "Today: " + ", ".join(short_title(p["title"]) for p in papers) + ". Each one comes with a weekend project."
    links = [f'<a href="{esc(em.get("repo_url"))}" style="color:{GOLD};">Source on GitHub</a>'] if em.get("repo_url") else []
    if em.get("site_url"):
        links.insert(0, f'<a href="{esc(em["site_url"])}" style="color:{GOLD};">The website</a>')
    signed = f'Made by {esc(em.get("signed_by"))}' if em.get("signed_by") else ""
    footer_line = " &middot; ".join([x for x in [signed] + links if x])

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark light"><title>{esc(em.get("from_name", "The Scholar's Desk"))}</title></head>
<body style="margin:0;padding:0;background:{INK};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{esc(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{INK};">
<tr><td align="center" style="padding:30px 12px 40px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;">
<tr><td align="center" style="padding:0 0 4px;">
  <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
  <td width="54" height="54" align="center" valign="middle" style="width:54px;height:54px;border-radius:50%;background:#7A2620;border:3px solid #62201B;font-family:{SERIF};font-size:20px;font-style:italic;font-weight:bold;color:{GOLD_HI};">SD</td>
  </tr></table>
</td></tr>
<tr><td align="center" style="padding:14px 0 4px;font-family:{SERIF};font-size:13px;letter-spacing:4px;text-transform:uppercase;color:{GOLD};">The Scholar&rsquo;s Desk</td></tr>
<tr><td align="center" style="padding:0 0 8px;font-family:{SERIF};font-size:26px;font-style:italic;color:{PARCHMENT};">{esc(day)}</td></tr>
<tr><td align="center" style="padding:4px 20px 28px;font-family:{SERIF};font-size:15px;line-height:1.6;color:{DIM};">
Good morning. {count_words(len(papers))} came off the press. Every line below was checked against the paper&rsquo;s own abstract, and each one comes with a weekend project.</td></tr>
{"".join(paper_block(n, p) for n, p in enumerate(papers))}
<tr><td align="center" style="padding:16px 20px 0;font-family:{SERIF};font-size:13px;line-height:1.7;color:{DIM};">
Picked and written by Gemini, checked line by line by Groq, sent by a small robot for &#8377;0.<br>{footer_line}</td></tr>
<tr><td align="center" style="padding:18px 0 0;font-family:{SERIF};font-size:14px;font-style:italic;color:{GOLD};">See you tomorrow morning.</td></tr>
</table></td></tr></table>
</body></html>"""


def build_text(digest, config):
    """Plain-text copy, for email apps that don't show HTML."""
    em = config.get("email", {})
    plain = lambda s: re.sub(r"\s+", " ", s or "").strip()
    lines = ["THE SCHOLAR'S DESK", nice_date(digest["date"], "%A, %d %B %Y"), "",
             f"Good morning. {count_words(len(digest['papers']))}. Every line was checked against the paper's own abstract.", ""]
    for n, p in enumerate(digest["papers"]):
        proj = p.get("project_idea") or {}
        lines += [f"{ROMAN[n]}. {p['title']}", f"   {short_authors(p.get('authors'))} · {p.get('url', '')}"]
        for name, key in (("Why I picked it", "ranking_reason"), ("What they did", "explanation"), ("Why it matters", "why_it_matters")):
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
    lines += ["Picked and written by Gemini, checked line by line by Groq, sent by a small robot for Rs 0."]
    if em.get("repo_url"):
        lines.append(f"Source: {em['repo_url']}")
    return "\n".join(lines)


def build_subject(digest, config):
    template = config.get("email", {}).get("subject", "The Scholar's Desk · {date} · {count} papers")
    return template.format(date=nice_date(digest["date"], "%a %d %b"), count=len(digest["papers"]))


def send(subject, text, body_html, config):
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
        raise SystemExit("The digest has no papers, so there is nothing to send.")

    config = load_config(args.config)
    subject, body_html = build_subject(digest, config), build_html(digest, config)

    log.info(f"Subject: {subject}")
    if args.preview:
        out = folder / "email.html"
        out.write_text(body_html, encoding="utf-8")
        print(f"Preview saved to {out} ({len(body_html.encode('utf-8')) // 1024} KB). Open it in your browser.")
        return

    count = send(subject, build_text(digest, config), body_html, config)
    print(f"Sent the {date} email with {len(digest['papers'])} papers to {count} reader{'s' if count != 1 else ''}.")


if __name__ == "__main__":
    main()
