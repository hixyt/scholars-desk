# The Scholar's Desk: build log

A free robot that reads new AI papers every morning, picks the 5 worth reading and suggests a weekend project for each.

## Status

| Part | Status |
|---|---|
| Hero page (3D seal and books) | Done |
| Fetch new papers (fetch.py) | Done |
| Pick top 5 and explain them (rank.py) | Done |
| Topic balance and no-code project versions | In progress |
| Fact-checker (verify.py) | In progress |
| Daily email | Not started |
| Runs every morning on GitHub Actions | Not started |
| Website shows the real papers | Not started |
| README and launch | Not started |

## So far

| Days worked | Hours | Papers read by the robot | AI calls per day | Cost |
|---|---|---|---|---|
| 1 | about 4 | 388 | 2 | ₹0 |

## Key decisions

| Date | What I chose | Why |
|---|---|---|
| 28 Oct | Send all papers to the AI in one call, not one call per paper | The free plan allows only a few calls a day |
| 28 Oct | Groq as a backup AI | If Gemini fails, the digest still goes out |
| 28 Oct | Keys only in .env and GitHub Secrets | The repo is public, so keys can never sit in code |
| 28 Oct | At least 1 paper per topic | Without it, all 5 picks came from one topic |

## Daily log

<!-- Newest day on top. Copy the template at the bottom for each new day. -->

### Day 1 · 28 Oct 2026 · about 4 h

**Built**
- The hero page: a 3D wax seal with books orbiting it, my ex libris bookplate, sound and a quill cursor.
- fetch.py: collects new AI papers every day.
- rank.py: the AI picks the best 5 and writes a simple summary and a weekend project for each.

**How it works**
- arXiv and Hugging Face → keep papers that match my topics → Gemini picks 5 → save digest.json.

**Decision**
- One AI call for all 44 papers instead of 44 calls, so it stays inside the free limit.

**Problem → fix**
- I exposed my API keys by accident → deleted them, made new ones, moved them to .env and GitHub Secrets.
- All 5 picks came from one topic → added a rule for at least 1 paper per topic.

**Numbers**
- 388 papers fetched, 44 matched, 5 picked, 2 AI calls.

**Learned**
- .env keeps secrets on my laptop, .gitignore keeps them off GitHub, GitHub Secrets keeps them safe online.

**Say it in one line**
- "My robot read 388 papers today and picked the 5 a student should read, using just 2 free AI calls."

**Next**
- Finish the fact-checker, then send the digest by email.

---

<!--
TEMPLATE

### Day N · DD Mon YYYY · X h

**Built**
-

**How it works**
-

**Decision**
-

**Problem → fix**
-

**Numbers**
-

**Learned**
-

**Say it in one line**
- ""

**Next**
-
-->
