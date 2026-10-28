#!/usr/bin/env python3
"""
The Scholar's Desk - Step 2: Paper Ranking & Writing
===================================================
1. Topic Balance: Selects at least 1 paper for each topic in config.yaml.
2. Writing for 2nd-Year Students:
   - Explains technical words in brackets [like this] the first time or uses simple words.
   - Written like a friendly senior student.
   - Short sentences.
   - No hype words (crucial, essential, vital, powerful, game-changer, highly employable, cutting-edge).
   - No em dashes (—).
3. Weekend Projects: Includes coded project idea and a no_code_version (n8n, Make, or Google Sheets).
4. Saves draft to data/YYYY-MM-DD/digest_draft.json.

Total AI calls in this script: Exactly 2.
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml
from dotenv import load_dotenv

# Fix Windows terminal encoding for UTF-8 characters
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("scholars-desk.rank")


def clean_plain_language(text: str) -> str:
    """Enforce plain language guidelines, strip em dashes, and replace hype words."""
    if not text:
        return ""
    text = text.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", ", ")
    text = text.replace("—", ", ").replace("–", ", ").replace(" -- ", ", ").replace("--", ", ")
    text = re.sub(r"\bcrucial\b", "important", text, flags=re.IGNORECASE)
    text = re.sub(r"\bessential\b", "key", text, flags=re.IGNORECASE)
    text = re.sub(r"\bvital\b", "helpful", text, flags=re.IGNORECASE)
    text = re.sub(r"\bpowerful\b", "effective", text, flags=re.IGNORECASE)
    text = re.sub(r"\bgame-?changers?\b", "big improvement", text, flags=re.IGNORECASE)
    text = re.sub(r"\bhighly employable\b", "useful for practical work", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcutting-?edge\b", "modern", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_environment() -> Tuple[Optional[str], Optional[str]]:
    """Load API keys safely from .env or API.env without logging or printing values."""
    current_dir = Path(__file__).resolve().parent
    env_file = current_dir / ".env"
    api_env_file = current_dir / "API.env"

    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
    elif api_env_file.exists():
        load_dotenv(dotenv_path=api_env_file)
    else:
        load_dotenv()

    gemini_key = os.getenv("GEMINI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")

    if not gemini_key and not groq_key:
        logger.error("No API keys found in environment. Ensure GEMINI_API_KEY or GROQ_API_KEY is in .env.")
    else:
        logger.info(f"API Keys loaded (Gemini: {'Yes' if gemini_key else 'No'}, Groq: {'Yes' if groq_key else 'No'}).")

    return gemini_key, groq_key


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from config.yaml."""
    path = Path(config_path)
    if not path.exists():
        logger.warning(f"Config file not found at {config_path}. Using default settings.")
        return {
            "topics": [
                {"name": "AI tools for non-programmers"},
                {"name": "LLM agents for everyday work"}
            ],
            "models": {
                "gemini": "gemini-3.5-flash-lite",
                "gemini_fallback": "gemini-flash-lite-latest",
                "groq": "llama-3.3-70b-versatile",
                "groq_fallback": "openai/gpt-oss-120b"
            }
        }
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def extract_json_from_text(text: str) -> Any:
    """Extract and parse JSON from an LLM response string."""
    cleaned = text.strip()
    if "```" in cleaned:
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()

    array_start = cleaned.find("[")
    array_end = cleaned.rfind("]")
    obj_start = cleaned.find("{")
    obj_end = cleaned.rfind("}")

    if array_start != -1 and (obj_start == -1 or array_start < obj_start):
        if array_end != -1:
            cleaned = cleaned[array_start:array_end + 1]
    elif obj_start != -1:
        if obj_end != -1:
            cleaned = cleaned[obj_start:obj_end + 1]

    return json.loads(cleaned)


def call_gemini(prompt: str, system_instruction: str, model_name: str, api_key: str, fallback_model: Optional[str] = None) -> str:
    """Call Google Gemini using google-genai SDK."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        temperature=0.3
    )

    models_to_try = [model_name]
    if fallback_model and fallback_model != model_name:
        models_to_try.append(fallback_model)

    last_err = None
    for m in models_to_try:
        try:
            logger.info(f"Calling Gemini model '{m}'...")
            response = client.models.generate_content(
                model=m,
                contents=prompt,
                config=config
            )
            return response.text
        except Exception as e:
            last_err = e
            logger.warning(f"Gemini call to model '{m}' failed: {e}")

    raise last_err if last_err else RuntimeError("Gemini failed on all models.")


def call_groq(prompt: str, system_instruction: str, primary_model: str, api_key: str, fallback_model: Optional[str] = None) -> str:
    """Call Groq API as backup."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    models_to_try = [primary_model]
    if fallback_model and fallback_model != primary_model:
        models_to_try.append(fallback_model)

    last_err = None
    for m in models_to_try:
        logger.info(f"Calling Groq model '{m}'...")
        payload = {
            "model": m,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "response_format": {"type": "json_object"}
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=45)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            else:
                last_err = RuntimeError(f"Groq HTTP {resp.status_code}: {resp.text}")
                logger.warning(f"Groq model '{m}' returned status {resp.status_code}: {resp.text}")
        except Exception as e:
            last_err = e
            logger.warning(f"Groq model '{m}' exception: {e}")

    raise last_err if last_err else RuntimeError("Groq failed on all models.")


def execute_ai_call_with_fallback(
    prompt: str,
    system_instruction: str,
    call_label: str,
    config: dict,
    gemini_key: Optional[str],
    groq_key: Optional[str]
) -> Tuple[Any, str]:
    """Execute AI call with retry once and Groq backup."""
    models_cfg = config.get("models", {})
    gemini_model = models_cfg.get("gemini", "gemini-3.5-flash-lite")
    gemini_fallback = models_cfg.get("gemini_fallback", "gemini-flash-lite-latest")
    groq_model = models_cfg.get("groq", "llama-3.3-70b-versatile")
    groq_fallback = models_cfg.get("groq_fallback", "openai/gpt-oss-120b")

    raw_response = None
    used_provider = None

    if gemini_key:
        for attempt in (1, 2):
            try:
                logger.info(f"[{call_label}] Gemini attempt {attempt}/2...")
                raw_response = call_gemini(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    model_name=gemini_model,
                    api_key=gemini_key,
                    fallback_model=gemini_fallback
                )
                used_provider = f"Gemini ({gemini_model})"
                break
            except Exception as e:
                logger.warning(f"[{call_label}] Gemini attempt {attempt} failed: {e}")
                if attempt == 1:
                    logger.info("Waiting 3.0s before retrying Gemini once...")
                    time.sleep(3.0)

    if raw_response is None:
        if not groq_key:
            raise RuntimeError("Gemini failed and no GROQ_API_KEY is available as backup.")

        logger.info(f"[{call_label}] Switching to Groq backup ({groq_model})...")
        try:
            raw_response = call_groq(
                prompt=prompt,
                system_instruction=system_instruction,
                primary_model=groq_model,
                api_key=groq_key,
                fallback_model=groq_fallback
            )
            used_provider = f"Groq ({groq_model})"
        except Exception as e:
            logger.error(f"[{call_label}] Groq backup also failed: {e}")
            raise RuntimeError(f"All AI providers failed for {call_label}.") from e

    parsed = extract_json_from_text(raw_response)
    logger.info(f"[{call_label}] Successfully received and parsed JSON using {used_provider}.")
    return parsed, used_provider


def rank_and_select_papers(papers: List[dict], config: dict, gemini_key: Optional[str], groq_key: Optional[str]) -> Tuple[List[dict], str]:
    """
    AI Call 1:
    Select 5 papers with topic balance (at least 1 per configured topic if available),
    written in plain language with no hype words and no em dashes.
    """
    logger.info(f"--- AI Call 1/2: Selecting top 5 from {len(papers)} candidate papers with topic balance ---")

    topic_items = config.get("topics", [])
    topic_names = []
    for item in topic_items:
        if isinstance(item, dict):
            topic_names.append(item.get("name", ""))
        elif isinstance(item, str):
            topic_names.append(item)
    topic_names = [t for t in topic_names if t]

    paper_catalog = []
    for p in papers:
        paper_catalog.append({
            "id": p["id"],
            "title": p["title"],
            "abstract": p["abstract"][:600],
            "categories": p.get("categories", []),
            "matched_topics": p.get("matched_topics", [])
        })

    topics_list_str = "\n".join([f"- {t}" for t in topic_names])

    system_instruction = (
        "You are a friendly senior student helping a 2nd-year B.Tech AI student choose research papers to read.\n"
        "Your student has never read a research paper before.\n"
        "Target topics:\n"
        f"{topics_list_str}\n\n"
        "Rules:\n"
        "1. Topic Balance: You MUST pick at least 1 paper for each topic that has matching candidate papers in the list.\n"
        "   Fill the remaining slots with the most practical papers.\n"
        "2. Plain Language for Beginners:\n"
        "   - Write like a friendly senior student.\n"
        "   - Use short sentences.\n"
        "   - Explain any technical word in brackets the first time you use it (for example: GUI [graphical user interface, like phone apps and buttons], or LLM [large language model, an AI that understands text]), or replace it with a simple everyday word.\n"
        "   - NEVER use em dashes (—). Use a period or comma instead.\n"
        "   - NEVER use hype words like: crucial, essential, vital, powerful, game-changer, highly employable, cutting-edge.\n"
        "   - Give a clean, grounded one-line reason for each chosen paper."
    )

    prompt = (
        f"Here are {len(paper_catalog)} candidate research papers:\n\n"
        f"{json.dumps(paper_catalog, indent=1)}\n\n"
        "Select exactly 5 papers following the topic balance rule (at least 1 paper per topic if available).\n"
        "Return a JSON array with exactly 5 objects matching this schema:\n"
        "[\n"
        "  {\n"
        '    "id": "<paper id from list>",\n'
        '    "reason": "<short one-line reason in plain words, short sentences, technical terms explained in brackets, no hype, no em dashes>"\n'
        "  }\n"
        "]"
    )

    result, provider = execute_ai_call_with_fallback(
        prompt=prompt,
        system_instruction=system_instruction,
        call_label="Call 1: Balanced Paper Selection",
        config=config,
        gemini_key=gemini_key,
        groq_key=groq_key
    )

    if isinstance(result, dict):
        for val in result.values():
            if isinstance(val, list):
                result = val
                break

    if not isinstance(result, list):
        raise ValueError(f"Expected JSON list from Call 1, got {type(result)}")

    paper_map = {p["id"]: p for p in papers}
    selected_papers = []

    for item in result:
        pid = str(item.get("id", "")).strip()
        reason = clean_plain_language(str(item.get("reason", "")).strip())
        if pid in paper_map:
            p_copy = dict(paper_map[pid])
            p_copy["ranking_reason"] = reason
            selected_papers.append(p_copy)

    # Programmatic enforcement of topic balance
    selected_topics = set()
    for p in selected_papers:
        for t in p.get("matched_topics", []):
            selected_topics.add(t)

    for req_topic in topic_names:
        if req_topic not in selected_topics:
            candidates_for_topic = [p for p in papers if req_topic in p.get("matched_topics", [])]
            if candidates_for_topic:
                candidate_to_add = None
                for c in candidates_for_topic:
                    if not any(sp["id"] == c["id"] for sp in selected_papers):
                        candidate_to_add = c
                        break
                if candidate_to_add:
                    logger.info(f"Enforcing topic balance: Adding paper for '{req_topic}': {candidate_to_add['title'][:50]}")
                    c_copy = dict(candidate_to_add)
                    c_copy["ranking_reason"] = f"Shows how to make practical {req_topic} accessible without complex code."
                    if len(selected_papers) >= 5:
                        selected_papers[-1] = c_copy
                    else:
                        selected_papers.append(c_copy)
                    selected_topics.add(req_topic)

    # Ensure exactly 5 papers
    if len(selected_papers) < 5:
        seen_ids = {p["id"] for p in selected_papers}
        for cand in papers:
            if cand["id"] not in seen_ids:
                cand_copy = dict(cand)
                cand_copy["ranking_reason"] = "A practical paper for building modern AI assistants."
                selected_papers.append(cand_copy)
                seen_ids.add(cand["id"])
                if len(selected_papers) >= 5:
                    break

    selected_5 = selected_papers[:5]
    logger.info("AI Call 1 successfully selected 5 balanced papers.")
    return selected_5, provider


def deep_dive_papers(selected_papers: List[dict], config: dict, gemini_key: Optional[str], groq_key: Optional[str]) -> Tuple[List[dict], str]:
    """
    AI Call 2:
    Writes plain language explanations, student relevance, and weekend project ideas
    with both code and no_code_version (n8n, Make, or Google Sheets).
    Explains technical terms in brackets [like this] the first time.
    No hype words, no em dashes, short sentences.
    """
    logger.info("--- AI Call 2/2: Generating plain explanations & weekend projects (with no-code versions) ---")

    input_papers = []
    for p in selected_papers:
        input_papers.append({
            "id": p["id"],
            "title": p["title"],
            "abstract": p["abstract"],
            "reason": p.get("ranking_reason", "")
        })

    system_instruction = (
        "You are a friendly senior student mentoring a 2nd-year B.Tech AI student who has never read a research paper.\n"
        "For each paper, write clear, grounded learning material in simple English.\n\n"
        "Writing Style Rules:\n"
        "- Explain any technical word in brackets the first time you use it (for example: GUI [graphical user interface, like phone apps and buttons], or LLM [large language model, an AI that understands text], or state machine [a program that moves between fixed steps]).\n"
        "- Use short sentences.\n"
        "- NEVER use em dashes (—). Use a period or comma instead.\n"
        "- NEVER use hype words like: crucial, essential, vital, powerful, game-changer, highly employable, cutting-edge.\n\n"
        "Required Fields per paper:\n"
        "1. explanation: Exactly 2 to 3 short sentences explaining what the paper did in simple everyday words.\n"
        "2. why_it_matters: 1 to 2 short sentences on why this helps a 2nd-year student understand practical AI.\n"
        "3. project_idea:\n"
        "   - title: Short, catchy project name.\n"
        "   - description: 2 short sentences on what code to write over the weekend.\n"
        "   - difficulty: Must be strictly 'Easy' or 'Medium'.\n"
        "   - time_estimate: e.g. '3-4 hours' or '4-5 hours'.\n"
        "   - no_code_version: 1 to 2 sentences explaining how a student can build the same idea using n8n, Make, or Google Sheets without writing code."
    )

    prompt = (
        f"Analyze these 5 papers:\n\n"
        f"{json.dumps(input_papers, indent=2)}\n\n"
        "Return a JSON array containing exactly 5 objects matching this schema:\n"
        "[\n"
        "  {\n"
        '    "id": "<paper id>",\n'
        '    "explanation": "<2-3 short sentences, plain words, technical terms in brackets, no hype, no em dashes>",\n'
        '    "why_it_matters": "<1-2 short sentences, plain words, no hype, no em dashes>",\n'
        '    "project_idea": {\n'
        '      "title": "<short project title>",\n'
        '      "description": "<2 short sentences of what code to build>",\n'
        '      "difficulty": "Easy" or "Medium",\n'
        '      "time_estimate": "<e.g. 3-4 hours>",\n'
        '      "no_code_version": "<1-2 sentences using n8n, Make, or Google Sheets>"\n'
        "    }\n"
        "  }\n"
        "]"
    )

    result, provider = execute_ai_call_with_fallback(
        prompt=prompt,
        system_instruction=system_instruction,
        call_label="Call 2: Deep Dive & No-Code Projects",
        config=config,
        gemini_key=gemini_key,
        groq_key=groq_key
    )

    if isinstance(result, dict):
        for val in result.values():
            if isinstance(val, list):
                result = val
                break

    if not isinstance(result, list):
        raise ValueError(f"Expected JSON list from Call 2, got {type(result)}")

    deep_dive_map = {str(item.get("id", "")).strip(): item for item in result}

    final_papers = []
    for p in selected_papers:
        pid = p["id"]
        details = deep_dive_map.get(pid, {})

        explanation = clean_plain_language(details.get("explanation", "").strip() or "This paper shows how to build automated workflows with language models.")
        why_it_matters = clean_plain_language(details.get("why_it_matters", "").strip() or "It helps you see how real software connects models to tools.")

        proj = details.get("project_idea", {})
        if not isinstance(proj, dict):
            proj = {}

        diff = proj.get("difficulty", "Medium")
        if diff not in ["Easy", "Medium"]:
            diff = "Medium"

        title = clean_plain_language(proj.get("title", f"Hands-on {p['title'][:25]} Mini Project"))
        desc = clean_plain_language(proj.get("description", "Build a small Python script that tests this workflow on sample inputs."))
        no_code = clean_plain_language(proj.get("no_code_version", "Create a Make or n8n workflow with a webhook trigger that sends user inputs to an LLM module and records responses in Google Sheets."))

        project_idea = {
            "title": title,
            "description": desc,
            "difficulty": diff,
            "time_estimate": proj.get("time_estimate", "3-4 hours"),
            "no_code_version": no_code
        }

        merged = dict(p)
        merged["explanation"] = explanation
        merged["why_it_matters"] = why_it_matters
        merged["project_idea"] = project_idea
        final_papers.append(merged)

    logger.info("AI Call 2 deep dive processing complete.")
    return final_papers, provider


def save_draft_digest(papers: List[dict], date_str: str, providers_used: List[str], output_root: str = "data") -> Path:
    """Save the unchecked draft to data/YYYY-MM-DD/digest_draft.json."""
    output_dir = Path(output_root) / date_str
    output_dir.mkdir(parents=True, exist_ok=True)
    draft_file = output_dir / "digest_draft.json"

    draft_data = {
        "date": date_str,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ai_calls_made": 2,
        "providers_used": providers_used,
        "total_selected": len(papers),
        "status": "draft_unchecked",
        "papers": papers
    }

    with open(draft_file, "w", encoding="utf-8") as f:
        json.dump(draft_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved draft digest to {draft_file.resolve()}")
    return draft_file


def main():
    parser = argparse.ArgumentParser(description="Rank and explain top AI papers (Step 2/3 draft).")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml.")
    parser.add_argument("--date", default=None, help="Digest date in YYYY-MM-DD format.")
    parser.add_argument("--raw", default=None, help="Path to raw.json file.")
    parser.add_argument("--data-dir", default="data", help="Root data directory.")
    args = parser.parse_args()

    date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    raw_path = Path(args.raw) if args.raw else Path(args.data_dir) / date_str / "raw.json"

    print("=" * 75)
    print("  The Scholar's Desk - Ranker (Plain Language & Topic Balance)")
    print(f"  Target Digest Date: {date_str}")
    print(f"  Input Raw File    : {raw_path}")
    print("=" * 75)

    if not raw_path.exists():
        logger.error(f"Raw data file not found at {raw_path}. Run fetch.py first!")
        sys.exit(1)

    gemini_key, groq_key = load_environment()
    config = load_config(args.config)

    with open(raw_path, "r", encoding="utf-8") as f:
        raw_papers = json.load(f)

    providers_used = []

    selected_5, p1 = rank_and_select_papers(raw_papers, config, gemini_key, groq_key)
    providers_used.append(p1)

    final_5, p2 = deep_dive_papers(selected_5, config, gemini_key, groq_key)
    providers_used.append(p2)

    draft_path = save_draft_digest(final_5, date_str, providers_used, output_root=args.data_dir)

    print("\n" + "=" * 75)
    print("  Draft Digest Generated (Total AI Calls: 2)")
    print(f"  Draft Saved to: {draft_path}")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
