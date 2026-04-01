import logging
import subprocess
import sys
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from sqlalchemy import text

from app.config import settings
from app.database import async_session, engine
from app.router import file_router, job_router
from app.service.job_service import JobService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

hybrid_process = None


def start_hybrid_server() -> subprocess.Popen | None:
    """Start opendataloader-pdf-hybrid server as a background process."""
    try:
        port = settings.hybrid_server_url.split(":")[-1]
        cmd = ["opendataloader-pdf-hybrid", "--port", port]
        if settings.hybrid_force_ocr:
            cmd.append("--force-ocr")
            cmd.extend(["--ocr-lang", settings.hybrid_ocr_lang])
            logger.info(f"Hybrid server OCR enabled: lang={settings.hybrid_ocr_lang}")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Wait for server to be ready
        url = f"{settings.hybrid_server_url}/health"
        for _ in range(30):
            try:
                resp = httpx.get(url, timeout=1.0)
                if resp.status_code == 200:
                    logger.info("Hybrid server started successfully")
                    return proc
            except Exception:
                pass
            time.sleep(1)
        logger.warning("Hybrid server started but health check not responding, proceeding anyway")
        return proc
    except Exception as e:
        logger.warning(f"Could not start hybrid server: {e}")
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global hybrid_process

    # Startup: recover orphaned jobs
    try:
        async with async_session() as db:
            job_service = JobService()
            count = await job_service.recover_orphaned_jobs(db)
            if count > 0:
                logger.info(f"Recovered {count} orphaned jobs on startup")
    except Exception as e:
        logger.warning(f"Could not recover orphaned jobs: {e}")

    # Startup: start hybrid server
    hybrid_process = start_hybrid_server()

    yield

    # Shutdown: stop hybrid server
    if hybrid_process:
        hybrid_process.terminate()
        hybrid_process.wait(timeout=10)
        logger.info("Hybrid server stopped")

    await engine.dispose()


app = FastAPI(
    title="PDF Text Extraction & Chunking API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(file_router.router)
app.include_router(job_router.router)


@app.get("/health")
async def health_check():
    hybrid_status = "running" if hybrid_process and hybrid_process.poll() is None else "stopped"
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected", "hybrid_server": hybrid_status}
    except Exception as e:
        return {"status": "degraded", "database": f"error: {str(e)}", "hybrid_server": hybrid_status}
