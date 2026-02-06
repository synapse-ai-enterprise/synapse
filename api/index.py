"""Vercel serverless entrypoint for FastAPI."""

from src.main import app as fastapi_app

app = fastapi_app
