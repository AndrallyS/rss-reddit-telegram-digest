# Resilient Daily Digest for Telegram

Python pipeline for building and sending a daily Telegram briefing with curated sources across:

- Games
- Game Dev
- AI
- Markets
- Tech

Core architecture:

- RSS is the primary source layer
- Public Reddit JSON is optional enrichment only
- Telegram is the final delivery channel
- GitHub Actions handles daily automation

## Why this architecture

### RSS as the foundation

RSS remains the best primary layer for this project because it is:

- more predictable
- easy to audit
- independent from OAuth
- well suited for daily automation
- still useful even if one or more sources fail

### Reddit JSON as optional enrichment

Public Reddit JSON is treated as a secondary layer because:

- it is not an officially stable integration for primary ingestion
- it may return `403`, `429`, HTML, timeouts, or invalid JSON
- its structure may change without notice

Because of that:

- `ENABLE_REDDIT` starts disabled by default in the example configuration
- the workflow validates Reddit before using it operationally
- if validation fails, the pipeline continues with RSS only

## Configured categories

### Games

- GameSpot
- PC Gamer
- Nintendo Life
- Push Square
- Gematsu
- Polygon

### Game Dev

- Game Developer
- Unity Blog
- BlenderNation
- Godot Blog
- DirectX Developer Blog
- 80 Level

### AI

- OpenAI News
- NVIDIA Blog
- Hugging Face Blog
- TechCrunch AI
- The Verge AI
- VentureBeat AI

### Markets

- InfoMoney
- Money Times
- Brazil Journal
- MarketWatch Top Stories
- SEC Press Releases
- Federal Reserve Press

### Tech

- Ars Technica
- TechCrunch
- WIRED
- The Verge
- The Register
- InfoQ
- Hacker News via HNRSS

## Project structure

```text
app/
  config.py
  constants.py
  health.py
  logger.py
  models.py
  utils.py
  delivery/
    telegram_sender.py
  pipeline/
    dedupe.py
    formatter.py
    normalize.py
    ranker.py
    runner.py
    summarizer.py
  sources/
    reddit_json_fetcher.py
    rss_fetcher.py
config/
  ranking.yaml
  sources.yaml
scripts/
  run_digest.py
  send_test_telegram.py
  validate_reddit_json.py
tests/
.github/
  workflows/
    daily_digest.yml
output/
logs/
```

## Requirements

- Python 3.11+
- Windows PowerShell, CMD, Git Bash, or equivalent terminal
- a GitHub account
- a Telegram bot and chat ID

## Local setup on Windows

### 1. Open PowerShell in the project folder

Example:

```powershell
cd "C:\Users\User\Folder\rss-reddit-telegram-digest"
```

### 2. Create the virtual environment

```powershell
py -3.11 -m venv .venv
```

If you do not have Python 3.11 specifically installed, use:

```powershell
py -3 -m venv .venv
```

### 3. Activate the virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Configure `.env`

Create a `.env` file based on `.env.example`.

Fields:

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
REDDIT_USER_AGENT=games-tech-digest/1.0 (+https://github.com/your-user/your-repo; contact: digest-admin)
REQUEST_TIMEOUT_SECONDS=12
ENABLE_REDDIT=true
LOG_LEVEL=INFO
MAX_RETRIES=2
BACKOFF_BASE_SECONDS=0.75
```

Notes:

- `.env` is local only and should never be committed
- use a descriptive `REDDIT_USER_AGENT`
- for GitHub Actions, these values belong in repository secrets, not in the repo itself

## Testing Telegram

Quick test:

```powershell
python scripts\send_test_telegram.py
```

If it succeeds, you should receive a simple message in the configured Telegram chat.

## Validating Reddit JSON

```powershell
python scripts\validate_reddit_json.py
```

The script:

- tests example subreddits
- measures status, content type, and response time
- checks whether the payload is a valid `Listing`
- verifies minimum required fields
- saves `output/reddit_validation_report.json`

Interpretation:

- `functional`: worked at this moment, but still optional
- `functional_but_unstable`: usable with caution
- `blocked`: do not use
- `not_recommended`: keep RSS-only mode

Final rules:

- `enable_reddit_by_default` should remain `false`
- `enable_reddit_optionally` may be `true`
- `operate_only_rss` tells you whether Reddit should stay disabled
- validation success does not guarantee every later Reddit request will succeed on shared runners, so the runtime fetcher now uses a conservative request budget

## Running the digest manually

Standard run:

```powershell
python scripts\run_digest.py
```

Dry run without Telegram delivery:

```powershell
python scripts\run_digest.py --dry-run
```

Run without saving a dated history copy:

```powershell
python scripts\run_digest.py --no-history
```

One-click Windows launcher with Reddit enabled for that run:

```powershell
RUN_DIGEST_WITH_REDDIT.cmd
```

What it does:

- forces `ENABLE_REDDIT=true` only for that launcher session
- runs Reddit validation first
- runs the digest immediately after
- sends to Telegram if validation approves optional Reddit usage
- falls back to RSS automatically if Reddit is blocked or invalid

Files generated in `output/`:

- `raw_rss_items.json`
- `raw_reddit_items.json`
- `normalized_items.json`
- `ranked_items.json`
- `reddit_validation_report.json`
- `last_run_report.json`
- `telegram_preview.txt`

Dated execution history:

- `output/history/YYYY-MM-DD/HH-MM-SS/raw_rss_items.json`
- `output/history/YYYY-MM-DD/HH-MM-SS/raw_reddit_items.json`
- `output/history/YYYY-MM-DD/HH-MM-SS/normalized_items.json`
- `output/history/YYYY-MM-DD/HH-MM-SS/ranked_items.json`
- `output/history/YYYY-MM-DD/HH-MM-SS/telegram_preview.txt`
- `output/history/YYYY-MM-DD/HH-MM-SS/run_report.json`

### What `dry-run` does

- runs collection, normalization, dedupe, ranking, and formatting
- saves preview and JSON outputs
- does not send anything to Telegram
- ideal for validating layout, source health, and ranking before production use

### What dated history does

- keeps a copy of every execution
- prevents losing traceability when `last_run_report.json` is overwritten
- makes it easier to compare days or inspect previous test runs

## Telegram message format

The formatter is designed to produce a more structured and visually clearer Telegram briefing:

- Games
- Game Dev
- AI
- Markets
- Tech
- Reddit Radar
- Editorial Coverage

Each item includes:

- clickable title
- short summary
- explicit Reddit labeling when the primary link is a Reddit thread
- Reddit discussion hint when an external article is being amplified by Reddit
- editorial source labeling for RSS-driven coverage

## Daily GitHub automation

Workflow file:

- `.github/workflows/daily_digest.yml`

### Scheduled time

You asked for delivery from Monday to Saturday around noon in Brazil.

On March 24, 2026, `America/Sao_Paulo` is `UTC-03:00`.

That is why the workflow uses:

```yaml
cron: "55 14 * * 1-6"
```

Meaning:

- 14:55 UTC
- about 11:55 BRT, to compensate for common GitHub Actions schedule delays
- Monday through Saturday

If time zone rules change in the future, update the cron value accordingly.

### What the workflow does

1. checks out the code
2. installs Python and dependencies
3. validates Reddit JSON
4. runs the digest
5. publishes a digest summary with `rss_items`, `reddit_items`, and the runtime Reddit decision
6. sends messages to Telegram
7. uploads `output/` and `logs/` as workflow artifacts

## Full step-by-step GitHub setup

### 1. Initialize Git locally

```powershell
git init
git add .
git commit -m "Initial resilient Telegram digest"
```

### 2. Create a GitHub repository

In the browser:

1. go to [GitHub](https://github.com)
2. click `New repository`
3. choose a name, for example `daily-telegram-digest`
4. do not enable README, `.gitignore`, or license generation because they already exist here

### 3. Connect the local repo to GitHub

Replace `YOUR_USER` and `YOUR_REPO`:

```powershell
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git branch -M main
git push -u origin main
```

### 4. Add repository secrets

In the GitHub repository:

1. open `Settings`
2. open `Secrets and variables`
3. open `Actions`
4. create these secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `REDDIT_USER_AGENT`

### 5. Run the workflow manually once

In GitHub:

1. open the `Actions` tab
2. select `Daily Digest`
3. click `Run workflow`

### 6. Confirm the result

Check:

- whether the message reached Telegram
- whether the workflow run finished successfully
- whether the artifacts were uploaded

## What must never go into Git

- `.env`
- local logs
- sensitive outputs
- caches
- the virtual environment

The current `.gitignore` already covers these cases.

## Automated tests

Run:

```powershell
pytest
```

The suite covers:

- Reddit parsing
- invalid JSON
- HTML instead of JSON
- invalid content type
- missing fields
- RSS-only fallback
- partial subreddit failures
- deduplication
- ranking
- formatter behavior
- empty outputs
- dry-run behavior
- dated history generation

## Troubleshooting

### The Telegram message did not arrive

Check:

- bot token
- chat ID
- whether the bot has permission in the target chat
- whether `send_test_telegram.py` works

### Reddit stopped working

Check:

- `output/reddit_validation_report.json`
- `logs/digest.log`
- the GitHub Actions run summary for `reddit_items`, `reddit_reason`, and `reddit_failures`

Important:

- the validator uses a small sample of requests
- the full runtime fetch used to make many more requests than validation
- the runtime collector now stops early once each category already has enough Reddit material, which reduces shared-runner instability and makes GitHub runs closer to local runs

Even then, the digest should continue with RSS only.

### The workflow does not run at the expected time

Check:

- whether GitHub Actions is enabled for the repository
- whether the cron expression is correct
- whether your desired time zone is still `UTC-03:00`


