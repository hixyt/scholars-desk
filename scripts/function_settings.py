"""Copy the settings the Supabase function needs from config.yaml into supabase/functions/desk/settings.json.

Run:  python scripts/function_settings.py
GitHub runs it before every deploy, so config.yaml stays the one place to change topics,
models and limits. No keys go in this file; they reach the function as Supabase secrets.
"""

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def main():
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    site = (config["email"].get("site_url") or "").rstrip("/") + "/"
    origin = "/".join(site.split("/")[:3])  # https://hixyt.github.io
    settings = {
        "site_url": site,
        "from_name": config["email"].get("from_name", "The Scholar's Desk"),
        "allowed_origins": [origin, "http://127.0.0.1:8765", "http://localhost:8765"],
        "topics": [{"slug": t["slug"], "label": t["label"]} for t in config["topics"]],
        "models": config["models"],
        "checker": config.get("checker", {}),
    }
    out = ROOT / "supabase" / "functions" / "desk" / "settings.json"
    text = json.dumps(settings, indent=2, ensure_ascii=False) + "\n"
    if "--check" in sys.argv:  # used in CI: fail if someone changed config.yaml but not settings.json
        if out.read_text(encoding="utf-8") != text:
            raise SystemExit("settings.json is out of date. Run: python scripts/function_settings.py")
        return
    out.write_text(text, encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
