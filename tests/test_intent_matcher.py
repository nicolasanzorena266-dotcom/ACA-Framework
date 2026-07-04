from zero_cost.intent_matcher import IntentMatcher


def test_intent_matcher_detects_auto_claim_guidance():
    match = IntentMatcher().match("Me chocaron ayer y el tercero no hizo denuncia")

    assert match.intent == "auto_claim_guidance"
    assert match.confidence > 0
    assert "me chocaron" in match.matched_terms


def test_intent_matcher_detects_concept_franquicia():
    match = IntentMatcher().match("Que es la franquicia?")

    assert match.intent == "concept_franquicia"


def test_intent_matcher_detects_real_claim_status():
    match = IntentMatcher().match("Ya aprobaron mi indemnizacion?")

    assert match.intent == "real_claim_status"


def test_intent_matcher_fallback_when_no_rule_matches():
    match = IntentMatcher().match("asdf qwer zxcv")

    assert match.intent == "fallback"
    assert match.confidence == 0