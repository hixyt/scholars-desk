#!/usr/bin/env python3
"""
Step 3: fact-check the draft against each paper's abstract, using Groq.

Every sentence we wrote (the reason and the explanation) goes to the checker.
A sentence counts as supported only if the checker says so AND the proof it
quotes really is in the abstract. Unsupported sentences are left out of
the final digest.json.

--canary hides one obviously false sentence in each paper and reports how many
the checker caught. Nothing is saved in canary mode.
"""

import argparse
import json
import random
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from common import call_groq, load_config, load_keys, log, parse_json_list

CANARY_SENTENCES = [
    "The authors proved this method by testing it on 50,000 live penguins wearing VR headsets.",
    "The system achieved 99.9% accuracy on a quantum computer from the year 2045.",
    "The method relies on an ancient alchemical formula discovered in 1342.",
    "The benchmark was conducted exclusively inside underwater microwave ovens at zero gravity.",
    "The researchers confirmed that this software eliminates 100% of all programming bugs in human history.",
]

CHECKER_RULES = (
    "You are a strict fact-checker. A student wrote short summaries of research papers from their abstracts.\n"
    "For each paper you get the abstract and the student's sentences in 'sentences_to_verify'.\n\n"
    "Rules:\n"
    "1. Check ONLY the sentences in sentences_to_verify. Do not add other claims.\n"
    "2. Give a verdict for EVERY sentence, even ones that look wrong or silly. Never skip one. "
    "A wrong sentence gets supported: false.\n"
    "3. A sentence is supported ONLY if the abstract clearly and directly says it. If it adds any detail "
    "the abstract does not mention (a number, date, place, tool, test or result), it is NOT supported, "
    "even if the rest sounds right.\n"
    "4. Words in [square brackets] explain a technical term for beginners. They only need to be a correct "
    "general definition; judge the rest of the sentence against the abstract.\n"
    "5. For each sentence give, in this order:\n"
    "   - sentence_id: the id from the input\n"
    "   - evidence: the exact words from the ABSTRACT that prove it, copied without changes. "
    "Never copy the student's sentence as evidence. If nothing in the abstract proves it, write \"\".\n"
    "   - reason: one short sentence on why it is or isn't supported\n"
    "   - supported: true or false. If evidence is empty, supported must be false."
)

# The exact JSON shape Groq must return (strict mode). The order of the fields
# makes the model copy the proof first and decide last.
CHECKER_SCHEMA = {
    "type": "object",
    "required": ["papers"],
    "additionalProperties": False,
    "properties": {"papers": {"type": "array", "items": {
        "type": "object",
        "required": ["id", "results"],
        "additionalProperties": False,
        "properties": {
            "id": {"type": "string"},
            "results": {"type": "array", "items": {
                "type": "object",
                "required": ["sentence_id", "evidence", "reason", "supported"],
                "additionalProperties": False,
                "properties": {
                    "sentence_id": {"type": "string"},
                    "evidence": {"type": "string"},
                    "reason": {"type": "string"},
                    "supported": {"type": "boolean"},
                },
            }},
        },
    }}},
}


def split_sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if s]


def quote_in_abstract(quote, abstract):
    """
    Our own check that the checker's proof really comes from the abstract.
    Case and punctuation are ignored, and a word or two may differ (the AI once wrote
    "we develop" where the abstract says "to develop"). But at least 80% of the quote
    must match the abstract in runs of 3 or more words in a row, and every number
    in the quote must be in the abstract exactly.
    """
    words = lambda t: re.sub(r"[^a-z0-9]+", " ", t.lower()).split()
    q, a = words(quote), words(abstract)
    if len(q) < 4:  # a quote of 1-3 words proves nothing
        return False
    if any(w.isdigit() and w not in a for w in q):
        return False
    blocks = SequenceMatcher(None, q, a, autojunk=False).get_matching_blocks()
    return sum(b.size for b in blocks if b.size >= 3) / len(q) >= 0.8


def ask_checker(items, config, groq_key):
    """One Groq call. Returns ({paper id: {sentence id: verdict}}, model used)."""
    total = sum(len(item["sentences_to_verify"]) for item in items)
    prompt = (f"Fact-check these {len(items)} papers. There are {total} sentences in total, "
              f"so give {total} verdicts, one for every sentence_id.\n\n" + json.dumps(items, ensure_ascii=False))
    models = [config["models"]["groq"], config["models"]["groq_fallback"]]
    reply, model = call_groq(models, CHECKER_RULES, prompt, groq_key, schema=CHECKER_SCHEMA)

    verdicts = {item["id"]: {} for item in items}
    for n, paper in enumerate(parse_json_list(reply)):
        pid = paper["id"]
        if pid not in verdicts and n < len(items):
            pid = items[n]["id"]  # the AI changed the id a little (e.g. added "v1"), so go by order
        if pid in verdicts:
            for r in paper["results"]:
                verdicts[pid][r["sentence_id"].strip().lower()] = r
    return verdicts, model


def check_papers(papers, config, groq_key, canary=False):
    """Fact-check every sentence. Returns (checked papers, model used, canary results)."""
    items = []
    for n, p in enumerate(papers):
        reason = split_sentences(p.get("ranking_reason"))
        explanation = split_sentences(p.get("explanation"))
        if canary:
            # random spot, so the trap isn't always the last sentence
            explanation.insert(random.randint(0, len(explanation)), CANARY_SENTENCES[n % len(CANARY_SENTENCES)])
        sentences = [("reason", s) for s in reason] + [("explanation", s) for s in explanation]
        items.append({
            "id": p["id"],
            "title": p["title"],
            "abstract": p["abstract"],
            "sentences_to_verify": [{"sentence_id": f"s{i}", "source": src, "text": text}
                                    for i, (src, text) in enumerate(sentences, 1)],
        })

    verdicts, model = ask_checker(items, config, groq_key)

    # If the checker skipped any sentences, ask once more about just those
    missing = []
    for item in items:
        left = [s for s in item["sentences_to_verify"] if s["sentence_id"] not in verdicts[item["id"]]]
        if left:
            missing.append(dict(item, sentences_to_verify=left))
    if missing:
        log.info(f"Checker skipped {sum(len(m['sentences_to_verify']) for m in missing)} sentences, asking again")
        try:
            more, _ = ask_checker(missing, config, groq_key)
            for pid, found in more.items():
                verdicts[pid].update(found)
        except Exception as e:
            log.warning(f"Second check failed, skipped sentences count as not supported: {e}")

    checked, canaries, answered, total = [], [], 0, 0
    for p, item in zip(papers, items):
        claims = []
        for s in item["sentences_to_verify"]:
            total += 1
            v = verdicts[p["id"]].get(s["sentence_id"])
            claim = {"sentence_id": s["sentence_id"], "source": s["source"], "claim": s["text"]}
            if v is None:
                claims.append(dict(claim, supported=False, evidence="", no_verdict=True,
                                   reason="The checker gave no verdict, so this counts as not supported."))
                continue
            answered += 1
            proof_ok = quote_in_abstract(v["evidence"], p["abstract"])
            reason = v["reason"] if proof_ok or not v["supported"] else "Its proof quote is not in the abstract."
            claims.append(dict(claim, supported=v["supported"] and proof_ok, evidence=v["evidence"], reason=reason))

        if canary:
            canaries.append(next(c for c in claims if c["claim"] in CANARY_SENTENCES))
            continue

        def keep(source):
            return " ".join(c["claim"] for c in claims if c["source"] == source and c["supported"])

        if not keep("explanation"):
            log.warning(f"No sentence of the explanation for {p['id']} passed the check")
        checked.append(dict(p, ranking_reason=keep("reason"), explanation=keep("explanation"), claims=claims,
                            claims_checked=len(claims), claims_supported=sum(c["supported"] for c in claims)))

    log.info(f"Checker answered {answered} of {total} sentences")
    return checked, model, canaries


def main():
    parser = argparse.ArgumentParser(description="Fact-check the draft digest against the paper abstracts.")
    parser.add_argument("--date", help="YYYY-MM-DD (default: today in UTC)")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--canary", action="store_true", help="test the checker with planted false sentences (saves nothing)")
    args = parser.parse_args()

    date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    folder = Path(args.data_dir) / date
    draft_path = folder / "digest_draft.json"
    if not draft_path.exists():
        raise SystemExit(f"{draft_path} not found. Run rank.py first.")
    _, groq_key = load_keys()
    if not groq_key:
        raise SystemExit("GROQ_API_KEY is missing. The checker needs Groq.")

    config = load_config(args.config)
    with open(draft_path, encoding="utf-8") as f:
        papers = json.load(f)["papers"]
    if not papers:
        if not args.canary:
            with open(folder / "digest.json", "w", encoding="utf-8") as f:
                json.dump({"date": date, "verified_at": datetime.now(timezone.utc).isoformat(), "verifier": None,
                           "status": "no_papers", "papers": []}, f, indent=2)
        print("The draft has no papers, so there is nothing to check.")
        return

    checked, model, canaries = check_papers(papers, config, groq_key, canary=args.canary)

    if args.canary:
        caught = sum(not c["supported"] for c in canaries)
        print(f"\nCanary Score: {caught} / {len(canaries)} planted false sentences caught (checked by {model})")
        for c in canaries:
            status = "CAUGHT BY OUR CODE (no verdict)" if c.get("no_verdict") else "CAUGHT" if not c["supported"] else "MISSED"
            print(f"  [{status}] {c['claim']}")
            print(f"      checker said: {c['reason']}")
        print("Nothing was saved (canary mode).")
        return

    digest = {
        "date": date,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "verifier": f"Groq ({model})",
        "status": "verified",
        "papers": checked,
    }
    digest_path = folder / "digest.json"
    with open(digest_path, "w", encoding="utf-8") as f:
        json.dump(digest, f, indent=2, ensure_ascii=False)

    for i, p in enumerate(checked, 1):
        print(f"\n[{i}] {p['title']}")
        print(f"    Supported: {p['claims_supported']} of {p['claims_checked']} sentences")
        for c in p["claims"]:
            if not c["supported"]:
                print(f"    - LEFT OUT: {c['claim']}")
                print(f"      because: {c['reason']}")
    print(f"\nSaved {digest_path}")


if __name__ == "__main__":
    main()
