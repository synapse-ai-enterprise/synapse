## Vercel Deployment

This project deploys the FastAPI backend as a Vercel serverless function and the Vite UI as a static build.

### How to fix “Is Backend Running?” or config not loading on Vercel

1. **Set environment variables**  
   In Vercel: **Project → Settings → Environment Variables**. Add at least:
   - `OPENAI_API_KEY` (required for default embedding model on Vercel)
   - `LITELLM_MODEL` (e.g. `gpt-4o-mini`)
   - `EMBEDDING_MODEL` (e.g. `text-embedding-3-small`)

   Apply to **Production** (and Preview if you use it). Save.

2. **Do not point the UI at localhost in production**  
   Leave **`VITE_API_BASE_URL`** unset for the Production/Preview environment. The built UI will then call `/api/...` on the same domain (your Vercel URL). If you set `VITE_API_BASE_URL` to `http://localhost:8000`, the browser would try to call your machine and fail.

3. **Redeploy**  
   After changing env vars: **Deployments → … on latest deployment → Redeploy** (or push a new commit). Env vars are applied at build/run time.

4. **If it still fails, check the serverless function**  
   **Project → Logs** (or **Deployments → [deployment] → Functions**). Look for errors when opening Admin Console or loading Models & Agents. Common issues:
   - 500 from `/api/config/models`: missing env (e.g. `OPENAI_API_KEY`) or import/startup error.
   - Function timeout: increase **Project → Settings → Functions → Max Duration** (e.g. 30s) for the API route if cold start is slow.

### Build Setup

- Backend entrypoint: `api/index.py`
- Frontend root: `ui/`
- Config: `vercel.json`

### Why "Config" or "Models" Don’t Load on Vercel

- **Models & Agents stuck on "Loading available models..."**  
  The UI calls `/api/config/models`. If that request fails (e.g. serverless error or missing env), the list never loads. Ensure at least one LLM provider is configured (e.g. `OPENAI_API_KEY` for OpenAI models). Without any API keys, the endpoint can still return data, but cold starts or errors will leave the UI in a loading state.

- **Integrations show "Not connected"**  
  Connection status is driven by environment variables. Set the relevant keys in Vercel (e.g. `JIRA_*`, `CONFLUENCE_*`) so the app can connect and test integrations.

- **Templates empty**  
  Templates are stored in the app’s data layer (e.g. LanceDB/file). On Vercel, the vector store is ephemeral and resets on deploy, so uploaded templates don’t persist unless you use a persistent store.

### Required Environment Variables

Set these in Vercel Project Settings (Dashboard → Project → Settings → Environment Variables):

- `LITELLM_MODEL` (example: `gpt-4o-mini`)
- `EMBEDDING_MODEL` (example: `text-embedding-3-small`)
- `OPENAI_API_KEY` (required for OpenAI models; at least one LLM key is needed for Models & Agents to load)

Optional if you use integrations:

- `LINEAR_API_KEY`
- `LINEAR_WEBHOOK_SECRET`
- `GITHUB_TOKEN`
- `NOTION_TOKEN`
- **Jira:** `JIRA_BASE_URL`, `JIRA_USER_EMAIL`, `JIRA_TOKEN`, `JIRA_PROJECT_KEYS` (comma-separated)
- **Confluence:** `CONFLUENCE_BASE_URL`, `CONFLUENCE_USER_EMAIL`, `CONFLUENCE_TOKEN`, `CONFLUENCE_SPACE_KEYS` (comma-separated)

### Optional Environment Variables

- `CORS_ORIGINS` (comma-separated, example: `https://your-app.vercel.app`)
- `VECTOR_STORE_PATH` (defaults to `/tmp/lancedb` on Vercel)

### Notes

- Vercel provides the `VERCEL` env var automatically.
- The vector database is stored on ephemeral storage; it resets between deploys.
- The UI calls the API using a relative base URL in production.
