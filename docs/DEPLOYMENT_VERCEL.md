## Vercel Deployment

This project deploys the FastAPI backend as a Vercel serverless function and the Vite UI as a static build.

### Build Setup

- Backend entrypoint: `api/index.py`
- Frontend root: `ui/`
- Config: `vercel.json`

### Required Environment Variables

Set these in Vercel Project Settings:

- `LITELLM_MODEL` (example: `gpt-4o-mini`)
- `EMBEDDING_MODEL` (example: `text-embedding-3-small`)
- `OPENAI_API_KEY` (only if using OpenAI models)

Optional if you use integrations:

- `LINEAR_API_KEY`
- `LINEAR_WEBHOOK_SECRET`
- `GITHUB_TOKEN`
- `NOTION_TOKEN`

### Optional Environment Variables

- `CORS_ORIGINS` (comma-separated, example: `https://your-app.vercel.app`)
- `VECTOR_STORE_PATH` (defaults to `/tmp/lancedb` on Vercel)

### Notes

- Vercel provides the `VERCEL` env var automatically.
- The vector database is stored on ephemeral storage; it resets between deploys.
- The UI calls the API using a relative base URL in production.
