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


def test_toc_dots_removed():
    n = TextNormalizer()
    assert n.normalize("1. 조사 목적·························································3") == "1. 조사 목적"
    assert n.normalize("1) 표본규모 결정······················································4") == "1) 표본규모 결정"


def test_page_number_lines_removed():
    n = TextNormalizer()
    assert n.normalize("내용\n3\n다음내용") == "내용\n다음내용"
    assert n.normalize("내용\n94\n다음내용") == "내용\n다음내용"
    # 4자리 이상은 유지 (숫자 데이터일 수 있음)
    assert "1234" in n.normalize("내용\n1234\n다음내용")


def test_bullet_l_to_dot():
    n = TextNormalizer()
    assert n.normalize("l 본 조사는 경상북도 도민의") == "· 본 조사는 경상북도 도민의"
    assert n.normalize("l 통계법 제15조") == "· 통계법 제15조"
    # 일반 영어 l은 변환하지 않음
    assert n.normalize("let me check") == "let me check"


def test_combined_patterns():
    n = TextNormalizer()
    raw = "l 안동시 면적(㎢)은 ｢도시계획｣에 따라\n1. 개요···················3\n94\nl (참고) 추가 설명"
    result = n.normalize(raw)
    assert "· 안동시 면적(km²)은" in result
    assert "···" not in result
    assert "\n94\n" not in result
    assert "· (참고) 추가 설명" in result
