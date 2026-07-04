# Sprint 20 - Zero-Cost Intent Matcher

## Added

- `zero_cost/intent_matcher.py`
- IntentMatch model
- rule-based IntentMatcher
- runtime integration
- intent_match stored in CSM
- intent_match exposed in ACAOutput
- tests

## Architectural meaning

ACA now begins Phase 2: Zero-Cost Agent Runtime.

The system can classify user intent without LLMs, embeddings or paid APIs.