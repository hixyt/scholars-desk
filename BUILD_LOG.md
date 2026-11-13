# Build log: The Scholar's Desk

A small robot that reads new AI papers every morning, picks about one paper per topic, explains it in simple words and gives you a weekend project for it. It costs ₹0.

How it works: arXiv and Hugging Face → keep the papers on my 6 topics → Gemini picks about 6 and writes about them → Groq checks every line → email and website

## Status
- [x] Hero page
- [x] Get the papers
- [x] Pick the best ones
- [x] Fact-checker
- [x] Morning email
- [x] Runs by itself every morning
- [x] Website shows the real papers
- [x] README and share picture
- [x] Starts on time at 6:17 AM
- [x] Six topics
- [ ] Subscribe form and Examiner go live (built, I'll switch them on after my exams)
- [ ] Launch

## Log

### Day 7 · 13 Nov
- Built: I added four new topics (health, education, trust and safety, business and money). The desk now covers six and picks about one paper for each. I also built two new things. One is a form where people can subscribe and choose their topics. The other is the Examiner: you paste a LinkedIn post about a paper, and it checks each claim against the paper's abstract. Both run on a small Supabase function. They're ready, but I'm keeping them off until my exams are over.
- Broke: No email went out on 12 Nov. Gemini was overloaded, the backup model name didn't exist anymore, and the Groq backup broke because that day had only 1 paper. The Supabase timer never ran either. The token I saved was missing its first part ("github_pat_"), so GitHub said 401.
- Decided: If Gemini is busy, the desk now waits and tries again before it moves to Groq. I left out keywords that mean something else in ML papers, like "student" and "bias". The Examiner uses the same quote check as the email, so it can't show a made-up quote. It doesn't save anyone's IP address.
- Numbers: From 5 to 13 Nov there were 9 runs and 6 emails. 2 weekend days had no new papers and 1 run failed. 81 of 90 lines were proven. I tested the Examiner's quote check against the email's on 600 examples, and they agreed every time.

### Day 6 · 4 Nov
- Built: A README with screenshots, a preview picture that shows up when the link is shared on WhatsApp or LinkedIn, and a wax seal icon for the browser tab. I also removed the $ signs that showed up in some paper titles.
- Broke: GitHub's timer kept starting the morning run about 6 hours late, even after I set the time zone.
- Decided: Supabase now starts the run at 6:17 AM. GitHub's timer is still there as a backup, and it does nothing if the run already happened.
- Numbers: 1,447 papers read, 47 on my topics, 4 picked, 11 of 15 lines proven. From 29 Oct to 4 Nov, 52 of 73 lines were proven.

### Day 5 · 2 Nov
- Built: The website now shows the real papers. build_site.py rebuilds it every morning from the saved days.
- Broke: The morning runs started at 12:22 PM instead of 6:17 AM. Gemini also started one sentence with "Hey!", and the checker cut it.
- Decided: I set the schedule in India time. Nobody edits the page by hand; it's made from the data. Write-ups now start with what the paper does.
- Numbers: 4 days on the shelf. 1 Nov was a quiet Sunday with 0 matches. That day: 756 papers, 49 on my topics, 4 picked, 9 of 13 lines proven.

### Day 4 · 31 Oct
- Built: GitHub Actions now runs the whole desk every morning and saves the day's papers in the repo. Errors show up on the run page.
- Broke: The Groq key had a hidden line break, so every request failed. The Gmail secret went missing. One paper had 0 of 3 lines proven.
- Decided: Keys get cleaned before they're used. A paper with no proven lines stays out of the email. A day with no papers isn't an error.
- Numbers: 1,141 papers (1,091 from arXiv, 50 from Hugging Face), 45 already seen, 89 on my topics, 5 picked, 13 of 15 lines proven. The run took 40 seconds and cost ₹0.

### Day 3 · 30 Oct
- Built: send_email.py. It sends a dark academia style email, with a plain text copy too, through Gmail. I also made the first design of the website, with a 3D bookcase.
- Broke: The flat bookshelf looked fake, so I rebuilt it in 3D. Email links did nothing on laptops without a mail app, so I switched to a Gmail link.
- Decided: The email only shows lines that passed the fact-check. Email addresses never go in the logs, because the logs are public.
- Numbers: 5 papers, a 21 KB email, 1 reader, ₹0.

### Day 2 · 29 Oct · 1.5h
- Built: The desk now looks back 4 days and skips papers it already saw. I made the fact-checker, which needs a quote from the abstract as proof. Shared code went into common.py.
- Broke: Groq had shut down the llama-3.3-70b model. The checker missed all 5 fake sentences I planted to test it. Replies ran out of tokens.
- Decided: A sentence goes in only if its proof is really in the abstract.
- Numbers: 1,017 papers, 48 already seen, 82 on my topics. After the fix, the checker caught 5 of 5 fake sentences. 12 of 15 real sentences were kept. The code went from 1,851 lines to 764.

### Day 1 · 28 Oct · 4h
- Built: The hero page, fetch.py and rank.py.
- Broke: I shared my API keys by mistake, so I made new ones and moved them into .env and GitHub Secrets.
- Decided: One AI call for all the papers, so it stays free.
- Numbers: 388 papers, 44 on my topics, 5 picked.

<!--
Template (paste under "## Log", so the newest day stays on top):

### Day N · DD Mon · Xh
- Built:
- Broke:
- Decided:
- Numbers:
-->
