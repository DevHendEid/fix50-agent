# Day 3 — Real Opportunity Evaluation

- **Date:** _(fill in)_
- **Agent version:** V1/V2 — scoring logic **unchanged** before this evaluation
- **Goal:** manually review 10 real freelance opportunities and compare what the agent produced against human judgment.

> Rules: no scaling/scraping, no platform integration, no messaging. The 10
> opportunities are pasted manually from real marketplaces (copy/paste only).
> Scoring weights are **not** modified today.

---

## How to add each real opportunity

```bash
python -m app.cli add \
  --source "where you found it (marketplace name / community)" \
  --title "title exactly as posted" \
  --url "https://original-post-link" \
  --client "client or company name (if visible/mentioned)" \
  --market "country / language, e.g. DE / German" \
  --description "full original post text, pasted verbatim"
```

The description can also come from a file or stdin instead of the flag:

```bash
cat post.txt | python -m app.cli add --title "..." --source "..."
python -m app.cli add --title "..." --description-file post.txt
```

Record the returned `id:` — it becomes `opportunity_id` in the review below.

## How to view the agent output for each opportunity

```bash
# Everything the agent produced, for every stored opportunity
python -m app.cli eval

# Just one record
python -m app.cli eval --id 1

# Only candidates / new / etc.
python -m app.cli eval --status candidate

# Compact table for a quick overview
python -m app.cli list

# CSV/JSON export (spreadsheet-friendly, no full proposal text)
python -m app.cli export --format csv --out evaluation.csv
python -m app.cli export --format json
```

`python -m app.cli eval` prints per opportunity:
`opportunity_id, source, title, url, client, market, status`, then the full
agent analysis (`problem, required_skills, difficulty,
estimated_execution_time, estimated_price_range, confidence,
business_value_explanation, missing_information`), the `deterministic_score`
and `classification`, the `suggested_fixed_price`, `delivery_estimate`,
`problem_summary`, `proposed_solution`, the full proposal message, and the
original `INPUT DESCRIPTION` so you can check problem understanding against
what was actually posted.

## Fill-in legend

| Field | Values | Meaning |
|---|---|---|
| `human_score` | 0–100 | Your own score for the opportunity (same rubric idea: clarity, business value, speed, explainability, contactability, credibility) |
| `problem_understanding` | good / acceptable / bad | Does the agent's extracted `problem` match the post? |
| `price_realism` | good / high / low | Is `suggested_fixed_price` / `estimated_price_range` realistic for this client/market? |
| `time_estimate_realism` | good / high / low | Is `estimated_execution_time` realistic for the difficulty? |
| `proposal_quality` | sendable / needs_edit / bad | Could the generated proposal be sent as-is / after small edits / not at all |
| `would_we_pursue` | yes / no | Would you actually follow up on this one this week? |
| `notes` | free text | Gaps between human and agent judgment, what's wrong, what to improve |

---

# Opportunities

## 1.

- opportunity_id:
- source:
- title:
- agent_score:
- agent_classification:
- human_score (0-100):
- problem_understanding: good / acceptable / bad
- price_realism: good / high / low
- time_estimate_realism: good / high / low
- proposal_quality: sendable / needs_edit / bad
- would_we_pursue: yes / no
- notes:

## 2.

- opportunity_id:
- source:
- title:
- agent_score:
- agent_classification:
- human_score (0-100):
- problem_understanding: good / acceptable / bad
- price_realism: good / high / low
- time_estimate_realism: good / high / low
- proposal_quality: sendable / needs_edit / bad
- would_we_pursue: yes / no
- notes:

## 3.

- opportunity_id:
- source:
- title:
- agent_score:
- agent_classification:
- human_score (0-100):
- problem_understanding: good / acceptable / bad
- price_realism: good / high / low
- time_estimate_realism: good / high / low
- proposal_quality: sendable / needs_edit / bad
- would_we_pursue: yes / no
- notes:

## 4.

- opportunity_id:
- source:
- title:
- agent_score:
- agent_classification:
- human_score (0-100):
- problem_understanding: good / acceptable / bad
- price_realism: good / high / low
- time_estimate_realism: good / high / low
- proposal_quality: sendable / needs_edit / bad
- would_we_pursue: yes / no
- notes:

## 5.

- opportunity_id:
- source:
- title:
- agent_score:
- agent_classification:
- human_score (0-100):
- problem_understanding: good / acceptable / bad
- price_realism: good / high / low
- time_estimate_realism: good / high / low
- proposal_quality: sendable / needs_edit / bad
- would_we_pursue: yes / no
## 6.

- opportunity_id:
- source:
- title:
- agent_score:
- agent_classification:
- human_score (0-100):
- problem_understanding: good / acceptable / bad
- price_realism: good / high / low
- time_estimate_realism: good / high / low
- proposal_quality: sendable / needs_edit / bad
- would_we_pursue: yes / no
- notes:

## 7.

- opportunity_id:
- source:
- title:
- agent_score:
- agent_classification:
- human_score (0-100):
- problem_understanding: good / acceptable / bad
- price_realism: good / high / low
- time_estimate_realism: good / high / low
- proposal_quality: sendable / needs_edit / bad
- would_we_pursue: yes / no
- notes:

## 8.

- opportunity_id:
- source:
- title:
- agent_score:
- agent_classification:
- human_score (0-100):
- problem_understanding: good / acceptable / bad
- price_realism: good / high / low
- time_estimate_realism: good / high / low
- proposal_quality: sendable / needs_edit / bad
- would_we_pursue: yes / no
- notes:

## 9.

- opportunity_id:
- source:
- title:
- agent_score:
- agent_classification:
- human_score (0-100):
- problem_understanding: good / acceptable / bad
- price_realism: good / high / low
- time_estimate_realism: good / high / low
- proposal_quality: sendable / needs_edit / bad
- would_we_pursue: yes / no
- notes:

## 10.

- opportunity_id:
- source:
- title:
- agent_score:
- agent_classification:
- human_score (0-100):
- problem_understanding: good / acceptable / bad
- price_realism: good / high / low
- time_estimate_realism: good / high / low
- proposal_quality: sendable / needs_edit / bad
- would_we_pursue: yes / no
- notes:

---

## Summary (fill after reviewing all 10)

- opportunities reviewed:
- agent rejected / candidate / strong:
- human disagreeing with agent score (|Δ| >= 15):
- consensus issues spotted (price, time, problem, proposal):
- actions for Day 4 (scoring weights, proposal template, provider tweaks):
- notes: