import io
import pytest


@pytest.mark.asyncio
async def test_upload_pdf(client):
    pdf_content = b"%PDF-1.4 fake content"
    response = await client.post(
        "/api/v1/files/upload",
        files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
        data={"chunking_strategy": "semantic"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "file_id" in data
    assert "job_id" in data
    assert data["status"] == "PENDING"


@pytest.mark.asyncio
async def test_upload_non_pdf_rejected(client):
    response = await client.post(
        "/api/v1/files/upload",
        files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_files(client):
    response = await client.get("/api/v1/files")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_nonexistent_file(client):
    response = await client.get("/api/v1/files/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
