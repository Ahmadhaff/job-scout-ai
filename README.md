# job-scout-ai

CLI agent that reads public startup job feeds, asks Claude how well each role fits a full-stack and AI engineer profile (React, Next.js, Node.js, NestJS, PostgreSQL), and sends a Telegram alert plus a one-page PDF résumé when the match score is 8/10 or higher.

## How it works

1. `src/fetchers.py` downloads Hacker News RSS, plus listing pages from Keejob, Tanitjobs, and Free-Work. Each source returns `title`, `link`, and `description`. Listings outside React, Next.js, Node.js, NestJS, PostgreSQL, or AI are skipped before Claude is called.
2. `src/evaluator.py` sends the listing plus the candidate profile to Claude through the official `anthropic` SDK. The default model is `claude-sonnet-5-5`. `claude-3-5-sonnet-latest` was retired on 2025-10-28, so requests to that id fail. Set `ANTHROPIC_MODEL` to use a different model.
3. Claude replies with three fields:
   - `MATCH_SCORE` — integer from 1 to 10
   - `IS_STARTUP` — `True` or `False`
   - `SUMMARY` — two sentences on why the role does or does not fit
4. A listing alerts only when `MATCH_SCORE` is at least 8 and the text is in the React, Next.js, Node.js, NestJS, PostgreSQL, or AI lane.
5. For each alert, Claude rewrites the headline and profile and reorders projects from the English CV. Employers, dates, and metrics stay fixed. `src/resume_pdf.py` writes a one-page PDF, and `src/notifier.py` sends the alert plus that file.
6. Handled listing ids are stored in `data/seen_jobs.json` so later runs skip them. Listings are paced by `REQUEST_DELAY_SECONDS` (default 1.5s). A listing is recorded only after scoring succeeds and, for an alert, after Telegram accepts both the message and the PDF. Failures stay unseen and are retried next run.

The candidate profile lives in `src/config.py`. Résumé facts live in `src/resume_facts.py` and follow the English CV.

## Project layout

```
main.py                         CLI entry point
src/config.py                   Environment variables and developer profile
src/fetchers.py                 RSS and board fetch
src/boards.py                   Keejob, Tanitjobs, and Free-Work pages
src/evaluator.py                Claude request and response parsing
src/notifier.py                 Telegram alerts and PDF upload
src/resume_facts.py             CV facts and tailoring parser
src/resume_pdf.py               One-page PDF renderer
src/resume_tailor.py            Job-specific headline and profile
src/state.py                    Seen-listing store
.github/workflows/job_agent.yml Scheduled run every 6 hours
```

## Local setup

Python 3.10 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

| Variable | Purpose |
| --- | --- |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `TELEGRAM_BOT_TOKEN` | Token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Your chat id |

To find the chat id, send any message to the bot, then open `https://api.telegram.org/bot<token>/getUpdates` and read `message.chat.id`.

Optional settings are listed in `.env.example`. `JOB_FEEDS` is a comma-separated list of RSS URLs. A useful extra feed is `https://weworkremotely.com/categories/remote-programming-jobs.rss`.

Check the feeds without spending API credits:

```bash
python main.py --dry-run --limit 5
```

Write the base résumé PDF without calling Claude:

```bash
python main.py --sample-resume
```

Run the agent:

```bash
python main.py
```

`--limit` caps how many new listings are scored in that run. `--verbose` prints the raw model response.

## GitHub Actions

`.github/workflows/job_agent.yml` runs on cron `0 */6 * * *` (every 6 hours, UTC) and on manual `workflow_dispatch`.

Add these repository secrets before enabling the workflow:

- `ANTHROPIC_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

The workflow caches `data/seen_jobs.json` between runs. If that cache is evicted, a later run can score the same listings again and send another alert. Delete the local seen file when you want a full rescan on your machine.

## Tests

```bash
python -m unittest discover -s tests -t .
```

## License

MIT. See [LICENSE](LICENSE).
