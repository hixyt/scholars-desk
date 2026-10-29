#!/usr/bin/env python3
"""
The Scholar's Desk - Step 3: Strict Fact-Checking & Verification
================================================================
1. Extracts claims ONLY from our text (why_picked / ranking_reason and explanation),
   one claim per sentence. Never adds claims from the abstract that we didn't write.
2. Strict verification: if the abstract does not clearly say it, marks it unsupported.
3. Writing style:
   - Plain language for a 2nd-year student who has never read a research paper.
   - Short sentences.
   - Technical terms explained in brackets [like this] the first time.
   - No hype words (crucial, essential, vital, powerful, game-changer, highly employable, cutting-edge).
   - No em dashes (—).
4. Canary mode (--canary):
   - Injects one clearly false sentence into each of the 5 drafts.
   - Runs the checker and reports how many of the 5 false sentences were caught.
   - Does NOT save canary results to digest.json.
5. Saves checked results to data/YYYY-MM-DD/digest.json (keeping digest_draft.json).

Total AI calls in this script: Exactly 1.
"""

import argparse
import json
import logging
import os
import re
import sys
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
logger = logging.getLogger("scholars-desk.verify")

# Distinct, obviously false canary sentences for --canary test mode
CANARY_SENTENCES = [
    "The authors proved this method by testing it on 50,000 live penguins wearing VR headsets.",
    "The system achieved 99.9% accuracy on a quantum computer from the year 2045.",
    "The method relies on an ancient alchemical formula discovered in 1342.",
    "The benchmark was conducted exclusively inside underwater microwave ovens at zero gravity.",
    "The researchers confirmed that this software eliminates 100% of all programming bugs in human history."
]


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

    if not groq_key:
        logger.error("No GROQ_API_KEY found in environment. verify.py requires Groq as an independent verifier.")
    else:
        logger.info("GROQ_API_KEY loaded successfully.")

    return gemini_key, groq_key


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from config.yaml."""
    path = Path(config_path)
    if not path.exists():
        return {
            "models": {
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


def split_into_sentences(text: str) -> List[str]:
    """Split a paragraph into individual clean sentences."""
    if not text:
        return []
    cleaned = re.sub(r"\s+", " ", text).strip()
    # Split on sentence terminals . ! ? followed by space or end
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [p.strip() for p in parts if p.strip()]


def call_groq(prompt: str, system_instruction: str, primary_model: str, api_key: str, fallback_model: Optional[str] = None) -> Tuple[str, str]:
    """Call Groq API with model fallback."""
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
        logger.info(f"Calling Groq verification model '{m}'...")
        payload = {
            "model": m,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,  # Low temperature for strict factual verification
            "response_format": {"type": "json_object"}
        }
        for attempt in (1, 2):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=60)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    return content, f"Groq ({m})"
                elif resp.status_code == 429 and attempt == 1:
                    logger.warning(f"Groq rate limit reached (429). Waiting 14s before retry...")
                    import time
                    time.sleep(14)
                else:
                    last_err = RuntimeError(f"Groq HTTP {resp.status_code}: {resp.text}")
                    logger.warning(f"Groq model '{m}' returned status {resp.status_code}: {resp.text}")
                    break
            except Exception as e:
                last_err = e
                logger.warning(f"Groq model '{m}' exception: {e}")
                break

    raise last_err if last_err else RuntimeError("Groq failed on all models.")


def verify_papers(draft_papers: List[dict], config: dict, groq_key: str, canary_mode: bool = False) -> Tuple[List[dict], str, Optional[Dict[str, Any]]]:
    """
    Executes exactly ONE AI call with Groq to strictly cross-check explanations against paper abstracts.
    Evaluates ONLY our own sentences (one claim per sentence).
    """
    logger.info("--- Verification Call 1/1: Strictly fact-checking draft against original abstracts via Groq ---")

    models_cfg = config.get("models", {})
    groq_primary = models_cfg.get("groq", "llama-3.3-70b-versatile")
    groq_fallback = models_cfg.get("groq_fallback", "openai/gpt-oss-120b")

    # Prepare sentence-by-sentence audit payload
    audit_items = []
    canary_tracking = {}

    for idx, p in enumerate(draft_papers):
        paper_id = p["id"]
        reason = p.get("ranking_reason", "").strip()
        explanation = p.get("explanation", "").strip()

        reason_sentences = split_into_sentences(reason)
        exp_sentences = split_into_sentences(explanation)

        # In canary mode, inject one clearly false sentence into each paper
        canary_sentence = None
        if canary_mode:
            canary_sentence = CANARY_SENTENCES[idx % len(CANARY_SENTENCES)]
            exp_sentences.append(canary_sentence)

        sentences_to_verify = []
        s_count = 1
        for s in reason_sentences:
            sentences_to_verify.append({
                "sentence_id": f"s{s_count}",
                "source": "ranking_reason",
                "text": s
            })
            s_count += 1

        canary_sid = None
        for s in exp_sentences:
            sid = f"s{s_count}"
            if canary_mode and s == canary_sentence:
                canary_sid = sid
            sentences_to_verify.append({
                "sentence_id": sid,
                "source": "explanation",
                "text": s
            })
            s_count += 1

        if canary_mode and canary_sentence:
            canary_tracking[paper_id] = (canary_sid, canary_sentence)

        audit_items.append({
            "id": paper_id,
            "title": p["title"],
            "abstract": p["abstract"],
            "sentences_to_verify": sentences_to_verify
        })

    system_instruction = (
        "You are an impartial, strict scientific fact-checker and undergraduate mentor.\n"
        "A student wrote short summaries of 5 research papers based on their abstracts.\n"
        "You are given each paper's abstract along with the exact sentences written by the student in 'sentences_to_verify'.\n\n"
        "CRITICAL RULES:\n"
        "1. ONLY evaluate the specific sentences provided in 'sentences_to_verify'. DO NOT invent or extract any other claims from the abstract.\n"
        "2. STRICT CHECK: A claim is supported (true) ONLY IF the abstract clearly and directly states it. If the abstract does not clearly say it, mark supported: false.\n"
        "3. For each sentence in sentences_to_verify, output:\n"
        "   - sentence_id: exact id matching input\n"
        "   - claim: exact sentence text\n"
        "   - supported: true or false\n"
        "   - reason: 1 brief sentence explaining why it is supported or unsupported according to the abstract.\n"
        "4. Output claims_checked (total count of sentences evaluated) and claims_supported (count of sentences where supported == true).\n"
        "5. Final Verified Text:\n"
        "   - verified_ranking_reason: the verified reason sentence. If unsupported, rewrite it so it is 100% grounded in the abstract.\n"
        "   - verified_explanation: the verified explanation sentences combined (2-3 sentences). Exclude or correct any unsupported claims.\n"
        "   - Writing style: Friendly senior talking to a 2nd-year student who has never read a research paper. Short sentences. Explain any technical term in brackets [like this] the first time (e.g. GUI [graphical user interface, like phone buttons and screens]). NO em dashes (—). NO hype words."
    )

    prompt = (
        f"Fact-check these 5 papers:\n\n"
        f"{json.dumps(audit_items, indent=2)}\n\n"
        "Return a JSON object with one key, \"papers\", holding exactly 5 objects matching this schema:\n"
        '{"papers": [\n'
        "  {\n"
        '    "id": "<paper id>",\n'
        '    "claims_checked": <int>,\n'
        '    "claims_supported": <int>,\n'
        '    "results": [\n'
        "      {\n"
        '        "sentence_id": "<s1, s2, etc>",\n'
        '        "claim": "<exact sentence text>",\n'
        '        "supported": true or false,\n'
        '        "reason": "<why supported or unsupported>"\n'
        "      }\n"
        "    ],\n"
        '    "verified_ranking_reason": "<grounded 1-line reason, plain words, brackets for technical terms, no hype, no em dashes>",\n'
        '    "verified_explanation": "<grounded 2-3 sentence explanation, plain words, brackets for technical terms, no hype, no em dashes>"\n'
        "  }\n"
        "]}"
    )

    raw_response, provider = call_groq(
        prompt=prompt,
        system_instruction=system_instruction,
        primary_model=groq_primary,
        api_key=groq_key,
        fallback_model=groq_fallback
    )

    parsed = extract_json_from_text(raw_response)
    if isinstance(parsed, dict):
        for val in parsed.values():
            if isinstance(val, list):
                parsed = val
                break

    if not isinstance(parsed, list):
        raise ValueError(f"Expected JSON list from Groq verification, got {type(parsed)}")

    # Handle both nested {"id": ..., "results": [...]} and flat [{"id": ..., "sentence_id": ..., ...}]
    paper_results = {p["id"]: [] for p in draft_papers}
    paper_reasons = {}
    paper_exps = {}

    for item in parsed:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("id", "")).strip()
        if pid not in paper_results:
            continue

        if "results" in item and isinstance(item["results"], list):
            for r in item["results"]:
                paper_results[pid].append(r)
            if item.get("verified_ranking_reason"):
                paper_reasons[pid] = item["verified_ranking_reason"]
            if item.get("verified_explanation"):
                paper_exps[pid] = item["verified_explanation"]
        elif "sentence_id" in item:
            sup = item.get("supported")
            if sup is None:
                sup = item.get("verdict")
            paper_results[pid].append({
                "sentence_id": item.get("sentence_id"),
                "claim": item.get("claim", ""),
                "supported": bool(sup),
                "reason": item.get("reason", "")
            })

    canary_results = {"caught": 0, "total": len(canary_tracking), "details": []} if canary_mode else None

    verified_papers = []
    for idx, p in enumerate(draft_papers):
        pid = p["id"]
        results_list = paper_results.get(pid, [])

        # Check canary detection if in canary mode
        if canary_mode and pid in canary_tracking:
            target_sid, fake_sent = canary_tracking[pid]
            caught_this = False
            for r in results_list:
                r_sid = str(r.get("sentence_id", "")).lower()
                r_claim = str(r.get("claim", "")).lower()

                # Find the injected sentence by its id or its exact text only
                is_canary = (
                    r_sid == str(target_sid).lower() or
                    fake_sent.lower() in r_claim
                )
                if is_canary:
                    if not r.get("supported", False):
                        caught_this = True
                    break

            if caught_this:
                canary_results["caught"] += 1
                canary_results["details"].append({"id": pid, "caught": True, "sentence": fake_sent})
            else:
                canary_results["details"].append({"id": pid, "caught": False, "sentence": fake_sent})

        claims_checked = len(results_list)
        claims_supported = sum(1 for c in results_list if c.get("supported", False))

        verified_exp = clean_plain_language(paper_exps.get(pid) or p.get("explanation", ""))
        verified_reason = clean_plain_language(paper_reasons.get(pid) or p.get("ranking_reason", ""))

        proj = dict(p.get("project_idea", {}))
        proj["title"] = clean_plain_language(proj.get("title", ""))
        proj["description"] = clean_plain_language(proj.get("description", ""))
        proj["no_code_version"] = clean_plain_language(proj.get("no_code_version", ""))

        v_paper = dict(p)
        v_paper["ranking_reason"] = verified_reason
        v_paper["explanation"] = verified_exp
        v_paper["claims_checked"] = claims_checked
        v_paper["claims_supported"] = claims_supported
        v_paper["claims"] = results_list
        v_paper["project_idea"] = proj
        v_paper["verified_by"] = provider

        verified_papers.append(v_paper)

    logger.info(f"Verification complete for all {len(verified_papers)} papers.")
    return verified_papers, provider, canary_results


def save_final_digest(papers: List[dict], date_str: str, verifier: str, output_root: str = "data") -> Path:
    """Save the final verified digest to data/YYYY-MM-DD/digest.json."""
    output_dir = Path(output_root) / date_str
    output_dir.mkdir(parents=True, exist_ok=True)
    digest_file = output_dir / "digest.json"

    digest_data = {
        "date": date_str,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "total_papers": len(papers),
        "verifier": verifier,
        "status": "verified",
        "papers": papers
    }

    with open(digest_file, "w", encoding="utf-8") as f:
        json.dump(digest_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved final verified digest to {digest_file.resolve()}")
    return digest_file


def main():
    parser = argparse.ArgumentParser(description="Strict fact-checking and verification for The Scholar's Desk.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml.")
    parser.add_argument("--date", default=None, help="Digest date in YYYY-MM-DD format.")
    parser.add_argument("--draft", default=None, help="Path to draft digest JSON file.")
    parser.add_argument("--data-dir", default="data", help="Root data directory.")
    parser.add_argument("--canary", action="store_true", help="Run in canary test mode (injects fake claims, does NOT save to digest.json).")
    args = parser.parse_args()

    date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    draft_path = Path(args.draft) if args.draft else Path(args.data_dir) / date_str / "digest_draft.json"

    print("=" * 75)
    print("  The Scholar's Desk - Step 3: Strict Fact-Checking & Verification")
    print(f"  Target Digest Date: {date_str}")
    print(f"  Input Draft File  : {draft_path}")
    print(f"  Mode              : {'CANARY TEST MODE' if args.canary else 'PRODUCTION VERIFICATION'}")
    print("=" * 75)

    if not draft_path.exists():
        logger.error(f"Draft file not found at {draft_path}. Please run rank.py first!")
        sys.exit(1)

    _, groq_key = load_environment()
    if not groq_key:
        logger.error("Missing GROQ_API_KEY. Verification requires Groq.")
        sys.exit(1)

    config = load_config(args.config)

    with open(draft_path, "r", encoding="utf-8") as f:
        draft_data = json.load(f)

    draft_papers = draft_data.get("papers", [])
    if not draft_papers:
        logger.error(f"No papers found in draft file {draft_path}.")
        sys.exit(1)

    logger.info(f"Loaded {len(draft_papers)} draft papers for verification.")

    # ONE AI call to verify
    verified_papers, verifier, canary_results = verify_papers(draft_papers, config, groq_key, canary_mode=args.canary)

    if args.canary:
        print("\n" + "=" * 75)
        print("  CANARY TEST RESULTS")
        print("=" * 75)
        caught = canary_results["caught"]
        total = canary_results["total"]
        score_pct = (caught / total) * 100 if total > 0 else 0
        print(f"  Canary Score: {caught} / {total} false sentences caught ({score_pct:.0f}%)")
        print("  (Note: Canary results are NOT saved to digest.json)")
        print("=" * 75 + "\n")

        for d in canary_results["details"]:
            status = "CAUGHT (MARKED NOT SUPPORTED)" if d["caught"] else "MISSED (MARKED SUPPORTED)"
            print(f"  [{status}] ID: {d['id']}")
            print(f"    Injected False Sentence: \"{d['sentence']}\"")
        print("\n" + "=" * 75 + "\n")
        return

    # Normal mode: Save final verified digest to data/YYYY-MM-DD/digest.json
    final_path = save_final_digest(verified_papers, date_str, verifier, output_root=args.data_dir)

    print("\n" + "=" * 75)
    print("  Final Fact-Checked Digest (Verified by Groq)")
    print(f"  Verified Digest Saved: {final_path}")
    print(f"  Unchecked Draft Kept : {draft_path}")
    print("=" * 75 + "\n")

    for i, p in enumerate(verified_papers, 1):
        print(f"[{i}] {p['title']}")
        print(f"    ID: {p['id']} | Sources: {', '.join(p.get('sources', []))}")
        print(f"    Topic: {', '.join(p.get('matched_topics', []))}")
        print(f"    Why Picked: {p.get('ranking_reason')}")
        print(f"\n    Explanation (Plain & Grounded):")
        print(f"    {p.get('explanation')}")

        proj = p.get("project_idea", {})
        print(f"\n    Weekend Project (Coded): {proj.get('title')} [{proj.get('difficulty')} | {proj.get('time_estimate')}]")
        print(f"    {proj.get('description')}")
        print(f"\n    No-Code Version (n8n / Make / Sheets):")
        print(f"    {proj.get('no_code_version')}")

        print(f"\n    Fact-Check Verification:")
        print(f"    Claims Supported: {p.get('claims_supported')} / {p.get('claims_checked')}")
        for c in p.get("claims", []):
            status = "SUPPORTED" if c.get("supported") else "NOT SUPPORTED"
            print(f"      - [{status}] {c.get('claim')}")
            if not c.get("supported"):
                print(f"        Reason: {c.get('reason')}")
        print("-" * 75 + "\n")


if __name__ == "__main__":
    main()
