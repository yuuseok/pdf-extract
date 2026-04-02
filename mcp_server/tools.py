"""MCP tool definitions for the PDF Extract API."""

import asyncio
import os
from pathlib import Path

import httpx

PDF_API_URL = os.environ.get("PDF_API_URL", "http://localhost:8000")
POLL_INTERVAL = 2  # seconds


def _api_url(path: str) -> str:
    return f"{PDF_API_URL}{path}"


async def upload_document(file_path: str) -> str:
    """Upload a document file and extract text content.

    Uploads a local file (PDF, Word, Excel, PowerPoint, CSV) to the extraction API,
    waits for processing to complete, and returns the extracted text in all formats.

    Args:
        file_path: Absolute path to the document file on disk.

    Returns:
        Extracted content as a formatted string with text, markdown, and JSON sections.
    """
    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"
    if not path.is_file():
        return f"Error: Not a file: {file_path}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Upload file
        with open(path, "rb") as f:
            files = {"file": (path.name, f)}
            try:
                resp = await client.post(_api_url("/api/v1/files/upload"), files=files)
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                return f"Error uploading file: {e.response.status_code} - {e.response.text}"
            except httpx.RequestError as e:
                return f"Error connecting to API: {e}"

        data = resp.json()
        job_id = data["job_id"]
        file_id = data["file_id"]

        # Poll until job completes
        for _ in range(150):  # max 5 minutes
            await asyncio.sleep(POLL_INTERVAL)
            try:
                status_resp = await client.get(_api_url(f"/api/v1/jobs/{job_id}"))
                status_resp.raise_for_status()
            except httpx.HTTPError:
                continue

            job = status_resp.json()
            status = job["status"]

            if status == "COMPLETED":
                # Get result
                try:
                    result_resp = await client.get(_api_url(f"/api/v1/jobs/{job_id}/result"))
                    result_resp.raise_for_status()
                except httpx.HTTPStatusError as e:
                    return f"Job completed but failed to fetch result: {e.response.status_code}"

                result = result_resp.json()
                return _format_result(result, file_id, job_id)

            elif status == "FAILED":
                error_msg = job.get("error_message", "Unknown error")
                return f"Job failed: {error_msg}\n(job_id: {job_id}, file_id: {file_id})"

        return f"Timeout: Job did not complete within 5 minutes.\n(job_id: {job_id}, file_id: {file_id})"


async def get_job_status(job_id: str) -> str:
    """Check the processing status of a document extraction job.

    Args:
        job_id: The UUID of the job to check.

    Returns:
        Job status information as a formatted string.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(_api_url(f"/api/v1/jobs/{job_id}"))
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            return f"Error: {e.response.status_code} - {e.response.text}"
        except httpx.RequestError as e:
            return f"Error connecting to API: {e}"

    job = resp.json()
    lines = [
        f"Job ID: {job['id']}",
        f"File ID: {job['file_id']}",
        f"Status: {job['status']}",
        f"Chunking: {job['chunking_strategy']}",
        f"OCR: {job['ocr_enabled']}",
        f"Hybrid: {job['use_hybrid']}",
    ]
    if job.get("error_message"):
        lines.append(f"Error: {job['error_message']}")
    if job.get("started_at"):
        lines.append(f"Started: {job['started_at']}")
    if job.get("finished_at"):
        lines.append(f"Finished: {job['finished_at']}")
    return "\n".join(lines)


async def get_extraction_result(job_id: str, format: str = "all") -> str:
    """Get the extraction result of a completed job.

    Args:
        job_id: The UUID of the completed job.
        format: Output format - "text", "markdown", "json", or "all" (default: "all").

    Returns:
        Extracted content in the requested format.
    """
    valid_formats = ("text", "markdown", "json", "all")
    if format not in valid_formats:
        return f"Error: Invalid format '{format}'. Must be one of: {', '.join(valid_formats)}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(_api_url(f"/api/v1/jobs/{job_id}/result"))
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            return f"Error: {e.response.status_code} - {e.response.text}"
        except httpx.RequestError as e:
            return f"Error connecting to API: {e}"

    result = resp.json()

    if format == "all":
        return _format_result(result, result.get("file_id", "N/A"), job_id)
    elif format == "text":
        return result.get("content_text") or "(no text content)"
    elif format == "markdown":
        return result.get("content_markdown") or "(no markdown content)"
    elif format == "json":
        import json
        content = result.get("content_json")
        if content is None:
            return "(no JSON content)"
        return json.dumps(content, ensure_ascii=False, indent=2)

    return ""


async def list_files() -> str:
    """List all uploaded files.

    Returns:
        A formatted list of uploaded files with their IDs, names, and sizes.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(_api_url("/api/v1/files"), params={"page": 1, "per_page": 50})
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            return f"Error: {e.response.status_code} - {e.response.text}"
        except httpx.RequestError as e:
            return f"Error connecting to API: {e}"

    data = resp.json()
    items = data.get("items", [])
    if not items:
        return "No files found."

    lines = [f"Files (total: {data.get('total', len(items))}):", ""]
    for f in items:
        size_kb = f.get("file_size", 0) / 1024
        lines.append(
            f"- {f['original_filename']} ({size_kb:.1f} KB)\n"
            f"  ID: {f['id']} | Extension: {f['file_extension']} | "
            f"Pages: {f.get('page_count', 'N/A')} | Created: {f['created_at']}"
        )
    return "\n".join(lines)


def _format_result(result: dict, file_id: str, job_id: str) -> str:
    """Format extraction result into an LLM-friendly string."""
    text = result.get("content_text") or ""
    markdown = result.get("content_markdown") or ""

    # Truncate very long content for readability
    max_section = 10000
    text_display = text[:max_section] + "\n... (truncated)" if len(text) > max_section else text
    md_display = markdown[:max_section] + "\n... (truncated)" if len(markdown) > max_section else markdown

    parts = [
        f"file_id: {file_id}",
        f"job_id: {job_id}",
        "",
        "=== TEXT ===",
        text_display or "(empty)",
        "",
        "=== MARKDOWN ===",
        md_display or "(empty)",
    ]

    content_json = result.get("content_json")
    if content_json:
        import json
        json_str = json.dumps(content_json, ensure_ascii=False, indent=2)
        json_display = json_str[:max_section] + "\n... (truncated)" if len(json_str) > max_section else json_str
        parts.extend(["", "=== JSON ===", json_display])

    return "\n".join(parts)
