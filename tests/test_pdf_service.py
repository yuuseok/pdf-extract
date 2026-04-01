from unittest.mock import patch
from app.service.pdf_service import PdfService


def test_extract_returns_three_formats():
    pdf_service = PdfService()
    mock_convert_result = None  # convert writes files, we mock file reading

    with patch("opendataloader_pdf.convert"):
        with patch("builtins.open") as mock_open:
            with patch("os.path.exists", return_value=False):
                result = pdf_service.extract("/tmp/test.pdf")

    # With no files existing, should return empty but correct structure
    assert "text" in result
    assert "markdown" in result
    assert "json" in result
    assert "page_count" in result


def test_extract_real_pdf_if_available():
    """Integration test with a real PDF file (skipped if no file available)."""
    import os
    test_pdf = "/home/yusuk/documents/ai_workspace/hancom-pdf/uploads/047e1518-f7d4-4934-b98a-ae3078a80496.pdf"
    if not os.path.exists(test_pdf):
        return  # skip if no test file

    pdf_service = PdfService()
    result = pdf_service.extract(test_pdf)
    assert len(result["text"]) > 0
    assert len(result["markdown"]) > 0
    assert len(result["json"]) > 0
    assert result["page_count"] is not None
