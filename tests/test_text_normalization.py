from aca_os.text import normalize_text, repair_mojibake


def test_normalize_text_removes_accents_and_extra_spaces():
    text = bytes.fromhex("c2bf5175c3a9206573206c6120696e64656d6e697a616369c3b36e3f").decode("utf-8")

    assert normalize_text(f"  {text}  ") == "Â¿que es la indemnizacion?"
    assert normalize_text("P\u00d3LIZA   VENCIDA") == "poliza vencida"


def test_normalize_text_repairs_common_mojibake():
    expected = bytes.fromhex("c2bf5175c3a9206573206c6120696e64656d6e697a616369c3b36e3f").decode("utf-8")
    mojibake = bytes.fromhex("c382c2bf5175c383c2a9206573206c6120696e64656d6e697a616369c383c2b36e3f").decode("utf-8")

    assert repair_mojibake(mojibake) == expected
    assert normalize_text(mojibake) == "Â¿que es la indemnizacion?"