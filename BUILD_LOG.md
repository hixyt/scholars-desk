# Build log: The Scholar's Desk

A free robot that reads new AI papers daily, picks about one per topic and suggests a weekend project for each.

**How it works:** arXiv + Hugging Face → filter by 6 topics → Gemini picks ~6 → Groq fact-checks → email + website

## Status
- [x] Hero page
- [x] Fetch papers
- [x] Pick top 5
- [x] Fact-checker
- [x] Daily email
- [x] Runs every morning
- [x] Website shows real papers
- [x] README and share preview
- [x] Starts on time (Supabase timer)
- [x] Six topics
- [ ] Subscribe form and Examiner live (built, switched on after exams)
- [ ] Launch

## Log

**Day 7 · 13 Nov**
- Built: six topics instead of two (added health, education, trust and safety, business and money), about one paper per topic; a subscribe form where people choose their topics, with a confirmation email and an unsubscribe link in every email; the Examiner, which checks the claims in a LinkedIn post against the paper's abstract; a Supabase Edge Function for both, which GitHub tests and deploys
- Broke: no email on 12 Nov, because Gemini was overloaded, the backup model name no longer existed, and on a 1-paper day the Groq backup sent a reply with no list; the Supabase timer never fired, because the saved token was missing its "github_pat_" start, so GitHub answered 401
- Decided: Gemini gets two more tries (after 30s and 90s) before Groq; keywords skip words that mean something else in ML papers (student, bias, trading); the Examiner uses the same quote test as the digest, so a made-up quote is never shown; visitors are counted with a scrambled id, never an IP; the new features stay off until the setup is done
- Numbers: 5 to 13 Nov: 9 runs · 6 emails · 2 weekend days with no new papers · 1 failed run · 81 of 90 lines proven · the quote test in TypeScript matches the Python one on 600 of 600 cases · 7 function tests pass

**Day 6 · 4 Nov**
- Built: README with screenshots; a share picture so links show a preview on WhatsApp and LinkedIn; a wax seal favicon; paper titles without LaTeX $ marks
- Broke: GitHub's own timer kept starting the morning run about 6 hours late, even with the time zone set
- Decided: a Supabase pg_cron job starts the run at 6:17 AM; GitHub's timer stays as a backup that does nothing if the morning run already happened
- Numbers: 1,447 papers → 131 already seen → 47 matched → 4 picked · 11 of 15 lines proven · 29 Oct to 4 Nov: 52 of 73 lines proven

**Day 5 · 2 Nov**
- Built: the website now shows the real papers; build_site.py rebuilds it from the saved days every morning, and the design lives in site/
- Broke: the morning runs started at 12:22 PM instead of 6:17 AM; Gemini began one reason with "Hey!", and the checker struck it
- Decided: the schedule is set in India time; the page is made from the data, so nobody edits it by hand; write-ups start with what the paper does
- Numbers: 4 days on the shelf · 1 Nov was a quiet Sunday with 0 matches · today 756 papers → 49 matched → 4 picked · 9 of 13 lines proven

**Day 4 · 31 Oct**
- Built: GitHub Actions runs the whole desk at 6:17 AM every day and saves the day's papers to the repo; errors now show on the run page
- Broke: the Groq secret had a hidden line break, so every request was refused; the Gmail secret had gone missing; one paper had 0 of 3 lines proven
- Decided: keys are cleaned before use; a paper with no proven summary stays out of the email; a quiet day with no papers is not an error
- Numbers: 1,141 papers (1,091 arXiv + 50 Hugging Face) → 45 already seen → 89 matched → 5 picked · 13 of 15 lines proven · run took 40s · ₹0

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
