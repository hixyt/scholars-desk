# Build log: The Scholar's Desk

A free robot that reads new AI papers every morning, picks five and suggests a weekend project for each. I'm writing down what I build each day, including what broke.

**So far:** 1 day · about 4 hours · 388 papers read · ₹0 spent

## Where things stand

- [x] Hero page
- [x] Fetch new papers from arXiv and Hugging Face
- [x] Pick the top 5 and explain them
- [ ] Topic balance and no-code project ideas (testing)
- [ ] Fact-checker (testing)
- [ ] Daily email
- [ ] Run every morning on GitHub Actions
- [ ] Show the real papers on the website
- [ ] README and launch

## How it works

```
arXiv + Hugging Face
  → keep papers that match my topics
  → Gemini picks 5 and writes the summaries
  → Groq checks every claim against the abstract
  → digest.json
  → email and website (not built yet)
```

## Decisions

| Date | Decision | Why |
|---|---|---|
| 28 Oct | One AI call for all papers, not one per paper | The free plan only allows a few calls a day |
| 28 Oct | Groq as a backup | If Gemini is down, the digest still goes out |
| 28 Oct | Keys only in `.env` and GitHub Secrets | The repo is public |
| 28 Oct | At least one paper per topic | The first run picked all five from one topic |
| 28 Oct | A different model checks the summaries | A model checking its own work misses its own mistakes |

## Log

### Day 1 · 28 Oct 2026 · about 4 hours

**What I did**
Designed the hero page, a wax seal with books orbiting it. Wrote `fetch.py`, which pulls yesterday's papers from arXiv and today's from Hugging Face, and `rank.py`, which asks Gemini to pick five and write a short explanation and a weekend project for each.

**What went wrong**
I shared my API keys by mistake while asking for help, so I deleted them and made new ones. They now live only in `.env` and GitHub Secrets. The first ranking also picked all five papers from one topic, so I added a rule for at least one per topic.

**Numbers**
388 papers fetched, 44 matched my topics, 5 picked, 2 AI calls.

**What I learned**
How `.env`, `.gitignore` and GitHub Secrets work together to keep keys out of a public repo.

**In one line**
The robot read 388 papers today and picked five for a student, on two free AI calls.

**Next**
Finish the fact-checker and test it with planted false sentences. Then the daily email.

<!--
Template for a new day. Paste it right under "## Log", above the previous day.

### Day N · DD Mon YYYY · about X hours

**What I did**

**What went wrong**

**Numbers**

**What I learned**

**In one line**

**Next**
-->
