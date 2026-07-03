from aca_os.text import normalize_text, repair_mojibake


def test_normalize_text_removes_accents_and_extra_spaces():
    text = "\u00bfQu\u00e9 es la indemnizaci\u00f3n?"

    assert normalize_text(f"  {text}  ") == "\u00bfque es la indemnizacion?"
    assert normalize_text("P\u00d3LIZA   VENCIDA") == "poliza vencida"


def test_normalize_text_repairs_common_mojibake():
    mojibake = "\u00bfQu\u00e9 es la indemnizaci\u00f3n?".encode("utf-8").decode("latin1")

    assert repair_mojibake(mojibake) == "\u00bfQu\u00e9 es la indemnizaci\u00f3n?"
    assert normalize_text(mojibake) == "\u00bfque es la indemnizacion?"