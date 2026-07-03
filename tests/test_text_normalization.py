from aca_os.text import normalize_text


def test_normalize_text_removes_accents_and_extra_spaces():
    assert normalize_text("  Â¿QuÃ© es la indemnizaciÃ³n?  ") == "Â¿que es la indemnizacion?"
    assert normalize_text("PÃ“LIZA   VENCIDA") == "poliza vencida"