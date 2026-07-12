from aca_core.text import normalize_search_text, normalize_text, repair_mojibake


def test_normalize_text_removes_extra_spaces():
    assert normalize_text("  que   es   la   indemnizacion?  ") == "que es la indemnizacion?"


def test_normalize_text_lowercases_text():
    assert normalize_text("POLIZA   VENCIDA") == "poliza vencida"


def test_normalize_text_handles_empty_values():
    assert normalize_text(None) == ""
    assert normalize_text("") == ""


def test_normalize_text_repairs_common_mojibake():
    assert normalize_text("LÃ­mites del agente") == "limites del agente"


def test_normalize_text_is_idempotent():
    normalized = normalize_text("  Póliza   VENCIDA  ")
    assert normalize_text(normalized) == normalized


def test_normalize_search_text_removes_punctuation():
    assert normalize_search_text("¿Qué podés hacer?") == "que podes hacer"


def test_normalize_search_text_can_collapse_common_typos():
    assert normalize_search_text("haceeer algo másss?", typo_tolerant=True) == "hacer algo mas"


def test_repair_mojibake_leaves_clean_text_unchanged():
    assert repair_mojibake("póliza") == "póliza"
