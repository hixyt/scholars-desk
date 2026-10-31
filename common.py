"""Helpers shared by fetch.py, rank.py and verify.py."""

import json
import logging
import os
import re
import sys
import time

import requests
import yaml
from dotenv import load_dotenv

# Paper titles have characters the Windows terminal can't print by default
if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("scholars-desk")
ON_ACTIONS = bool(os.getenv("GITHUB_ACTIONS"))


def annotate(level, message):
    """On GitHub Actions, show a warning or error as a note at the top of the run's page."""
    if ON_ACTIONS:
        print(f"::{level}::{str(message).replace(chr(10), ' ')}", flush=True)


class _ActionsNotes(logging.Handler):
    def emit(self, record):
        if record.levelno >= logging.WARNING:
            annotate("error" if record.levelno >= logging.ERROR else "warning", record.getMessage())


if ON_ACTIONS:
    log.addHandler(_ActionsNotes())


def run(main):
    """Run a script. If it stops with an error, say why on the run's page too."""
    try:
        main()
    except SystemExit as e:
        if isinstance(e.code, str):
            annotate("error", e.code)
        raise
    except Exception as e:
        annotate("error", f"{type(e).__name__}: {e}")
        raise


def load_config(path="config.yaml"):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_keys():
    """API keys come from .env on my laptop, or from GitHub Secrets in Actions."""
    load_dotenv()
    return os.getenv("GEMINI_API_KEY"), os.getenv("GROQ_API_KEY")


HYPE_WORDS = {
    r"crucial": "important",
    r"essential": "key",
    r"vital": "helpful",
    r"powerful": "effective",
    r"game-?changers?": "big improvement",
    r"highly employable": "useful for practical work",
    r"cutting-?edge": "modern",
}


def clean_text(text):
    """Remove em dashes and hype words that the AI sometimes writes anyway."""
    text = re.sub(r"\s*(—| -- )\s*", ", ", text or "")
    text = text.replace("–", "-")
    for word, plain in HYPE_WORDS.items():
        text = re.sub(rf"\b{word}\b", plain, text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def parse_json_list(text):
    """Parse the AI's JSON reply and return the list inside it ({"papers": [...]} gives [...])."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    data = json.loads(text)
    if isinstance(data, dict):
        data = next((v for v in data.values() if isinstance(v, list)), data)
    if not isinstance(data, list):
        raise ValueError("The AI reply has no list in it")
    return data


def call_groq(models, system, prompt, api_key, schema=None, max_tokens=4000):
    """
    Ask Groq, trying each model in order. Returns (reply text, model used).

    Free plan limit is 8,000 tokens per minute per model, and the reply cap
    (max_tokens) counts the model's hidden thinking too. Groq's default cap for
    gpt-oss is only 1,024, which is too small, so we set our own.
    With a schema, Groq's strict mode forces the reply into that exact JSON shape.
    """
    if schema:
        response_format = {"type": "json_schema", "json_schema": {"name": "reply", "strict": True, "schema": schema}}
    else:
        response_format = {"type": "json_object"}

    for model in models:
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "temperature": 0.6,  # Groq recommends 0.5 to 0.7 for gpt-oss
            "max_completion_tokens": max_tokens,
            "response_format": response_format,
        }
        if model.startswith("openai/gpt-oss"):
            payload["reasoning_effort"] = "low"  # short thinking leaves room for the answer

        log.info(f"Asking Groq ({model})...")
        send = lambda: requests.post("https://api.groq.com/openai/v1/chat/completions",
                                     headers={"Authorization": f"Bearer {api_key}"}, json=payload, timeout=120)
        try:
            resp = send()
            if resp.status_code == 429:
                wait = min(int(float(resp.headers.get("retry-after", 20))) + 1, 65)
                log.warning(f"Groq rate limit hit, waiting {wait}s")
                time.sleep(wait)
                resp = send()
        except requests.RequestException as e:
            log.warning(f"Groq ({model}) failed: {e}")
            continue

        if resp.status_code == 200:
            data = resp.json()
            usage = data.get("usage", {})
            log.info(f"Groq ({model}) used {usage.get('prompt_tokens')} prompt + {usage.get('completion_tokens')} reply tokens")
            return data["choices"][0]["message"]["content"], model
        log.warning(f"Groq ({model}) returned {resp.status_code}: {resp.text[:300]}")

    raise RuntimeError("All Groq models failed")
