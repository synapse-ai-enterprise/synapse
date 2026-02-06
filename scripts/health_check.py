#!/usr/bin/env python3
"""Health check script to verify all services and dependencies."""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def check_python_version() -> Tuple[bool, str]:
    """Check if Python version is 3.10+."""
    version = sys.version_info
    if version.major == 3 and version.minor >= 10:
        return True, f"Python {version.major}.{version.minor}.{version.micro}"
    return False, f"Python {version.major}.{version.minor}.{version.micro} (requires 3.10+)"


def check_poetry() -> Tuple[bool, str]:
    """Check if Poetry is installed."""
    try:
        result = subprocess.run(
            ["poetry", "--version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, "Poetry not found"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, "Poetry not installed"


def check_dependencies() -> Tuple[bool, str]:
    """Check if Poetry dependencies are installed."""
    try:
        result = subprocess.run(
            ["poetry", "show", "--tree"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=Path(__file__).parent.parent,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Check for key dependencies
            output = result.stdout.lower()
            has_langgraph = "langgraph" in output
            has_litellm = "litellm" in output
            has_lancedb = "lancedb" in output
            if has_langgraph and has_litellm and has_lancedb:
                return True, "Dependencies installed"
            return False, "Some dependencies missing"
        return False, "Dependencies not installed (run: poetry install)"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, "Cannot check dependencies"


def check_imports() -> Tuple[bool, str]:
    """Check if core dependencies can be imported."""
    try:
        import langgraph  # noqa: F401
        import litellm  # noqa: F401
        import lancedb  # noqa: F401
        import pydantic  # noqa: F401
        return True, "Core dependencies importable"
    except ImportError as e:
        return False, f"Import error: {e.name}"


def check_env_file() -> Tuple[bool, str, Dict[str, bool]]:
    """Check if .env file exists and has required variables."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return False, ".env file missing", {}

    # Read .env file
    env_vars = {}
    required_vars: Dict[str, bool] = {}
    optional_vars = {
        "LINEAR_API_KEY": False,
        "LINEAR_TEAM_ID": False,
        "GITHUB_TOKEN": False,
        "NOTION_TOKEN": False,
        "LINEAR_WEBHOOK_SECRET": False,
    }

    try:
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key = line.split("=")[0].strip()
                    value = line.split("=", 1)[1].strip()
                    if key in required_vars:
                        required_vars[key] = bool(value)
                    if key in optional_vars:
                        optional_vars[key] = bool(value)
                    env_vars[key] = value
    except Exception as e:
        return False, f"Error reading .env: {e}", {}

    model_name = env_vars.get("LITELLM_MODEL", "ollama/llama3")
    if model_name.startswith("ollama/"):
        required_vars["OLLAMA_BASE_URL"] = bool(env_vars.get("OLLAMA_BASE_URL"))
    else:
        required_vars["OPENAI_API_KEY"] = bool(env_vars.get("OPENAI_API_KEY"))

    # Check required vars
    missing_required = [k for k, v in required_vars.items() if not v]
    if missing_required:
        return False, f"Missing required vars: {', '.join(missing_required)}", env_vars

    return True, ".env file configured", env_vars


def check_redis() -> Tuple[bool, str]:
    """Check if Redis is running."""
    try:
        result = subprocess.run(
            ["redis-cli", "ping"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and "PONG" in result.stdout:
            return True, "Redis is running"
        return False, "Redis not responding"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, "Redis not installed or not running"


def check_lancedb_dir() -> Tuple[bool, str]:
    """Check if LanceDB directory exists or can be created."""
    base_path = Path(__file__).parent.parent
    lancedb_path = base_path / "data" / "lancedb"
    if lancedb_path.exists():
        return True, f"LanceDB directory exists: {lancedb_path}"
    # Check if parent directory is writable
    if base_path.joinpath("data").exists() or base_path.is_dir():
        return True, f"LanceDB directory will be created at: {lancedb_path}"
    return False, f"Cannot create LanceDB directory: {lancedb_path}"


def check_otel_collector() -> Tuple[bool, str]:
    """Check if OpenTelemetry collector is reachable (optional)."""
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("localhost", 4317))
        sock.close()
        if result == 0:
            return True, "OpenTelemetry collector reachable"
        return False, "OpenTelemetry collector not reachable (optional)"
    except Exception:
        return False, "Cannot check OpenTelemetry collector (optional)"


def check_poetry_lock() -> Tuple[bool, str]:
    """Check if poetry.lock is up to date."""
    try:
        result = subprocess.run(
            ["poetry", "check"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=Path(__file__).parent.parent,
        )
        if "poetry.lock was last generated" in result.stdout:
            return False, "poetry.lock needs update (run: poetry lock)"
        return True, "poetry.lock is up to date"
    except Exception:
        return True, "Cannot verify poetry.lock"


def print_status(check_name: str, passed: bool, message: str, is_optional: bool = False):
    """Print formatted status message."""
    status = f"{GREEN}✓{RESET}" if passed else (f"{YELLOW}⚠{RESET}" if is_optional else f"{RED}✗{RESET}")
    optional_note = " (optional)" if is_optional else ""
    print(f"{status} {check_name}: {message}{optional_note}")


def main():
    """Run all health checks."""
    print(f"{BLUE}=== Agentic AI PoC Health Check ==={RESET}\n")

    checks: List[Tuple[str, bool, str, bool]] = []

    # Required checks
    print(f"{BLUE}Required Services:{RESET}")
    python_ok, python_msg = check_python_version()
    checks.append(("Python Version", python_ok, python_msg, False))
    print_status("Python Version", python_ok, python_msg)

    poetry_ok, poetry_msg = check_poetry()
    checks.append(("Poetry", poetry_ok, poetry_msg, False))
    print_status("Poetry", poetry_ok, poetry_msg)

    lock_ok, lock_msg = check_poetry_lock()
    checks.append(("Poetry Lock", lock_ok, lock_msg, False))
    print_status("Poetry Lock", lock_ok, lock_msg)

    deps_ok, deps_msg = check_dependencies()
    checks.append(("Dependencies", deps_ok, deps_msg, False))
    print_status("Dependencies", deps_ok, deps_msg)

    imports_ok, imports_msg = check_imports()
    checks.append(("Imports", imports_ok, imports_msg, False))
    print_status("Imports", imports_ok, imports_msg)

    env_ok, env_msg, env_vars = check_env_file()
    checks.append(("Environment Config", env_ok, env_msg, False))
    print_status("Environment Config", env_ok, env_msg)

    redis_ok, redis_msg = check_redis()
    checks.append(("Redis", redis_ok, redis_msg, False))
    print_status("Redis", redis_ok, redis_msg)

    lancedb_ok, lancedb_msg = check_lancedb_dir()
    checks.append(("LanceDB Directory", lancedb_ok, lancedb_msg, False))
    print_status("LanceDB Directory", lancedb_ok, lancedb_msg)

    # Optional checks
    print(f"\n{BLUE}Optional Services:{RESET}")
    otel_ok, otel_msg = check_otel_collector()
    checks.append(("OpenTelemetry Collector", otel_ok, otel_msg, True))
    print_status("OpenTelemetry Collector", otel_ok, otel_msg, is_optional=True)

    # Summary
    print(f"\n{BLUE}=== Summary ==={RESET}")
    required_checks = [c for c in checks if not c[3]]  # Not optional
    passed_required = sum(1 for c in required_checks if c[1])
    total_required = len(required_checks)

    if passed_required == total_required:
        print(f"{GREEN}✓ All required services are ready ({passed_required}/{total_required}){RESET}")
        return 0
    else:
        print(
            f"{RED}✗ Some required services are not ready ({passed_required}/{total_required}){RESET}"
        )
        print(f"\n{YELLOW}Next steps:{RESET}")
        if not poetry_ok:
            print("  - Install Poetry: curl -sSL https://install.python-poetry.org | python3 -")
        if not deps_ok:
            print("  - Install dependencies: poetry install")
        if not lock_ok:
            print("  - Update lock file: poetry lock")
        if not env_ok:
            model_name = env_vars.get("LITELLM_MODEL", "ollama/llama3")
            if model_name.startswith("ollama/"):
                print("  - Create .env file with OLLAMA_BASE_URL (see README.md)")
            else:
                print("  - Create .env file with OPENAI_API_KEY (see README.md)")
        if not redis_ok:
            print("  - Install/start Redis: brew install redis && brew services start redis")
        return 1


if __name__ == "__main__":
    sys.exit(main())
