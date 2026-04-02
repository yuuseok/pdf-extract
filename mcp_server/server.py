"""MCP server that wraps the PDF Extract REST API."""

from mcp.server.fastmcp import FastMCP

from mcp_server.tools import (
    get_extraction_result,
    get_job_status,
    list_files,
    upload_document,
)

mcp = FastMCP("pdf-extract")


@mcp.tool()
async def upload_document_tool(file_path: str) -> str:
    """Upload a document file and extract text content.

    Uploads a local file (PDF, Word, Excel, PowerPoint, CSV) to the extraction API,
    waits for processing to complete, and returns the extracted text in all three
    formats: plain text, markdown, and JSON.

    Args:
        file_path: Absolute path to the document file on disk.
    """
    return await upload_document(file_path)


@mcp.tool()
async def get_job_status_tool(job_id: str) -> str:
    """Check the processing status of a document extraction job.

    Args:
        job_id: The UUID of the job to check.
    """
    return await get_job_status(job_id)


@mcp.tool()
async def get_extraction_result_tool(job_id: str, format: str = "all") -> str:
    """Get the extraction result of a completed job.

    Args:
        job_id: The UUID of the completed job.
        format: Output format - "text", "markdown", "json", or "all" (default: "all").
    """
    return await get_extraction_result(job_id, format)


@mcp.tool()
async def list_files_tool() -> str:
    """List all uploaded files in the document extraction system."""
    return await list_files()
