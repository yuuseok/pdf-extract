from app.service.quality_checker import QualityChecker


def test_normal_pdf_passes():
    checker = QualityChecker()
    extraction = {
        "text": "정상적인 텍스트 내용 " * 100,
        "json": [{"type": "paragraph", "content": "정상 내용"}],
    }
    result = checker.check(extraction, page_count=5)
    assert result.passed is True
    assert result.reason is None


def test_scan_pdf_detected():
    checker = QualityChecker()
    extraction = {
        "text": "SAMPLE",  # 3페이지에 6자 → 페이지당 2자
        "json": [],
    }
    result = checker.check(extraction, page_count=3)
    assert result.passed is False
    assert result.reason == "scan_detected"
    assert result.recommended_mode == "ocr"


def test_empty_text_detected_as_scan():
    checker = QualityChecker()
    extraction = {"text": "", "json": []}
    result = checker.check(extraction, page_count=10)
    assert result.passed is False
    assert result.reason == "scan_detected"


def test_broken_chars_detected():
    checker = QualityChecker()
    # 20% Private Use Area 문자
    normal = "가나다라마" * 8  # 40자
    broken = "\uE000" * 10     # 10자
    extraction = {"text": normal + broken, "json": []}
    result = checker.check(extraction, page_count=1)
    assert result.passed is False
    assert result.reason == "broken_chars"
    assert result.recommended_mode == "ocr"


def test_low_broken_chars_passes():
    checker = QualityChecker()
    normal = "정상 텍스트 " * 100
    broken = "\uE000"  # 1개만
    extraction = {"text": normal + broken, "json": []}
    result = checker.check(extraction, page_count=1)
    assert result.passed is True


def test_page_count_none_handled():
    checker = QualityChecker()
    extraction = {"text": "충분한 텍스트 " * 50, "json": []}
    result = checker.check(extraction, page_count=None)
    assert result.passed is True


def test_details_always_present():
    checker = QualityChecker()
    extraction = {"text": "텍스트 " * 100, "json": []}
    result = checker.check(extraction, page_count=5)
    assert "scan_check" in result.details
    assert "table_check" in result.details
    assert "broken_chars_check" in result.details
