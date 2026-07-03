from aca_os.text import normalize_text


def test_normalize_text_removes_extra_spaces():
    assert normalize_text("  que   es   la   indemnizacion?  ") == "que es la indemnizacion?"


def test_normalize_text_lowercases_text():
    assert normalize_text("POLIZA   VENCIDA") == "poliza vencida"


def test_normalize_text_handles_empty_values():
    assert normalize_text(None) == ""
    assert normalize_text("") == ""