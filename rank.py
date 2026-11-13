#!/usr/bin/env python3
"""
Step 2: pick today's papers and write about them.

AI call 1 picks about one paper per topic from raw.json (settings.picks_per_day in total).
AI call 2 writes a plain explanation, why it matters, and a weekend project
(with a no-code version) for each pick.
Gemini does the writing. If both Gemini models fail, Groq is the backup.
Saves data/YYYY-MM-DD/digest_draft.json, which verify.py then fact-checks.
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from common import call_groq, clean_text, load_config, load_keys, log, parse_json_list, run

STYLE_RULES = (
    "- Write like a friendly senior student. Use short sentences.\n"
    "- Start with what the paper does or shows. No greetings or filler such as 'Hey!', 'Check out', 'super cool' or 'neat'.\n"
    "- Explain any technical word in brackets the first time you use it "
    "(for example: GUI [graphical user interface, like phone apps and buttons], "
    "LLM [large language model, an AI that understands text]), or use a simple everyday word instead.\n"
    "- NEVER use em dashes. Use a period or comma instead.\n"
    "- NEVER use hype words like: crucial, essential, vital, powerful, game-changer, highly employable, cutting-edge.\n"
)

# Gemini says these when it is overloaded for a while. Waiting a bit usually fixes it.
BUSY_SIGNS = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "high demand", "overloaded")


gemini_busy = False  # True once both Gemini models stayed busy, so the next call goes straight to Groq


def ask_ai(system, prompt, config, gemini_key, groq_key, groq_prompt=None):
    """Try Gemini first, then Groq. Returns (parsed JSON list, model used).
    groq_prompt is a shorter version of the prompt for Groq, whose free plan allows 8,000 tokens a minute."""
    global gemini_busy
    models = config["models"]

    if gemini_key and not gemini_busy:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=gemini_key)
        settings = types.GenerateContentConfig(
            system_instruction=system, response_mime_type="application/json", temperature=0.3)
        all_busy = True
        for model in (models["gemini"], models["gemini_fallback"]):
            for wait in (0, 30, 90):
                if wait:
                    log.info(f"Trying Gemini ({model}) again in {wait}s")
                    time.sleep(wait)
                try:
                    log.info(f"Asking Gemini ({model})...")
                    reply = client.models.generate_content(model=model, contents=prompt, config=settings)
                    return parse_json_list(reply.text), f"Gemini ({model})"
                except Exception as e:
                    if not any(sign in str(e) for sign in BUSY_SIGNS):
                        log.warning(f"Gemini ({model}) failed: {e}")
                        all_busy = False
                        break  # a wrong model name or a bad reply won't fix itself by waiting
                    log.info(f"Gemini ({model}) is busy: {str(e)[:120]}")
            else:
                log.warning(f"Gemini ({model}) was still busy after 3 tries")
        gemini_busy = all_busy

    if not groq_key:
        raise RuntimeError("Gemini failed and there is no GROQ_API_KEY to fall back on")
    reply, model = call_groq([models["groq"], models["groq_fallback"]], system, groq_prompt or prompt, groq_key)
    return parse_json_list(reply), f"Groq ({model})"


def score(p):
    """A rough first sort before the AI looks: trending on Hugging Face, then how many keywords matched."""
    hf = p.get("huggingface") if isinstance(p.get("huggingface"), dict) else {}
    return (hf.get("upvotes") or 0) * 3 + len(p.get("matched_keywords") or []) + len(p.get("matched_topics") or [])


def shortlist(papers, topics, per_topic):
    """The best few papers of every topic, so a busy day still fits in one AI call."""
    ranked = sorted(papers, key=score, reverse=True)
    keep = {}
    for topic in topics:
        for p in [p for p in ranked if topic in p.get("matched_topics", [])][:per_topic]:
            keep.setdefault(p["id"], p)
    return [p for p in ranked if p["id"] in keep]


def pick_papers(papers, config, keys):
    """AI call 1: pick about one paper per topic (settings.picks_per_day in total)."""
    topics = [t["name"] for t in config["topics"]]
    want = min(config["settings"].get("picks_per_day", 5), len(papers))  # a slow day can have fewer papers

    def catalog(per_topic, cut):
        return [{"id": p["id"], "title": p["title"], "abstract": p["abstract"][:cut],
                 "matched_topics": p.get("matched_topics", [])} for p in shortlist(papers, topics, per_topic)]

    system = (
        "You are a friendly senior student helping a 2nd-year B.Tech AI student choose research papers to read. "
        "The student has never read a research paper before.\n"
        "Target topics:\n" + "\n".join(f"- {t}" for t in topics) + "\n\n"
        "Rules:\n"
        "- Cover as many different topics as you can. One paper per topic is ideal, for every topic that has "
        "papers in the list. Fill any other slots with the most practical papers.\n"
        + STYLE_RULES +
        "- Give a short, grounded one-line reason for each paper."
    )

    def ask(cards):
        return (f"Here are {len(cards)} candidate papers:\n\n{json.dumps(cards, ensure_ascii=False)}\n\n"
                f"Pick exactly {want}. Return a JSON object with a list of {want} picks:\n"
                '{"papers": [{"id": "<paper id from the list>", "reason": "<one short line>"}]}')

    picks, model = ask_ai(system, ask(catalog(20, 500)), config, *keys, groq_prompt=ask(catalog(5, 220)))

    by_id = {p["id"]: p for p in papers}
    chosen = []
    for item in picks:
        pid = str(item.get("id", "")).strip()
        if pid in by_id and pid not in {p["id"] for p in chosen}:
            chosen.append(dict(by_id[pid], ranking_reason=clean_text(item.get("reason", ""))))
    chosen = chosen[:want]
    if len(chosen) < want:
        log.warning(f"The AI returned only {len(chosen)} valid picks out of {want}")

    # In case the AI skipped a topic that had papers: add its best paper, and if the list is full,
    # drop a pick whose topics are all covered by the other picks anyway.
    def covered(items):
        return {t for p in items for t in p.get("matched_topics", [])}

    for topic in topics:
        if topic in covered(chosen):
            continue
        chosen_ids = {p["id"] for p in chosen}
        extra = next((p for p in sorted(papers, key=score, reverse=True)
                      if topic in p.get("matched_topics", []) and p["id"] not in chosen_ids), None)
        if not extra:
            continue
        if len(chosen) >= want:
            spare = next((k for k in range(len(chosen) - 1, -1, -1)
                          if set(chosen[k].get("matched_topics", [])) <= covered(chosen[:k] + chosen[k + 1:])), None)
            if spare is None:
                continue
            chosen.pop(spare)
        log.info(f"No pick for '{topic}', adding: {extra['title'][:60]}")
        chosen.append(dict(extra, ranking_reason=""))  # no made-up reason; the checker would only strike it

    return chosen, model


def write_details(chosen, config, keys):
    """AI call 2: explanation, why it matters and a weekend project for each paper."""
    papers_in = [{"id": p["id"], "title": p["title"], "abstract": p["abstract"],
                  "reason": p.get("ranking_reason", "")} for p in chosen]

    system = (
        "You are a friendly senior student mentoring a 2nd-year B.Tech AI student who has never read a research paper. "
        "For each paper, write clear, grounded learning material in simple English.\n\n"
        "Style rules:\n" + STYLE_RULES + "\n"
        "Fields for each paper:\n"
        "1. explanation: 2 to 3 short sentences on what the paper did, in simple everyday words.\n"
        "2. why_it_matters: 1 to 2 short sentences on why this helps a 2nd-year student understand practical AI.\n"
        "3. project_idea:\n"
        "   - title: short project name\n"
        "   - description: 2 short sentences on what to code over the weekend\n"
        "   - difficulty: 'Easy' or 'Medium'\n"
        "   - time_estimate: for example '3-4 hours'\n"
        "   - no_code_version: 1 to 2 sentences on building the same idea with n8n, Make or Google Sheets, without code"
    )
    prompt = (
        f"Write about these {len(papers_in)} papers:\n\n{json.dumps(papers_in, ensure_ascii=False)}\n\n"
        "Return a JSON object with one entry per paper in its list:\n"
        '{"papers": [{"id": "<paper id>", "explanation": "...", "why_it_matters": "...", '
        '"project_idea": {"title": "...", "description": "...", "difficulty": "Easy or Medium", '
        '"time_estimate": "...", "no_code_version": "..."}}]}'
    )
    details, model = ask_ai(system, prompt, config, *keys)

    by_id = {str(d.get("id", "")).strip(): d for d in details}
    papers = []
    for p in chosen:
        d = by_id.get(p["id"])
        if not d or not d.get("explanation"):
            log.warning(f"No write-up came back for {p['id']}, leaving it out")
            continue
        project = d.get("project_idea") or {}
        papers.append(dict(
            p,
            explanation=clean_text(d["explanation"]),
            why_it_matters=clean_text(d.get("why_it_matters", "")),
            project_idea={
                "title": clean_text(project.get("title", "")),
                "description": clean_text(project.get("description", "")),
                "difficulty": project.get("difficulty") if project.get("difficulty") in ("Easy", "Medium") else "Medium",
                "time_estimate": project.get("time_estimate", ""),
                "no_code_version": clean_text(project.get("no_code_version", "")),
            },
        ))
    return papers, model


def main():
    parser = argparse.ArgumentParser(description="Pick today's papers and write about them.")
    parser.add_argument("--date", help="YYYY-MM-DD (default: today in UTC)")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    folder = Path(args.data_dir) / date
    raw_path = folder / "raw.json"
    if not raw_path.exists():
        raise SystemExit(f"{raw_path} not found. Run fetch.py first.")

    config = load_config(args.config)
    keys = load_keys()
    with open(raw_path, encoding="utf-8") as f:
        papers = json.load(f)
    log.info(f"Ranking {len(papers)} papers for {date}")

    if not papers:  # a quiet day: save an empty draft so the next steps know
        empty = {"date": date, "generated_at": datetime.now(timezone.utc).isoformat(), "providers_used": [],
                 "status": "no_papers", "papers": []}
        with open(folder / "digest_draft.json", "w", encoding="utf-8") as f:
            json.dump(empty, f, indent=2)
        print("No new papers matched my topics today, so there is nothing to pick.")
        return

    chosen, model1 = pick_papers(papers, config, keys)
    final, model2 = write_details(chosen, config, keys)

    draft = {
        "date": date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "providers_used": [model1, model2],
        "status": "draft_unchecked",
        "papers": final,
    }
    draft_path = folder / "digest_draft.json"
    with open(draft_path, "w", encoding="utf-8") as f:
        json.dump(draft, f, indent=2, ensure_ascii=False)

    print(f"\nPicked {len(final)} papers (written by {model2}):")
    for i, p in enumerate(final, 1):
        print(f"  {i}. {p['title']}")
    print(f"\nSaved draft to {draft_path}")


if __name__ == "__main__":
    run(main)
