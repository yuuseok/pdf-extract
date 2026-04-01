from app.service.text_normalizer import TextNormalizer


def test_brackets():
    n = TextNormalizer()
    assert n.normalize("｢테스트｣") == '"테스트"'
    assert n.normalize("「테스트」") == '"테스트"'


def test_quotes():
    n = TextNormalizer()
    assert n.normalize("\u2018테스트\u2019") == "'테스트'"


def test_symbols():
    n = TextNormalizer()
    assert n.normalize("￭ 항목1") == "· 항목1"
    assert n.normalize("‧ 항목2") == "· 항목2"


def test_units():
    n = TextNormalizer()
    assert n.normalize("26,477,108㎡") == "26,477,108m²"
    assert n.normalize("86.07㎢") == "86.07km²"


def test_roman_numerals():
    n = TextNormalizer()
    assert n.normalize("Ⅰ. 개요") == "I. 개요"
    assert n.normalize("Ⅱ. 내용") == "II. 내용"


def test_private_use_area_removed():
    n = TextNormalizer()
    assert n.normalize("테스트\uF000문자") == "테스트문자"


def test_fullwidth_to_halfwidth():
    n = TextNormalizer()
    assert n.normalize("Ａ Ｂ Ｃ") == "A B C"
    assert n.normalize("０１２") == "012"


def test_whitespace_cleanup():
    n = TextNormalizer()
    assert n.normalize("여러    공백") == "여러 공백"
    assert n.normalize("줄1\n\n\n\n줄2") == "줄1\n\n줄2"


def test_empty_and_none():
    n = TextNormalizer()
    assert n.normalize("") == ""
    assert n.normalize(None) is None


def test_real_world_sample():
    n = TextNormalizer()
    raw = "｢2026년 물순환 촉진구역 지정｣ 공모\n￭ 촉진구역 면적 : 26,477,108㎡\nⅠ. 촉진구역 개요"
    expected = '"2026년 물순환 촉진구역 지정" 공모\n· 촉진구역 면적 : 26,477,108m²\nI. 촉진구역 개요'
    assert n.normalize(raw) == expected
