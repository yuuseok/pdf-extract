import logging
import shutil
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

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
    """Start opendataloader-pdf-hybrid server as a background process (local mode only)."""
    try:
        port = settings.hybrid_server_url.split(":")[-1]

        # venv 내 바이너리 경로를 우선 사용
        hybrid_bin = shutil.which("opendataloader-pdf-hybrid")
        if not hybrid_bin:
            venv_bin = Path(sys.executable).parent / "opendataloader-pdf-hybrid"
            if venv_bin.exists():
                hybrid_bin = str(venv_bin)
            else:
                raise FileNotFoundError("opendataloader-pdf-hybrid not found in PATH or venv")

        cmd = [hybrid_bin, "--port", port]
        if settings.hybrid_force_ocr:
            cmd.append("--force-ocr")
            cmd.extend(["--ocr-lang", settings.hybrid_ocr_lang])
            logger.info(f"Hybrid server OCR enabled: lang={settings.hybrid_ocr_lang}")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        url = f"{settings.hybrid_server_url}/health"
        for _ in range(60):
            try:
                resp = httpx.get(url, timeout=2.0)
                if resp.status_code == 200:
                    logger.info("Hybrid server started successfully")
                    return proc
            except Exception:
                pass
            time.sleep(1)
        logger.warning("Hybrid server started but health check not responding")
        return proc
    except Exception as e:
        logger.warning(f"Could not start hybrid server: {e}")
        return None


def wait_for_hybrid_server() -> bool:
    """Wait for external hybrid server to be available (docker mode)."""
    url = f"{settings.hybrid_server_url}/health"
    logger.info(f"Waiting for hybrid server at {url}...")
    for _ in range(60):
        try:
            resp = httpx.get(url, timeout=2.0)
            if resp.status_code == 200:
                logger.info("Hybrid server is available")
                return True
        except Exception:
            pass
        time.sleep(1)
    logger.warning("Hybrid server not available, proceeding without hybrid support")
    return False


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

    # Startup: hybrid server
    if settings.run_mode == "local":
        hybrid_process = start_hybrid_server()
    else:
        wait_for_hybrid_server()

    yield

    # Shutdown
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
    # hybrid 상태 확인
    if settings.run_mode == "local":
        hybrid_status = "running" if hybrid_process and hybrid_process.poll() is None else "stopped"
    else:
        try:
            resp = httpx.get(f"{settings.hybrid_server_url}/health", timeout=2.0)
            hybrid_status = "running" if resp.status_code == 200 else "error"
        except Exception:
            hybrid_status = "unavailable"

    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected", "hybrid_server": hybrid_status}
    except Exception as e:
        return {"status": "degraded", "database": f"error: {str(e)}", "hybrid_server": hybrid_status}
