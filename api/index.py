"""Vercel serverless entrypoint for FastAPI."""

import sys
from pathlib import Path

# Ensure project root is on path so "src" can be imported (Vercel runs from /var/task)
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from src.main import app as fastapi_app

app = fastapi_app
