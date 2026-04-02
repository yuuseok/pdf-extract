"""Tests for the MCP server tool definitions and basic structure."""

import importlib

import pytest


def test_mcp_server_module_imports():
    """mcp_server package is importable."""
    mod = importlib.import_module("mcp_server")
    assert mod is not None


def test_tools_module_imports():
    """mcp_server.tools module is importable."""
    mod = importlib.import_module("mcp_server.tools")
    assert mod is not None


def test_server_module_imports():
    """mcp_server.server module is importable and exposes mcp instance."""
    mod = importlib.import_module("mcp_server.server")
    assert hasattr(mod, "mcp")


def test_tool_functions_exist():
    """All expected tool functions are defined in tools module."""
    from mcp_server import tools

    assert callable(getattr(tools, "upload_document", None))
    assert callable(getattr(tools, "get_job_status", None))
    assert callable(getattr(tools, "get_extraction_result", None))
    assert callable(getattr(tools, "list_files", None))


def test_mcp_tools_registered():
    """MCP server has all four tools registered."""
    from mcp_server.server import mcp

    tool_names = {name for name in mcp._tool_manager._tools}
    expected = {"upload_document_tool", "get_job_status_tool", "get_extraction_result_tool", "list_files_tool"}
    assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"


def test_upload_document_is_async():
    """upload_document should be an async function."""
    import asyncio
    from mcp_server.tools import upload_document

    assert asyncio.iscoroutinefunction(upload_document)


def test_pdf_api_url_default():
    """PDF_API_URL defaults to http://localhost:8000."""
    from mcp_server.tools import PDF_API_URL

    assert PDF_API_URL == "http://localhost:8000"


@pytest.mark.asyncio
async def test_upload_document_file_not_found():
    """upload_document returns an error for a non-existent file."""
    from mcp_server.tools import upload_document

    result = await upload_document("/tmp/nonexistent_file_abc123.pdf")
    assert "Error" in result
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_get_extraction_result_invalid_format():
    """get_extraction_result rejects invalid format values."""
    from mcp_server.tools import get_extraction_result

    result = await get_extraction_result("some-job-id", format="invalid")
    assert "Error" in result
    assert "invalid" in result.lower()
