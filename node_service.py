"""Local maintenance API for Rebecca-node.

Provides minimal endpoints to trigger update/restart using the existing
`rebecca-node` CLI. Intended to be installed as a systemd service and
bound to localhost only.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("rebecca.node.service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class Settings:
    def __init__(self) -> None:
        self.host = os.getenv("REBECCA_NODE_SCRIPT_HOST", "127.0.0.1")
        self.port = int(os.getenv("REBECCA_NODE_SCRIPT_PORT", "3100"))
        allowed = os.getenv("REBECCA_NODE_SCRIPT_ALLOWED_HOSTS", "127.0.0.1,::1,localhost")
        self.allowed_hosts = {value.strip() for value in allowed.split(",") if value.strip()}

        cli_path = os.getenv("REBECCA_NODE_SCRIPT_BIN")
        if cli_path:
            candidates: Iterable[Path] = [Path(cli_path)]
        else:
            resolved = shutil.which("rebecca-node")
            fallback = Path("/usr/local/bin/rebecca-node")
            candidates = [Path(resolved)] if resolved else []
            candidates.append(fallback)

        self.node_cli = self._resolve_existing(candidates)

    @staticmethod
    def _resolve_existing(candidates: Iterable[Path]) -> Path:
        for candidate in candidates:
            if candidate and candidate.exists():
                return candidate
        raise RuntimeError("Unable to locate rebecca-node CLI. Set REBECCA_NODE_SCRIPT_BIN.")


settings = Settings()
app = FastAPI(title="Rebecca-node Maintenance API", version="0.1.0")


def run_subprocess(cmd: List[str]) -> subprocess.CompletedProcess[bytes]:
    logger.info("Executing command: %s", " ".join(cmd))
    completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command {' '.join(cmd)} failed with exit code {completed.returncode}",
            completed.stdout.decode(errors="ignore"),
            completed.stderr.decode(errors="ignore"),
        )
    return completed


async def run_cli(*args: str) -> JSONResponse:
    def _runner():
        try:
            result = run_subprocess([str(settings.node_cli), *args])
            return {
                "status": "ok",
                "stdout": result.stdout.decode(errors="ignore"),
                "stderr": result.stderr.decode(errors="ignore"),
            }
        except RuntimeError as exc:
            message = exc.args[0]
            stdout = exc.args[1] if len(exc.args) > 1 else ""
            stderr = exc.args[2] if len(exc.args) > 2 else ""
            raise HTTPException(
                status_code=500,
                detail={"message": message, "stdout": stdout, "stderr": stderr},
            ) from exc

    payload = await asyncio.to_thread(_runner)
    return JSONResponse({"status": payload["status"], "stdout": payload["stdout"].strip()})


@app.middleware("http")
async def local_only(request: Request, call_next):
    host = request.client.host if request.client else None
    if host not in settings.allowed_hosts:
        return JSONResponse(status_code=403, content={"detail": "Only local requests are allowed"})
    return await call_next(request)


@app.get("/health")
async def health():
    return {"status": "ok", "cli": str(settings.node_cli)}


@app.post("/update")
async def update_node():
    return await run_cli("update")


@app.post("/restart")
async def restart_node():
    return await run_cli("restart", "-n")


def main():
    uvicorn.run(app, host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
