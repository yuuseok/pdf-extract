from app.schema.schemas import UploadRequest


def test_upload_request_defaults():
    req = UploadRequest()
    assert req.chunking_strategy == "semantic"
    assert req.chunk_size == 500
    assert req.chunk_overlap == 50
    assert req.ocr_enabled is False


def test_upload_request_invalid_strategy():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        UploadRequest(chunking_strategy="invalid")
