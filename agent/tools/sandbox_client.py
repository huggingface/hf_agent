#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["huggingface_hub>=0.20.0", "httpx>=0.27.0"]
# ///
"""
Sandbox Tools — Agent-native primitives for HF Space dev-mode sandboxes.

Architecture:
  - Creates a sandbox by duplicating a template Space (runs sandbox_server.py)
  - Waits for it to come online
  - Communicates via HTTPS to the Space's API
  - Optionally deletes the Space when done

Lifecycle:
    sb = Sandbox.create(owner="burtenshaw")         # duplicate, wait, connect
    sb = Sandbox.create(owner="burtenshaw",          # with options
                        hardware="t4-small",
                        private=True,
                        sleep_time=3600)
    sb = Sandbox.connect("burtenshaw/my-sandbox-abc") # attach to existing

    sb.bash("uv run train.py")
    sb.read("/app/train.py")
    sb.edit("/app/train.py", old_str="lr=1e-3", new_str="lr=1e-4")

    sb.delete()                                       # tear down when done

    # Or use as a context manager for automatic cleanup
    with Sandbox.create(owner="burtenshaw") as sb:
        sb.bash("python train.py")
    # Space deleted on exit

Tools: bash, read, write, edit, glob, grep, upload
"""

from __future__ import annotations

import io
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from huggingface_hub import CommitOperationAdd, HfApi

TEMPLATE_SPACE = "burtenshaw/sandbox"
HARDWARE_OPTIONS = [
    "cpu-basic",
    "cpu-upgrade",
    "t4-small",
    "t4-medium",
    "a10g-small",
    "a10g-large",
    "a100-large",
]
OUTPUT_LIMIT = 30000
LINE_LIMIT = 2000
DEFAULT_READ_LIMIT = 2000
DEFAULT_TIMEOUT = 120
MAX_TIMEOUT = 600
WAIT_TIMEOUT = 300
WAIT_INTERVAL = 5
API_WAIT_TIMEOUT = 180

_DOCKERFILE = """\
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update && \\
    apt-get install -y \\
      bash git git-lfs wget curl procps \\
      htop vim nano jq tmux \\
      build-essential grep && \\
    rm -rf /var/lib/apt/lists/*

# Install server dependencies (as root, before USER switch)
RUN uv pip install --system fastapi uvicorn python-multipart

RUN useradd -m -u 1000 user
USER user

ENV HOME=/home/user \\
    PATH=/home/user/.local/bin:$PATH

WORKDIR /app
COPY --chown=user . /app

EXPOSE 7860

CMD ["python", "sandbox_server.py"]
"""


@dataclass
class ToolResult:
    success: bool
    output: str = ""
    error: str = ""

    def __str__(self):
        if self.success:
            return self.output or "(no output)"
        return f"ERROR: {self.error}"

    def to_dict(self) -> dict:
        return {"success": self.success, "output": self.output, "error": self.error}


@dataclass
class Sandbox:
    """
    A handle to an HF Space sandbox.

    Use Sandbox.create() to spin up a new one, or Sandbox.connect() to
    attach to an existing running Space.
    """

    space_id: str
    token: str | None = None
    work_dir: str = "/app"
    timeout: int = DEFAULT_TIMEOUT
    _owns_space: bool = field(default=False, repr=False)
    _base_url: str = field(init=False, repr=False)
    _client: httpx.Client = field(init=False, repr=False)
    _hf_api: HfApi = field(init=False, repr=False)
    _files_read: set = field(init=False, repr=False, default_factory=set)

    def __post_init__(self):
        self.token = self.token or os.environ.get("HF_TOKEN")
        slug = self.space_id.replace("/", "-")
        # Trailing slash is critical: httpx resolves relative paths against base_url.
        # Without it, client.get("health") resolves to /health instead of /api/health.
        self._base_url = f"https://{slug}.hf.space/api/"
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {self.token}"} if self.token else {},
            timeout=httpx.Timeout(MAX_TIMEOUT, connect=30),
            follow_redirects=True,
        )
        self._hf_api = HfApi(token=self.token)

    # ── Lifecycle ─────────────────────────────────────────────────

    @classmethod
    def create(
        cls,
        owner: str,
        *,
        name: str | None = None,
        template: str = TEMPLATE_SPACE,
        hardware: str = "cpu-basic",
        private: bool = False,
        sleep_time: int | None = None,
        token: str | None = None,
        wait_timeout: int = WAIT_TIMEOUT,
    ) -> Sandbox:
        """
        Create a new sandbox by duplicating the template Space.

        Generates a unique space name, duplicates the template, waits for it
        to come online, then returns a connected Sandbox.

        Args:
            owner: HF username or org (e.g. "burtenshaw").
            name: Base name for the space. Defaults to "sandbox".
                  A unique suffix is always appended.
            template: Source Space to duplicate (default: burtenshaw/sandbox).
            hardware: Hardware tier (cpu-basic, t4-small, etc.).
            private: Whether the Space should be private.
            sleep_time: Auto-sleep after N seconds of inactivity.
            token: HF API token. Falls back to HF_TOKEN env var.
            wait_timeout: Max seconds to wait for Space to start (default: 300).

        Returns:
            A Sandbox instance connected to the running Space.
        """
        token = token or os.environ.get("HF_TOKEN")
        api = HfApi(token=token)

        base = name or "sandbox"
        suffix = uuid.uuid4().hex[:8]
        space_id = f"{owner}/{base}-{suffix}"

        print(f"Creating sandbox: {space_id} (from {template})...")

        kwargs = {
            "from_id": template,
            "to_id": space_id,
            "private": private,
            "hardware": hardware,
        }
        if sleep_time is not None:
            kwargs["sleep_time"] = sleep_time

        api.duplicate_space(**kwargs)
        print(f"Space created: https://huggingface.co/spaces/{space_id}")

        # Upload sandbox server and Dockerfile (triggers rebuild)
        cls._setup_server(space_id, api)

        # Wait for it to come online (rebuild + start)
        print(f"Waiting for Space to start (timeout: {wait_timeout}s)...")
        deadline = time.time() + wait_timeout
        while time.time() < deadline:
            runtime = api.get_space_runtime(space_id)
            if runtime.stage == "RUNNING":
                print(f"Space is running (hardware: {runtime.hardware})")
                break
            if runtime.stage in ("RUNTIME_ERROR", "BUILD_ERROR"):
                raise RuntimeError(
                    f"Space failed to start: {runtime.stage}. "
                    f"Check https://huggingface.co/spaces/{space_id}"
                )
            print(f"  {runtime.stage}...")
            time.sleep(WAIT_INTERVAL)
        else:
            raise TimeoutError(
                f"Space did not start within {wait_timeout}s. "
                f"Check https://huggingface.co/spaces/{space_id}"
            )

        # Wait for the API server to be responsive (non-fatal)
        sb = cls(space_id=space_id, token=token, _owns_space=True)
        try:
            sb._wait_for_api(timeout=API_WAIT_TIMEOUT)
        except TimeoutError as e:
            print(
                f"Warning: API health check timed out ({e}), but Space is RUNNING. Continuing."
            )
        return sb

    @staticmethod
    def _setup_server(space_id: str, api: HfApi) -> None:
        """Upload FastAPI server + Dockerfile to the sandbox Space (single commit)."""
        server_path = Path(__file__).parent / "example_sandbox_server.py"
        server_code = server_path.read_text()

        print(f"Uploading sandbox server to {space_id}...")
        api.create_commit(
            repo_id=space_id,
            repo_type="space",
            operations=[
                CommitOperationAdd(
                    path_in_repo="sandbox_server.py",
                    path_or_fileobj=io.BytesIO(server_code.encode()),
                ),
                CommitOperationAdd(
                    path_in_repo="Dockerfile",
                    path_or_fileobj=io.BytesIO(_DOCKERFILE.encode()),
                ),
            ],
            commit_message="Setup sandbox server",
        )
        print("Server files uploaded, rebuild triggered.")

    @classmethod
    def connect(cls, space_id: str, *, token: str | None = None) -> Sandbox:
        """
        Connect to an existing running Space.

        Does a health check to verify the Space is reachable.
        """
        sb = cls(space_id=space_id, token=token, _owns_space=False)
        sb._wait_for_api(timeout=60)
        return sb

    def _wait_for_api(self, timeout: int = API_WAIT_TIMEOUT):
        """Poll the health endpoint until the server responds."""
        deadline = time.time() + timeout
        last_err = None
        last_status = None
        while time.time() < deadline:
            try:
                resp = self._client.get("health", timeout=10)
                last_status = resp.status_code
                if resp.status_code == 200:
                    print(f"API is responsive at {self._base_url}")
                    return
            except Exception as e:
                last_err = e
            time.sleep(3)
        raise TimeoutError(
            f"Sandbox API at {self._base_url} not responding after {timeout}s. "
            f"Last status: {last_status}, last error: {last_err}"
        )

    def delete(self):
        """Delete the Space. Only works if this Sandbox created it."""
        if not self._owns_space:
            raise RuntimeError(
                f"This Sandbox did not create {self.space_id}. "
                f"Use self._hf_api.delete_repo() directly if you're sure."
            )
        print(f"Deleting sandbox: {self.space_id}...")
        self._hf_api.delete_repo(self.space_id, repo_type="space")
        self._client.close()
        print("Deleted.")

    def pause(self):
        """Pause the Space (stops billing, preserves state)."""
        self._hf_api.pause_space(self.space_id)

    def restart(self):
        """Restart the Space."""
        self._hf_api.restart_space(self.space_id)
        self._wait_for_api()

    @property
    def url(self) -> str:
        """Public URL of the Space."""
        return f"https://huggingface.co/spaces/{self.space_id}"

    @property
    def status(self) -> str:
        """Current Space stage (RUNNING, BUILDING, PAUSED, etc.)."""
        return self._hf_api.get_space_runtime(self.space_id).stage

    def __enter__(self) -> Sandbox:
        return self

    def __exit__(self, *exc):
        if self._owns_space:
            try:
                self.delete()
            except Exception as e:
                print(f"Warning: failed to delete sandbox: {e}", file=sys.stderr)
        self._client.close()

    # ── HTTP plumbing ─────────────────────────────────────────────

    def _call(
        self, endpoint: str, payload: dict, timeout: float | None = None
    ) -> ToolResult:
        # Strip leading slash for correct httpx base_url resolution
        endpoint = endpoint.lstrip("/")
        try:
            resp = self._client.post(
                endpoint,
                json=payload,
                timeout=timeout or self.timeout,
            )
            data = resp.json()
            if resp.status_code == 200:
                return ToolResult(
                    success=data.get("success", True),
                    output=data.get("output", ""),
                    error=data.get("error", ""),
                )
            return ToolResult(
                success=False,
                error=data.get("error", f"HTTP {resp.status_code}"),
            )
        except httpx.TimeoutException:
            return ToolResult(
                success=False, error=f"Timeout after {timeout or self.timeout}s"
            )
        except httpx.ConnectError:
            return ToolResult(
                success=False,
                error=f"Cannot connect to sandbox. Is {self.space_id} running? Status: {self.status}",
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    # ── Tools ─────────────────────────────────────────────────────

    def bash(
        self,
        command: str,
        *,
        work_dir: str | None = None,
        timeout: int | None = None,
        description: str | None = None,
    ) -> ToolResult:
        return self._call(
            "bash",
            {
                "command": command,
                "work_dir": work_dir or self.work_dir,
                "timeout": min(timeout or self.timeout, MAX_TIMEOUT),
            },
            timeout=timeout,
        )

    def read(
        self, path: str, *, offset: int | None = None, limit: int | None = None
    ) -> ToolResult:
        self._files_read.add(path)
        return self._call(
            "read",
            {
                "path": path,
                "offset": offset,
                "limit": limit or (DEFAULT_READ_LIMIT if offset is None else None),
            },
        )

    def write(self, path: str, content: str) -> ToolResult:
        if path not in self._files_read:
            check = self._call("exists", {"path": path})
            if check.success and check.output == "true":
                return ToolResult(
                    success=False,
                    error=(
                        f"File {path} exists but has not been read this session. "
                        f"Read it first, or use sandbox_edit for targeted changes."
                    ),
                )
        result = self._call("write", {"path": path, "content": content})
        if result.success:
            self._files_read.add(path)
        return result

    def edit(
        self, path: str, old_str: str, new_str: str, *, replace_all: bool = False
    ) -> ToolResult:
        if old_str == new_str:
            return ToolResult(success=False, error="old_str and new_str are identical.")
        if path not in self._files_read:
            return ToolResult(
                success=False,
                error=f"File {path} has not been read this session. Read it first.",
            )
        return self._call(
            "edit",
            {
                "path": path,
                "old_str": old_str,
                "new_str": new_str,
                "replace_all": replace_all,
            },
        )

    def glob(self, pattern: str, *, path: str | None = None) -> ToolResult:
        return self._call(
            "glob",
            {
                "pattern": pattern,
                "path": path or self.work_dir,
            },
        )

    def grep(
        self,
        pattern: str,
        *,
        path: str | None = None,
        include: str | None = None,
        output_mode: str = "files_with_matches",
        case_insensitive: bool = False,
        n: bool = False,
        A: int | None = None,
        B: int | None = None,
        C: int | None = None,
        head_limit: int | None = None,
    ) -> ToolResult:
        return self._call(
            "grep",
            {
                "pattern": pattern,
                "path": path or self.work_dir,
                "include": include,
                "output_mode": output_mode,
                "case_insensitive": case_insensitive,
                "n": n,
                "A": A,
                "B": B,
                "C": C,
                "head_limit": head_limit,
            },
        )

    # ── Tool schemas & dispatch ───────────────────────────────────

    TOOLS = {
        "bash": {
            "description": (
                "Run a shell command in the remote sandbox and return stdout/stderr.\n"
                "\n"
                "Commands run in a shell at the working directory (default /app). "
                "Each invocation is independent — use files in /app to persist state.\n"
                "\n"
                "AVOID using bash for operations covered by specialized tools:\n"
                "- File reading: use read (not cat/head/tail)\n"
                "- File search: use grep (not grep/rg)\n"
                "- File finding: use glob (not find)\n"
                "- File editing: use edit (not sed/awk)\n"
                "- File writing: use write (not echo/cat <<EOF)\n"
                "\n"
                "For long-running tasks, background them:\n"
                "  nohup uv run train.py > /app/train.log 2>&1 &\n"
                "Then check with read on the log file.\n"
                "\n"
                "Chain dependent commands with &&. Independent commands should be "
                "separate bash calls (they can run in parallel).\n"
                "\n"
                "Timeout default 120s, max 600s."
            ),
            "parameters": {
                "type": "object",
                "required": ["command"],
                "additionalProperties": False,
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Short description (5-10 words, active voice). E.g. 'Install dependencies', 'Run training script'.",
                    },
                    "work_dir": {
                        "type": "string",
                        "description": "Working directory (default: /app).",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default: 120, max: 600).",
                    },
                },
            },
        },
        "read": {
            "description": (
                "Read file contents with line numbers (cat -n format).\n"
                "\n"
                "Returns the first 2000 lines by default. For large files, use offset/limit "
                "to read a specific range. Line numbers always match the original file.\n"
                "\n"
                "Lines longer than 2000 chars are truncated.\n"
                "Cannot read directories — use bash with 'ls' instead."
            ),
            "parameters": {
                "type": "object",
                "required": ["path"],
                "additionalProperties": False,
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file to read.",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Start from this line (1-based). Only if file is too large.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of lines to read. Only if file is too large.",
                    },
                },
            },
        },
        "write": {
            "description": (
                "Create or overwrite a file. Creates parent directories as needed.\n"
                "\n"
                "For existing files, you MUST read the file first (system enforced). "
                "Prefer edit for modifications."
            ),
            "parameters": {
                "type": "object",
                "required": ["path", "content"],
                "additionalProperties": False,
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file to write.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete file content.",
                    },
                },
            },
        },
        "edit": {
            "description": (
                "Targeted edit via exact string replacement.\n"
                "\n"
                "Rules:\n"
                "- old_str must appear EXACTLY once (unless replace_all is true).\n"
                "- Include enough context in old_str for uniqueness.\n"
                "- old_str and new_str must differ.\n"
                "- Preserve indentation exactly.\n"
                "- To delete code, set new_str to empty string.\n"
                "- File MUST have been read this session (system enforced).\n"
                "- Do NOT include line number prefixes in old_str/new_str.\n"
                "\n"
                "Use replace_all=true for batch operations like variable renaming."
            ),
            "parameters": {
                "type": "object",
                "required": ["path", "old_str", "new_str"],
                "additionalProperties": False,
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file.",
                    },
                    "old_str": {
                        "type": "string",
                        "description": "Exact text to find (must differ from new_str).",
                    },
                    "new_str": {"type": "string", "description": "Replacement text."},
                    "replace_all": {
                        "type": "boolean",
                        "description": "Replace all occurrences (default: false).",
                        "default": False,
                    },
                },
            },
        },
        "glob": {
            "description": (
                "Find files by glob pattern, sorted by modification time (newest first).\n"
                "\n"
                "Patterns: * (any), ** (recursive), ? (one char), {a,b}, [abc], [!abc].\n"
                "Examples: '*.py', '*.{json,yaml}', 'test_*'"
            ),
            "parameters": {
                "type": "object",
                "required": ["pattern"],
                "additionalProperties": False,
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to match file names.",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory to search (default: /app). Omit for default.",
                    },
                },
            },
        },
        "grep": {
            "description": (
                "Search file contents. ALWAYS use this — NEVER bash with grep.\n"
                "\n"
                "Output modes:\n"
                "- 'files_with_matches' (default): file paths only\n"
                "- 'content': matching lines (supports -n, -A/-B/-C context)\n"
                "- 'count': match counts per file\n"
                "\n"
                "Supports regex. Use glob for name matching, grep for content."
            ),
            "parameters": {
                "type": "object",
                "required": ["pattern"],
                "additionalProperties": False,
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Search string or regex.",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory to search (default: /app).",
                    },
                    "include": {
                        "type": "string",
                        "description": "Glob filter (e.g. '*.py').",
                    },
                    "output_mode": {
                        "type": "string",
                        "enum": ["content", "files_with_matches", "count"],
                        "description": "Default: 'files_with_matches'.",
                    },
                    "-i": {"type": "boolean", "description": "Case-insensitive."},
                    "-n": {
                        "type": "boolean",
                        "description": "Line numbers (content mode only).",
                    },
                    "-A": {
                        "type": "integer",
                        "description": "Lines after match (content mode only).",
                    },
                    "-B": {
                        "type": "integer",
                        "description": "Lines before match (content mode only).",
                    },
                    "-C": {
                        "type": "integer",
                        "description": "Lines around match (content mode only).",
                    },
                    "head_limit": {
                        "type": "integer",
                        "description": "Limit output entries.",
                    },
                },
            },
        },
    }

    @classmethod
    def tool_definitions(cls) -> list[dict]:
        return [{"name": name, **spec} for name, spec in cls.TOOLS.items()]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        dispatch = {
            "bash": lambda a: self.bash(
                a["command"],
                work_dir=a.get("work_dir"),
                timeout=a.get("timeout"),
                description=a.get("description"),
            ),
            "read": lambda a: self.read(
                a["path"],
                offset=a.get("offset"),
                limit=a.get("limit"),
            ),
            "write": lambda a: self.write(a["path"], a["content"]),
            "edit": lambda a: self.edit(
                a["path"],
                a["old_str"],
                a["new_str"],
                replace_all=a.get("replace_all", False),
            ),
            "glob": lambda a: self.glob(a["pattern"], path=a.get("path")),
            "grep": lambda a: self.grep(
                a["pattern"],
                path=a.get("path"),
                include=a.get("include"),
                output_mode=a.get("output_mode", "files_with_matches"),
                case_insensitive=a.get("-i", False),
                n=a.get("-n", False),
                A=a.get("-A"),
                B=a.get("-B"),
                C=a.get("-C"),
                head_limit=a.get("head_limit"),
            ),
        }
        fn = dispatch.get(name)
        if not fn:
            return ToolResult(success=False, error=f"Unknown tool: {name}")
        return fn(arguments)
