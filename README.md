# fix50-agent

AI agent for finding, scoring, and preparing small freelance opportunities in a 14-day $50 revenue experiment.

**V1 scope:** receive an opportunity -> analyze it (mock AI provider) -> score it 0-100 -> draft a proposal if it's worth >= 70 -> store everything in SQLite. No scraping, no auto-messaging, no payments. Contacting clients is a manual, human-driven step.

## Tech stack

- Python 3.12, FastAPI, Pydantic v2
- SQLite (stdlib `sqlite3`, no ORM)
- Pytest for tests
- Mock AI provider (runs with **zero** budget and no API keys)

## Project structure

```
app/
  main.py                  # FastAPI app factory + wiring
  config.py                # env-based settings
  api/
    routes.py              # /opportunities endpoints
    deps.py                # DI from app.state
  models/
    opportunity.py         # domain dataclasses + enums (Status, Difficulty, ...)
  schemas/
    opportunity.py         # Pydantic request/response models
  services/
    ai_provider.py         # AIProvider interface + MockAIProvider + factory
    analyzer.py            # analysis pipeline entry point
    scorer.py              # deterministic 0-100 rubric
    proposal_generator.py  # proposal template builder
  db/
    database.py            # sqlite connection + schema
    repository.py          # OpportunityRepository
tests/
  test_analyzer.py         # mock provider behavior
  test_scorer.py           # rubric + classification boundaries
  test_api.py              # all endpoints
```

## Setup & run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # defaults work out of the box (mock provider)
uvicorn app.main:app --reload
```

Interactive docs: http://localhost:8000/docs

## API

| Method | Path                          | Purpose                                        |
|--------|-------------------------------|------------------------------------------------|
| POST   | `/opportunities/analyze`      | Analyze + score + (maybe) draft proposal + store |
| GET    | `/opportunities?status=`      | List stored opportunities (optional status filter) |
| GET    | `/opportunities/{id}`         | Get one opportunity with full analysis         |
| PATCH  | `/opportunities/{id}/status`  | Move it through the pipeline manually          |
| GET    | `/health`                     | Liveness + active provider                     |

### Example

```bash
curl -s -X POST http://localhost:8000/opportunities/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "source": "upwork",
    "title": "Fix broken checkout on Shopify store - losing orders",
    "description": "Our Shopify checkout has been failing for the last week. Customers report errors when paying, and we estimate we are losing about 30% of daily orders and revenue. We need someone to find the bug and fix it quickly.",
    "url": "https://example.com/job/123",
    "client_name": "Acme Store",
    "market": "US / English"
  }'
```

Response (shortened): analysis (problem, skills, difficulty, time, price range, confidence), score with per-criterion breakdown, classification, a drafted proposal, and the stored record with `status: "candidate"`.

## Scoring rubric (0-100)

| Criterion                              | Max |
|----------------------------------------|-----|
| Is the problem clear?                  | 25  |
| Does solving it provide business value?| 25  |
| Can it be completed quickly?           | 20  |
| Is the solution easy to explain?       | 10  |
| Can the client be contacted?           | 10  |
| Is the opportunity/client credible?    | 10  |

Classification: `< 70` rejected, `70-84` candidate, `>= 85` strong opportunity. Proposals are drafted only for score >= 70.

## Statuses

`new` -> `rejected` / `candidate` -> `approved` -> `contacted` -> `replied` -> `paid`

`POST /opportunities/analyze` stores `rejected` or `candidate` automatically; you move records forward manually via `PATCH`.

## Tests

```bash
pytest -v
```

## Swapping the AI provider

All analysis goes through the `AIProvider` interface (`app/services/ai_provider.py`). Two providers ship today:

- `mock` (default): deterministic, rule-based, zero cost.
- `openai`: any OpenAI-compatible chat-completions endpoint (OpenAI, OpenRouter, Groq, local vLLM), selected via env vars.

To use the real provider:

```bash
export AI_PROVIDER=openai
export OPENAI_API_KEY=sk-...        # never hardcoded; .env works too
# optional:
# export OPENAI_BASE_URL=https://api.openai.com/v1
# export OPENAI_MODEL=gpt-4o-mini
# export OPENAI_TIMEOUT_SECONDS=30
```

The provider requests structured JSON output and validates it with a strict
schema before it enters the pipeline. Invalid/missing model data fails safely
with a clear error (HTTP 502 from the API, `error: ...` from the CLI).
Missing configuration (e.g. no `OPENAI_API_KEY`) fails fast with a clear
message at startup. **The LLM never decides the score** — scoring stays
deterministic in `app/services/scorer.py`.

Missing an API key? Everything still works with `AI_PROVIDER=mock`.

## Manual ingestion & evaluation (CLI)

Paste real opportunities yourself — no scraping, no platform integrations:

```bash
# Add one opportunity (description via flag, file, or piped stdin)
python -m app.cli add \
  --source "local business" \
  --title "Automate daily invoice CSV processing" \
  --url "https://example.com/post" \
  --client "Bistro GmbH" \
  --market "DE / German" \
  --description "We receive CSV invoices daily and staff retype them into our system..."

# Or paste the description interactively / from a file:
cat opportunity.txt | python -m app.cli add --title "..." --source "..."

# Review what was analyzed
python -m app.cli list
python -m app.cli list --status candidate
python -m app.cli show 1

# Export for manual evaluation of your 10 real opportunities
python -m app.cli export --format csv --out evaluation.csv
python -m app.cli export --format json
```

Export rows contain: `id, source, title, analysis_summary, score,
classification, suggested_price, proposal, status`.

## Day 3 — Real opportunity evaluation

Workflow for manually reviewing 10 real freelance opportunities (no scraping,
no platform integration — you paste them yourself). Scoring logic is frozen
during this evaluation; the template lives in
[`docs/day3_evaluation.md`](docs/day3_evaluation.md).

```bash
# 1. Paste a real opportunity (record the returned id)
python -m app.cli add \
  --source "marketplace" --title "title from the post" \
  --url "https://link" --client "company" --market "DE / German" \
  --description "full original post text"

# 2. Print everything the agent produced, for comparison
python -m app.cli eval                # all
python -m app.cli eval --id 1         # one record
python -m app.cli eval --status candidate
```

`eval` prints per opportunity: the original input, the agent's `problem`,
`required_skills`, `difficulty`, `estimated_execution_time`,
`estimated_price_range`, `confidence`, `business_value_explanation`,
`missing_information`, the deterministic `score`, `classification`,
`suggested_fixed_price`, `delivery_estimate`, `problem_summary`,
`proposed_solution`, the full proposal message, and the `INPUT DESCRIPTION`
for checking problem understanding. Then fill in the human-review fields
(`human_score`, `problem_understanding`, `price_realism`,
`time_estimate_realism`, `proposal_quality`, `would_we_pursue`, `notes`)
in `docs/day3_evaluation.md` for each of the 10 records.

## What is intentionally NOT in V1/V2

- Scraping / sourcing of opportunities
- Automatic messaging to clients (proposals are drafts only)
- Payments / invoicing
- Multiple autonomous agents
- A frontend
- Platform integrations (Upwork, Contra, Mostaql, Khamsat, Moltbook, ...)

## V2 ideas

- Feedback loop: track `replied`/`paid` rates per source and per market to tune scoring weights
- Duplicate detection so the same post isn't analyzed twice
- Parsing LLM execution-time labels into `estimated_hours` for tighter speed scoring
