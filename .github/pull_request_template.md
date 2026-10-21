## Summary

<!-- What changed, and which module it touches: evaluate, enforce, release, or the demo. -->

## Test plan

- [ ] `ruff check src tests examples`
- [ ] `pytest`
- [ ] `sentinel-eval run datasets/product_support.jsonl --mutations --min-pass-rate 0.80`
- [ ] `agent-guardrails demo`

## Notes

<!-- Call out synthetic fixtures, policy changes, and anything a reviewer should not treat as a production measurement. -->
