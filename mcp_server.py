"""MCP server for remote codebase and log access via FastMCP + SSE."""

from __future__ import annotations

import json
import os
from collections import deque
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError

ROOT = Path("/root/COS_Deploy")
ENV_FILE = ROOT / ".env"
LOG_DIR = ROOT / "logs"
STDOUT_LOG = LOG_DIR / "cos-agent.out.log"
STDERR_LOG = LOG_DIR / "cos-agent.err.log"
HOST_NAME = "cos-droplet"

EXCLUDED_DIRS = {"venv", ".git", "__pycache__"}


def _read_env_value(key: str) -> str | None:
    value = os.environ.get(key)
    if value:
        return value

    if not ENV_FILE.is_file():
        return None

    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        name, _, raw_value = stripped.partition("=")
        if name.strip() != key:
            continue
        return raw_value.strip().strip('"').strip("'")
    return None


MCP_API_KEY = _read_env_value("MCP_API_KEY")

mcp = FastMCP(
    "COS Deploy",
    host="0.0.0.0",
    port=8765,
    sse_path="/sse",
    message_path="/messages/",
    transport_security=None,
)


def _require_api_key(ctx: Context) -> None:
    request = ctx.request_context.request
    if request is None:
        raise ToolError("Missing request context")

    provided_key = request.headers.get("X-API-Key")
    if not MCP_API_KEY or provided_key != MCP_API_KEY:
        raise ToolError("Invalid or missing API key")


def _should_skip_dir(name: str) -> bool:
    return name in EXCLUDED_DIRS


def _build_tree(directory: Path, relative_to: Path) -> dict:
    children: list[dict] = []

    try:
        entries = sorted(directory.iterdir(), key=lambda path: (path.is_file(), path.name.lower()))
    except OSError:
        return {"name": directory.name, "type": "directory", "children": []}

    for entry in entries:
        if entry.is_dir():
            if _should_skip_dir(entry.name):
                continue
            children.append(_build_tree(entry, relative_to))
            continue

        if entry.suffix == ".pyc":
            continue

        rel_path = entry.relative_to(relative_to).as_posix()
        children.append({"name": entry.name, "type": "file", "path": rel_path})

    return {"name": directory.name, "type": "directory", "children": children}


def _validate_relative_path(path: str) -> Path:
    if path.startswith("/"):
        raise ToolError("Path must be relative")
    if ".." in path.split("/"):
        raise ToolError("Path traversal is not allowed")

    candidate = (ROOT / path).resolve()
    root_resolved = ROOT.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ToolError("Path traversal is not allowed") from exc

    return candidate


def _tail_lines(path: Path, lines: int) -> list[str]:
    if not path.is_file():
        return []

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return list(deque(handle, maxlen=lines))


@mcp.tool()
def read_file(path: str, ctx: Context) -> str:
    """Read a file relative to the COS_Deploy root."""
    _require_api_key(ctx)

    file_path = _validate_relative_path(path)
    if not file_path.is_file():
        raise ToolError("File not found")

    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ToolError("File is not valid UTF-8 text") from exc


@mcp.tool()
def list_files(ctx: Context) -> str:
    """List the recursive file tree of COS_Deploy."""
    _require_api_key(ctx)

    tree = _build_tree(ROOT, ROOT)
    return json.dumps({"root": ROOT.as_posix(), "tree": tree}, indent=2)


@mcp.tool()
def read_logs(ctx: Context, lines: int = 100) -> str:
    """Read the last N lines from cos-agent stdout and stderr logs."""
    _require_api_key(ctx)

    if lines < 1 or lines > 10_000:
        raise ToolError("lines must be between 1 and 10000")

    combined: list[str] = []
    for label, log_path in (("stdout", STDOUT_LOG), ("stderr", STDERR_LOG)):
        combined.append(f"=== {label}: {log_path.as_posix()} ===")
        tail = _tail_lines(log_path, lines)
        if tail:
            combined.extend(line.rstrip("\n") for line in tail)
        else:
            combined.append("(empty or missing)")
        combined.append("")

    return "\n".join(combined).rstrip()


app = FastAPI(title="COS Deploy MCP Server")


@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)

    if request.url.path == "/sse" or request.url.path.startswith("/messages"):
        provided_key = request.headers.get("X-API-Key")
        if not MCP_API_KEY or provided_key != MCP_API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

    return await call_next(request)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "host": HOST_NAME}


app.mount("/", mcp.sse_app())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8765)
