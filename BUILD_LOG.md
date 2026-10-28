# Build log: The Scholar's Desk

A free robot that reads new AI papers daily, picks 5 and suggests a weekend project for each.

**How it works:** arXiv + Hugging Face → filter by topic → Gemini picks 5 → Groq fact-checks → email + website

## Status
- [x] Hero page
- [x] Fetch papers
- [x] Pick top 5
- [ ] Fact-checker
- [ ] Daily email
- [ ] Runs every morning
- [ ] Website shows real papers
- [ ] Launch

## Log

**Day 1 · 28 Oct · 4h**
- Built: hero page, fetch.py, rank.py
- Broke: shared my API keys by mistake → made new ones, moved them to .env and GitHub Secrets
- Decided: one AI call for all papers, so it stays free
- Numbers: 388 papers → 44 matched → 5 picked

<!--
Template (paste under "## Log", above the last day):

**Day N · DD Mon · Xh**
- Built:
- Broke:
- Decided:
- Numbers:
-->
