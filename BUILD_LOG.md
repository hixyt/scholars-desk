# Build log: The Scholar's Desk

A free robot that reads new AI papers daily, picks 5 and suggests a weekend project for each.

**How it works:** arXiv + Hugging Face → filter by topic → Gemini picks 5 → Groq fact-checks → email + website

## Status
- [x] Hero page
- [x] Fetch papers
- [x] Pick top 5
- [x] Fact-checker
- [x] Daily email
- [ ] Runs every morning
- [ ] Website shows real papers
- [ ] Launch

## Log

**Day 3 · 30 Oct**
- Built: send_email.py, a dark academia email with a plain-text copy, sent through Gmail with an App Password; website design draft with a 3D bookcase
- Broke: the flat CSS bookshelf looked fake, rebuilt it in real 3D; mailto links do nothing on laptops with no mail app, switched to a Gmail link
- Decided: the email only shows lines that passed the fact-check; email addresses never go in the logs, because Actions logs are public
- Numbers: 5 papers → 21 KB email → 1 reader · ₹0

**Day 2 · 29 Oct · 1.5h**
- Built: 4-day arXiv window with a seen list, fact-checker that needs a proof quote, shared common.py
- Broke: Groq had shut down llama-3.3-70b, checker skipped all 5 planted lies, replies ran out of tokens
- Decided: a sentence goes in the digest only if its proof is really in the abstract
- Numbers: 1017 papers → 48 already seen → 82 matched · canary 5/5 · 12 of 15 real sentences kept · code 1851 → 764 lines

**Day 1 · 28 Oct · 4h**
- Built: hero page, fetch.py, rank.py
- Broke: shared my API keys by mistake → made new ones, moved them to .env and GitHub Secrets
- Decided: one AI call for all papers, so it stays free
- Numbers: 388 papers → 44 matched → 5 picked

<!--
Template (paste under "## Log", so the newest day stays on top):

**Day N · DD Mon · Xh**
- Built:
- Broke:
- Decided:
- Numbers:
-->
