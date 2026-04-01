import os
import tempfile
from openpyxl import Workbook
from app.service.xlsx_service import XlsxService


def _create_test_xlsx(path: str):
    wb = Workbook()
    ws = wb.active
    ws.title = "데이터"
    ws.append(["이름", "나이", "도시"])
    ws.append(["홍길동", 30, "서울"])
    ws.append(["김철수", 25, "부산"])
    wb.save(path)


def test_xlsx_extract_returns_three_formats():
    svc = XlsxService()
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        _create_test_xlsx(f.name)
        result = svc.extract(f.name)
    os.unlink(f.name)

    assert "text" in result
    assert "markdown" in result
    assert "json" in result
    assert "홍길동" in result["text"]
    assert "홍길동" in result["markdown"]


def test_xlsx_sheet_structure():
    svc = XlsxService()
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        _create_test_xlsx(f.name)
        result = svc.extract(f.name)
    os.unlink(f.name)

    sheets = result["json"]
    assert len(sheets) == 1
    assert sheets[0]["sheet_name"] == "데이터"
    assert sheets[0]["row_count"] == 3


def test_xlsx_markdown_table():
    svc = XlsxService()
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        _create_test_xlsx(f.name)
        result = svc.extract(f.name)
    os.unlink(f.name)

    assert "| 이름 | 나이 | 도시 |" in result["markdown"]
    assert "| 홍길동 | 30 | 서울 |" in result["markdown"]
