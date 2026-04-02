"""HwpxService 단위 테스트."""

import os
import tempfile

import pytest

from app.service.hwpx_service import HwpxService


@pytest.fixture
def hwpx_service():
    return HwpxService()


def _create_sample_hwpx() -> str:
    """python-hwpx로 테스트용 HWPX 파일을 생성한다."""
    from hwpx import HwpxDocument

    doc = HwpxDocument.new()
    doc.add_paragraph("첫 번째 문단입니다.")
    doc.add_paragraph("두 번째 문단입니다.")

    # 테이블 추가 (rows, cols로 생성 후 셀 텍스트 설정)
    table_data = [
        ["이름", "나이", "직업"],
        ["홍길동", "30", "개발자"],
        ["김철수", "25", "디자이너"],
    ]
    tbl = doc.add_table(rows=3, cols=3)
    for r, row in enumerate(table_data):
        for c, cell_text in enumerate(row):
            tbl.set_cell_text(r, c, cell_text)

    doc.add_paragraph("마지막 문단입니다.")

    tmp = tempfile.NamedTemporaryFile(suffix=".hwpx", delete=False)
    doc.save_to_path(tmp.name)
    doc.close()
    return tmp.name


class TestHwpxServiceExtract:
    """extract() 메서드 테스트."""

    def test_extract_returns_correct_keys(self, hwpx_service):
        """추출 결과에 필수 키가 모두 포함되어야 한다."""
        path = _create_sample_hwpx()
        try:
            result = hwpx_service.extract(path)
            assert "text" in result
            assert "markdown" in result
            assert "json" in result
            assert "json_raw" in result
            assert "page_count" in result
        finally:
            os.unlink(path)

    def test_extract_text_content(self, hwpx_service):
        """텍스트에 문단 내용이 포함되어야 한다."""
        path = _create_sample_hwpx()
        try:
            result = hwpx_service.extract(path)
            assert "첫 번째 문단입니다." in result["text"]
            assert "두 번째 문단입니다." in result["text"]
            assert "마지막 문단입니다." in result["text"]
        finally:
            os.unlink(path)

    def test_extract_markdown_content(self, hwpx_service):
        """마크다운에 문단 및 테이블이 포함되어야 한다."""
        path = _create_sample_hwpx()
        try:
            result = hwpx_service.extract(path)
            md = result["markdown"]
            assert "첫 번째 문단입니다." in md
            # 마크다운 테이블 형식 확인
            assert "|" in md
            assert "이름" in md
            assert "홍길동" in md
        finally:
            os.unlink(path)

    def test_extract_json_structure(self, hwpx_service):
        """JSON 결과가 구조화된 요소 리스트여야 한다."""
        path = _create_sample_hwpx()
        try:
            result = hwpx_service.extract(path)
            elements = result["json"]
            assert isinstance(elements, list)
            assert len(elements) > 0

            # paragraph 타입 요소 확인
            paragraphs = [e for e in elements if e["type"] == "paragraph"]
            assert len(paragraphs) >= 3

            # table 타입 요소 확인
            tables = [e for e in elements if e["type"] == "table"]
            assert len(tables) >= 1
            assert "rows" in tables[0]
            assert len(tables[0]["rows"]) == 3  # 헤더 + 2행
        finally:
            os.unlink(path)

    def test_extract_page_count(self, hwpx_service):
        """page_count가 반환되어야 한다."""
        path = _create_sample_hwpx()
        try:
            result = hwpx_service.extract(path)
            assert result["page_count"] is not None
            assert result["page_count"] >= 1
        finally:
            os.unlink(path)

    def test_extract_json_raw(self, hwpx_service):
        """json_raw에 elements와 sections 키가 있어야 한다."""
        path = _create_sample_hwpx()
        try:
            result = hwpx_service.extract(path)
            assert "elements" in result["json_raw"]
            assert "sections" in result["json_raw"]
        finally:
            os.unlink(path)


class TestHwpxServiceErrors:
    """에러 처리 테스트."""

    def test_extract_nonexistent_file(self, hwpx_service):
        """존재하지 않는 파일은 ValueError를 발생시켜야 한다."""
        with pytest.raises(ValueError, match="HWPX 파일을 열 수 없습니다"):
            hwpx_service.extract("/nonexistent/file.hwpx")

    def test_extract_invalid_file(self, hwpx_service):
        """유효하지 않은 파일(예: 일반 텍스트)은 ValueError를 발생시켜야 한다."""
        with tempfile.NamedTemporaryFile(suffix=".hwpx", delete=False, mode="w") as f:
            f.write("this is not a valid hwpx file")
            path = f.name
        try:
            with pytest.raises(ValueError, match="HWPX 파일을 열 수 없습니다"):
                hwpx_service.extract(path)
        finally:
            os.unlink(path)

    def test_extract_binary_hwp_fails(self, hwpx_service):
        """바이너리 HWP 파일은 ValueError를 발생시켜야 한다."""
        with tempfile.NamedTemporaryFile(suffix=".hwp", delete=False, mode="wb") as f:
            # HWP 바이너리 시그니처 (OLE compound document)
            f.write(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100)
            path = f.name
        try:
            with pytest.raises(ValueError, match="HWPX 파일을 열 수 없습니다"):
                hwpx_service.extract(path)
        finally:
            os.unlink(path)


class TestHwpxServiceSupportedExtensions:
    """지원 확장자 확인."""

    def test_supported_extensions(self):
        assert ".hwpx" in HwpxService.SUPPORTED_EXTENSIONS
