import os
import tempfile
from app.service.csv_service import CsvService


def _create_test_csv(path: str, delimiter: str = ","):
    with open(path, "w", encoding="utf-8") as f:
        f.write(delimiter.join(["이름", "나이", "도시"]) + "\n")
        f.write(delimiter.join(["홍길동", "30", "서울"]) + "\n")
        f.write(delimiter.join(["김철수", "25", "부산"]) + "\n")


def test_csv_extract_returns_three_formats():
    svc = CsvService()
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        _create_test_csv(f.name)
        result = svc.extract(f.name)
    os.unlink(f.name)

    assert "text" in result
    assert "markdown" in result
    assert "json" in result
    assert "홍길동" in result["text"]


def test_csv_markdown_table():
    svc = CsvService()
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        _create_test_csv(f.name)
        result = svc.extract(f.name)
    os.unlink(f.name)

    assert "| 이름 | 나이 | 도시 |" in result["markdown"]
    assert "| 홍길동 | 30 | 서울 |" in result["markdown"]


def test_tsv_extract():
    svc = CsvService()
    with tempfile.NamedTemporaryFile(suffix=".tsv", delete=False, mode="w") as f:
        _create_test_csv(f.name, delimiter="\t")
        result = svc.extract(f.name)
    os.unlink(f.name)

    assert "홍길동" in result["text"]
    assert "홍길동" in result["markdown"]


def test_csv_json_structure():
    svc = CsvService()
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        _create_test_csv(f.name)
        result = svc.extract(f.name)
    os.unlink(f.name)

    assert len(result["json"]) == 1
    assert result["json"][0]["type"] == "table"
    assert result["json"][0]["row_count"] == 3
