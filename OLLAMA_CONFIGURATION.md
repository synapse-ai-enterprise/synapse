# Ollama Configuration Summary

## Changes Made

The platform has been configured to use a local Ollama server at `127.0.0.1:11434`.

### 1. Configuration Updates

**File: `src/config.py`**
- Updated default `ollama_base_url` to `http://127.0.0.1:11434`

**File: `.env`**
- Updated `LITELLM_MODEL=ollama/llama3`
- Updated `OLLAMA_BASE_URL=http://127.0.0.1:11434`
- `EMBEDDING_MODEL` remains `text-embedding-3-small` (OpenAI) - embeddings still use OpenAI

### 2. LiteLLM Adapter Updates

**File: `src/adapters/llm/litellm_adapter.py`**

#### Changes:
1. **Initialization (`__init__`)**: 
   - Detects Ollama models (models starting with `ollama/`)
   - Sets `litellm.api_base` for Ollama models
   - Skips API key requirement for Ollama

2. **Chat Completion (`chat_completion`)**:
   - Passes `api_base` parameter directly to completion calls for Ollama models

3. **Structured Completion (`structured_completion`)**:
   - Passes `api_base` parameter directly to completion calls for Ollama models
   - Disables JSON mode for Ollama (uses prompt-based JSON extraction instead)

### 3. Model Configuration

- **Current Model**: `ollama/llama3` (uses `llama3:latest` from your Ollama server)
- **Base URL**: `http://127.0.0.1:11434`
- **Embeddings**: Still using OpenAI (`text-embedding-3-small`) - can be changed separately if needed

## Usage

The system will automatically:
1. Detect when using Ollama models (model name starts with `ollama/`)
2. Configure LiteLLM to use the local Ollama server
3. Skip API key requirements for Ollama
4. Use appropriate JSON parsing for Ollama responses

## Testing

To verify the configuration:

```bash
poetry run python -c "
from src.config import settings
from src.adapters.llm.litellm_adapter import LiteLLMAdapter

print(f'Model: {settings.litellm_model}')
print(f'Ollama Base URL: {settings.ollama_base_url}')

adapter = LiteLLMAdapter()
print(f'Adapter Model: {adapter.model}')
print(f'Using Ollama: {adapter.model.startswith(\"ollama/\")}')
"
```

## Switching Models

To use a different Ollama model, update `.env`:

```bash
# For example, to use llama3.2:
LITELLM_MODEL=ollama/llama3.2

# Or llama2:
LITELLM_MODEL=ollama/llama2
```

## Switching Back to OpenAI

To switch back to OpenAI:

```bash
# In .env:
LITELLM_MODEL=gpt-4-turbo-preview
OPENAI_API_KEY=your-key-here
```

## Notes

- **Embeddings**: Currently still using OpenAI. To use local embeddings, you would need to:
  1. Install a local embedding model (e.g., via Ollama or sentence-transformers)
  2. Update `EMBEDDING_MODEL` in `.env`
  3. Update the embedding function in `litellm_adapter.py` if needed

- **Model Availability**: Ensure your Ollama model is available:
  ```bash
  curl http://127.0.0.1:11434/api/tags
  ```

- **Performance**: Local Ollama models may be slower than OpenAI but provide:
  - No API costs
  - Complete privacy
  - No rate limits
  - Offline capability
