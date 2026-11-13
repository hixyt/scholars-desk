# Turning on the subscribe form and the Examiner

The morning digest works without any of this. These steps switch on the two parts that need a small backend: the subscribe form (Chapter V, By Post) and the claim checker (the Examiner, `check.html`). Both run on one Supabase Edge Function in `supabase/functions/desk`, which GitHub deploys by itself.

It takes about ten minutes, once.

## 1. Make the tables

In Supabase, open **SQL Editor**, paste all of [`supabase/schema.sql`](supabase/schema.sql) and press **Run**. It makes three tables (subscribers, claim checks, a usage log for the daily limits) and a nightly tidy-up job. Visitors can't read or change these tables; only the function and the morning run can.

## 2. Add two secrets to GitHub

In this repo: **Settings → Secrets and variables → Actions → New repository secret**.

| Name | Where to get it |
| --- | --- |
| `SUPABASE_SECRET_KEY` | Supabase: **Project Settings → API Keys**, the **secret** key (starts with `sb_secret_`). Never the publishable one, and never put it in `config.yaml`. |
| `SUPABASE_ACCESS_TOKEN` | Supabase: your avatar → **Account preferences → Access Tokens → Generate new token**. It lets GitHub deploy the function. |

The function also uses `GEMINI_API_KEY`, `GROQ_API_KEY`, `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD`, which the morning digest already has. The deploy job copies them into Supabase, so nobody pastes keys there by hand.

## 3. Deploy

**Actions → Deploy the desk function → Run workflow.** It runs the function's tests, sends the keys to Supabase and deploys. After that it runs again by itself whenever the function or `config.yaml` changes.

## 4. Switch them on

In `config.yaml`, under `site:`, set `subscribe: true` and `checker: true`, and push. The next website build shows Chapter V and the Examiner.

## How it fits together

- Subscribing: The form sends the email address and chosen topics to the function, which saves them and sends a confirmation email. Only confirmed people get the morning email. Every email has links to change topics or unsubscribe, and the List-Unsubscribe header that email apps use for their own unsubscribe button. Unconfirmed sign-ups are deleted after a week.
- The morning email: With `SUPABASE_SECRET_KEY` set, `send_email.py` reads the confirmed subscribers and sends each person only the papers on their topics. `EMAIL_TO` still gets everything. Gmail allows about 500 emails a day, so the run stops at 450 subscribers (`email.max_subscriber_emails` in `config.yaml` changes that).
- The Examiner: The function pulls up to six claims out of a post, asks Groq for a verdict and a quote from the abstract for each, and then runs the same quote test as `verify.py`. A quote that isn't really in the abstract is never shown, and a "supported" claim with a number the abstract doesn't have becomes "stretched". Results are saved, so a share link (`check.html?c=...`) always shows the same answer, and the same post is never checked twice.
- Limits: A visitor can check 8 posts and sign up 5 times a day; everyone together can check 120 posts a day (the `checker:` section of `config.yaml`). Visitors are counted with a scrambled id, never their IP address.

## Testing the function on your own computer

```
python scripts/function_settings.py   # copies topics and limits from config.yaml
deno test --allow-read supabase/tests/
```
