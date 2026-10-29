#!/usr/bin/env python3
"""
The Scholar's Desk - Step 3: Strict Fact-Checking & Verification
================================================================
1. Extracts claims ONLY from our text (why_picked / ranking_reason and explanation),
   one claim per sentence. Never adds claims from the abstract that we didn't write.
2. Strict verification: if the abstract does not clearly say it, marks it unsupported.
   The checker must also copy the exact words from the abstract that prove each sentence,
   and our code confirms those words really are there. No proof, no "supported".
   Any sentence the checker skips counts as not supported.
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

Total AI calls in this script: 1, plus 1 small follow-up only if the checker skipped sentences.
"""

import argparse
import json
import logging
import os
import random
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
                "groq": "openai/gpt-oss-120b",
                "groq_fallback": "openai/gpt-oss-20b"
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


def to_bool(value: Any) -> bool:
    """The AI sometimes writes false as text ("false"). Turn any form into a real True/False."""
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "supported")
    return bool(value)


def normalize_for_match(text: str) -> str:
    """Lowercase and keep only letters and numbers, so small punctuation changes don't matter."""
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def evidence_in_abstract(evidence: str, abstract: str, min_words: int = 4) -> bool:
    """
    The checker must copy the words from the abstract that prove a sentence.
    Here our own code confirms those words really are in the abstract.
    A quote with "..." in it is split, and every part must be found.
    """
    parts = [normalize_for_match(p) for p in re.split(r"\.\.\.|\u2026", evidence or "")]
    parts = [p for p in parts if p]
    if not parts or sum(len(p.split()) for p in parts) < min_words:
        return False
    abstract_norm = normalize_for_match(abstract)
    return all(p in abstract_norm for p in parts)


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


CHECKER_INSTRUCTION = (
    "You are an impartial, strict scientific fact-checker and undergraduate mentor.\n"
    "A student wrote short summaries of research papers based on their abstracts.\n"
    "You are given each paper's abstract along with the exact sentences written by the student in 'sentences_to_verify'.\n\n"
    "CRITICAL RULES:\n"
    "1. ONLY evaluate the specific sentences provided in 'sentences_to_verify'. DO NOT invent or extract any other claims from the abstract.\n"
    "2. Give a verdict for EVERY sentence, including sentences that look wrong or silly. Never skip or drop a sentence. "
    "A wrong sentence gets supported: false, it is not removed.\n"
    "3. STRICT CHECK: A claim is supported (true) ONLY IF the abstract clearly and directly states it. If the abstract does not clearly say it, mark supported: false.\n"
    "   Judge every sentence on its own. If a sentence adds ANY detail the abstract does not mention (a number, date, place, tool, test or result), it is NOT supported, even if the rest sounds right.\n"
    "4. For each sentence in sentences_to_verify, output:\n"
    "   - sentence_id: exact id matching input\n"
    "   - claim: exact sentence text\n"
    "   - supported: true or false (JSON boolean, not text)\n"
    "   - evidence: the exact words copied from the abstract that prove the sentence. Copy them without changing anything. If no words in the abstract prove it, write \"\" and set supported: false.\n"
    "   - reason: 1 brief sentence explaining why it is supported or unsupported according to the abstract.\n"
    "5. Final Verified Text:\n"
    "   - verified_ranking_reason: the verified reason sentence. If unsupported, rewrite it so it is 100% grounded in the abstract.\n"
    "   - verified_explanation: the verified explanation sentences combined (2-3 sentences). Leave out or correct any unsupported claims HERE, but still list every sentence in results.\n"
    "   - Writing style: Friendly senior talking to a 2nd-year student who has never read a research paper. Short sentences. Explain any technical term in brackets [like this] the first time (e.g. GUI [graphical user interface, like phone buttons and screens]). NO em dashes. NO hype words."
)


def build_checker_prompt(audit_items: List[dict]) -> str:
    """Write the message for the checker. It says exactly how many verdicts we expect."""
    total = sum(len(item["sentences_to_verify"]) for item in audit_items)
    return (
        f"Fact-check these {len(audit_items)} papers. There are {total} sentences in total, "
        f"so the results lists must contain {total} verdicts altogether, one for every sentence_id.\n\n"
        f"{json.dumps(audit_items, indent=2)}\n\n"
        f"Return a JSON object with one key, \"papers\", holding exactly {len(audit_items)} objects matching this schema:\n"
        '{"papers": [\n'
        "  {\n"
        '    "id": "<paper id, copied exactly>",\n'
        '    "results": [\n'
        "      {\n"
        '        "sentence_id": "<s1, s2, etc>",\n'
        '        "claim": "<exact sentence text>",\n'
        '        "supported": true or false,\n'
        '        "evidence": "<exact words copied from the abstract, or empty>",\n'
        '        "reason": "<why supported or unsupported>"\n'
        "      }\n"
        "    ],\n"
        '    "verified_ranking_reason": "<grounded 1-line reason, plain words, brackets for technical terms, no hype, no em dashes>",\n'
        '    "verified_explanation": "<grounded 2-3 sentence explanation, plain words, brackets for technical terms, no hype, no em dashes>"\n'
        "  }\n"
        "]}"
    )


def parse_checker_reply(raw_response: str, asked_ids: List[str]) -> Tuple[Dict[str, list], Dict[str, str], Dict[str, str]]:
    """
    Read the checker's JSON reply and sort the verdicts by paper.
    The AI may write the paper id a little differently (e.g. "2610.12345v1"),
    so we also accept an id that contains ours, and finally fall back to the order we asked in.
    """
    parsed = extract_json_from_text(raw_response)
    if isinstance(parsed, dict):
        for val in parsed.values():
            if isinstance(val, list):
                parsed = val
                break
    if not isinstance(parsed, list):
        raise ValueError(f"Expected JSON list from Groq verification, got {type(parsed)}")

    results = {pid: [] for pid in asked_ids}
    reasons, explanations = {}, {}
    for position, item in enumerate(parsed):
        if not isinstance(item, dict):
            continue
        returned_id = str(item.get("id", "")).strip()
        pid = next((d for d in asked_ids if d == returned_id), None)
        if pid is None:
            pid = next((d for d in asked_ids if d and d in returned_id), None)
        if pid is None and position < len(asked_ids):
            pid = asked_ids[position]
        if pid is None:
            continue

        if isinstance(item.get("results"), list):
            results[pid].extend(r for r in item["results"] if isinstance(r, dict))
            if item.get("verified_ranking_reason"):
                reasons[pid] = item["verified_ranking_reason"]
            if item.get("verified_explanation"):
                explanations[pid] = item["verified_explanation"]
        elif "sentence_id" in item:
            results[pid].append(item)
    return results, reasons, explanations


def find_missing(audit_items: List[dict], results: Dict[str, list]) -> List[dict]:
    """Return audit items holding only the sentences the checker gave no verdict for."""
    missing_items = []
    for item in audit_items:
        got = {str(r.get("sentence_id", "")).strip().lower() for r in results.get(item["id"], [])}
        missing = [s for s in item["sentences_to_verify"] if s["sentence_id"].lower() not in got]
        if missing:
            missing_items.append(dict(item, sentences_to_verify=missing))
    return missing_items


def verify_papers(draft_papers: List[dict], config: dict, groq_key: str, canary_mode: bool = False) -> Tuple[List[dict], str, Optional[Dict[str, Any]]]:
    """
    Uses Groq to strictly cross-check our sentences against the paper abstracts.
    Normally ONE AI call. If the checker skips any sentence, we ask once more,
    only about the skipped sentences (a second, smaller call).
    """
    logger.info("--- Verification: Strictly fact-checking draft against original abstracts via Groq ---")

    models_cfg = config.get("models", {})
    groq_primary = models_cfg.get("groq", "openai/gpt-oss-120b")
    groq_fallback = models_cfg.get("groq_fallback", "openai/gpt-oss-20b")

    # Prepare sentence-by-sentence audit payload
    audit_items = []
    canary_tracking = {}
    sentences_by_paper = {}

    for idx, p in enumerate(draft_papers):
        paper_id = p["id"]
        reason = p.get("ranking_reason", "").strip()
        explanation = p.get("explanation", "").strip()

        reason_sentences = split_into_sentences(reason)
        exp_sentences = split_into_sentences(explanation)

        # In canary mode, hide one clearly false sentence in each paper.
        # Its place is random, so the checker can't learn "the last sentence is the trap".
        canary_sentence = None
        if canary_mode:
            canary_sentence = CANARY_SENTENCES[idx % len(CANARY_SENTENCES)]
            exp_sentences.insert(random.randint(0, len(exp_sentences)), canary_sentence)

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
        sentences_by_paper[paper_id] = sentences_to_verify

        audit_items.append({
            "id": paper_id,
            "title": p["title"],
            "abstract": p["abstract"],
            "sentences_to_verify": sentences_to_verify
        })

    draft_ids = [p["id"] for p in draft_papers]
    total_sentences = sum(len(s) for s in sentences_by_paper.values())

    # Call 1: check every sentence
    raw_response, provider = call_groq(
        prompt=build_checker_prompt(audit_items),
        system_instruction=CHECKER_INSTRUCTION,
        primary_model=groq_primary,
        api_key=groq_key,
        fallback_model=groq_fallback
    )
    paper_results, paper_reasons, paper_exps = parse_checker_reply(raw_response, draft_ids)

    missing_items = find_missing(audit_items, paper_results)
    missing_count = sum(len(i["sentences_to_verify"]) for i in missing_items)
    logger.info(f"Checker gave verdicts for {total_sentences - missing_count} of {total_sentences} sentences.")

    # Call 2 (only if needed): ask again, only about the skipped sentences
    if missing_items:
        logger.info(f"Asking the checker once more about the {missing_count} skipped sentences...")
        try:
            raw_retry, retry_provider = call_groq(
                prompt=build_checker_prompt(missing_items),
                system_instruction=CHECKER_INSTRUCTION,
                primary_model=groq_primary,
                api_key=groq_key,
                fallback_model=groq_fallback
            )
            retry_results, _, _ = parse_checker_reply(raw_retry, [i["id"] for i in missing_items])
            for pid, extra in retry_results.items():
                paper_results[pid].extend(extra)
            if retry_provider != provider:
                provider = f"{provider} + {retry_provider}"
            still_missing = sum(len(i["sentences_to_verify"]) for i in find_missing(audit_items, paper_results))
            logger.info(f"After asking again: verdicts for {total_sentences - still_missing} of {total_sentences} sentences.")
        except Exception as e:
            logger.warning(f"Second checker call failed: {e}. Skipped sentences will count as not supported.")

    canary_results = {"caught": 0, "no_verdict": 0, "total": len(canary_tracking), "details": [],
                      "sentences": total_sentences, "verdicts": 0} if canary_mode else None

    verified_papers = []
    for p in draft_papers:
        pid = p["id"]
        returned = {str(r.get("sentence_id", "")).strip().lower(): r for r in paper_results.get(pid, [])}

        # Go through EVERY sentence we sent, not only the ones the AI sent back.
        # A sentence is supported only if (1) the AI says so AND (2) its proof quote is really in the abstract.
        checked = []
        for s in sentences_by_paper.get(pid, []):
            r = returned.get(s["sentence_id"].lower())
            if r is None:
                checked.append({
                    "sentence_id": s["sentence_id"],
                    "claim": s["text"],
                    "supported": False,
                    "evidence": "",
                    "reason": "The checker gave no verdict for this sentence, so it counts as not supported.",
                    "no_verdict": True
                })
                continue

            ai_says_supported = to_bool(r.get("supported", r.get("verdict")))
            evidence = str(r.get("evidence") or "")
            proof_found = evidence_in_abstract(evidence, p.get("abstract", ""))
            reason = str(r.get("reason") or "")
            if ai_says_supported and not proof_found:
                reason = "The checker said supported, but its proof quote is not in the abstract. " + reason

            checked.append({
                "sentence_id": s["sentence_id"],
                "claim": s["text"],
                "supported": ai_says_supported and proof_found,
                "evidence": evidence,
                "reason": reason.strip()
            })

        # Canary mode: did the planted false sentence get marked NOT supported?
        if canary_mode and pid in canary_tracking:
            target_sid, fake_sent = canary_tracking[pid]
            result = next((c for c in checked if c["sentence_id"] == target_sid), None)
            caught_this = result is not None and not result["supported"]
            no_verdict = bool(result and result.get("no_verdict"))
            if caught_this:
                canary_results["caught"] += 1
            if no_verdict:
                canary_results["no_verdict"] += 1
            canary_results["details"].append({
                "id": pid,
                "caught": caught_this,
                "no_verdict": no_verdict,
                "sentence": fake_sent,
                "reason": result["reason"] if result else ""
            })

        claims_checked = len(checked)
        claims_supported = sum(1 for c in checked if c["supported"])
        if canary_mode:
            canary_results["verdicts"] += sum(1 for c in checked if not c.get("no_verdict"))

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
        v_paper["claims"] = checked
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
        print(f"  Checked by  : {verifier}")
        print(f"  Verdicts    : {canary_results['verdicts']} of {canary_results['sentences']} sentences answered by the checker")
        print(f"  Canary Score: {caught} / {total} false sentences caught ({score_pct:.0f}%)")
        if canary_results["no_verdict"]:
            print(f"  ({canary_results['no_verdict']} of these got no verdict from the checker and were blocked by our code)")
        print("  (Note: Canary results are NOT saved to digest.json)")
        print("=" * 75 + "\n")

        for d in canary_results["details"]:
            if d["no_verdict"]:
                status = "CAUGHT BY OUR CODE (CHECKER GAVE NO VERDICT)"
            elif d["caught"]:
                status = "CAUGHT (MARKED NOT SUPPORTED)"
            else:
                status = "MISSED (MARKED SUPPORTED)"
            print(f"  [{status}] ID: {d['id']}")
            print(f"    Injected False Sentence: \"{d['sentence']}\"")
            if d.get("reason"):
                print(f"    Checker's reason: {d['reason']}")
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
