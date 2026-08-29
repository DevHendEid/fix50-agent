# Day 4 — Scoring Calibration

Goal: improve opportunity selection after the 10-opportunity Day 3 real-provider evaluation without overfitting to that sample.

## Observed Day 3 failures

- 10/10 opportunities were rejected.
- Real-provider execution-time labels were not converted to `estimated_hours`, so speed scoring defaulted instead of using the model's estimate.
- Business-value scoring relied mostly on English keyword matches and underweighted Arabic opportunities.
- Marketplace jobs without a visible client name were penalized for contactability despite being directly contactable through the listing.
- Low-value jobs such as a $10 fixed Flutter task could be rejected, but not because economics were explicitly modeled.

## Day 4 changes

1. Parse common duration labels conservatively into hours.
2. Use the provider's explicit business-value explanation as scoring evidence, with multilingual keyword support as a secondary signal.
3. Treat marketplace URLs as directly contactable.
4. Add a hard Fix50 economics guardrail: if the full realistic price range is below $50, classification is rejected.
5. Keep the original six rubric dimensions and 70/85 thresholds unchanged.
6. Distinguish empty HTTP-200 LLM content from malformed JSON for clearer diagnostics.

## Validation rule

Do not judge success by whether all Day 3 opportunities become candidates. The intended behavior is selective:

- clear, quick, >= $50 work should normally survive the first filter;
- vague, risky, slow, or sub-$50 work should still be rejected;
- the scorer must remain deterministic and independent from the LLM's final judgment.

## Next validation

Run the full test suite, then rescore/re-ingest a fresh set of real opportunities rather than tuning further on the same ten records.
