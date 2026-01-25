# Switching LLM Providers - Simple Guide

## The Easy Way

**Just change the model name and set the API key environment variable!**

LiteLLM automatically detects the provider from the model name prefix and reads API keys from environment variables.

## Quick Examples

### Switch to OpenAI
```bash
# In .env:
LITELLM_MODEL=gpt-4-turbo-preview
# Or set environment variable:
export OPENAI_API_KEY=your-key-here
```

### Switch to Anthropic (Claude)
```bash
# In .env:
LITELLM_MODEL=claude-3-opus
# Or set environment variable:
export ANTHROPIC_API_KEY=your-key-here
```

### Switch to Google (Gemini)
```bash
# In .env:
LITELLM_MODEL=gemini/gemini-pro
# Or set environment variable:
export GEMINI_API_KEY=your-key-here
```

### Switch to Azure OpenAI
```bash
# In .env:
LITELLM_MODEL=azure/gpt-4
# Set environment variables:
export AZURE_API_KEY=your-key-here
export AZURE_API_BASE=https://your-resource.openai.azure.com
export AZURE_API_VERSION=2024-02-15-preview
```

### Switch to Ollama (Local)
```bash
# In .env:
LITELLM_MODEL=ollama/llama3
OLLAMA_BASE_URL=http://127.0.0.1:11434
# No API key needed for Ollama
```

### Switch to Other Providers

LiteLLM supports 100+ providers! Just:
1. Set `LITELLM_MODEL` to the model name (check LiteLLM docs for format)
2. Set the appropriate API key environment variable
3. That's it!

## Supported Providers (Sample)

| Provider | Model Format | Environment Variable |
|----------|-------------|---------------------|
| OpenAI | `gpt-4`, `gpt-3.5-turbo` | `OPENAI_API_KEY` |
| Anthropic | `claude-3-opus`, `claude-3-sonnet` | `ANTHROPIC_API_KEY` |
| Google | `gemini/gemini-pro` | `GEMINI_API_KEY` |
| Azure | `azure/gpt-4` | `AZURE_API_KEY`, `AZURE_API_BASE` |
| Ollama | `ollama/llama3` | `OLLAMA_BASE_URL` (config) |
| Together AI | `together_ai/meta-llama/Llama-2-70b-chat-hf` | `TOGETHER_AI_API_KEY` |
| Replicate | `replicate/meta/llama-2-70b-chat` | `REPLICATE_API_KEY` |
| HuggingFace | `huggingface/meta-llama/Llama-2-70b-chat-hf` | `HUGGINGFACE_API_KEY` |
| Cohere | `cohere/command` | `COHERE_API_KEY` |
| Bedrock | `bedrock/anthropic.claude-v2` | AWS credentials |

See full list: https://docs.litellm.ai/docs/providers

## How It Works

1. **Model Name Detection**: LiteLLM automatically detects the provider from the model name prefix
   - `gpt-4` → OpenAI
   - `claude-3-opus` → Anthropic
   - `ollama/llama3` → Ollama
   - `azure/gpt-4` → Azure OpenAI
   - etc.

2. **API Key Reading**: LiteLLM automatically reads API keys from environment variables
   - No code changes needed!
   - Just set the appropriate `*_API_KEY` environment variable

3. **Special Cases**: Only Ollama needs a custom `api_base` URL (handled automatically)

## No Code Changes Required!

The adapter automatically:
- Detects provider from model name
- Reads API keys from environment variables
- Handles special cases (like Ollama's base URL)

**You never need to modify code to switch providers!**

## Testing a New Provider

1. Set the model name in `.env`:
   ```bash
   LITELLM_MODEL=claude-3-opus
   ```

2. Set the API key:
   ```bash
   export ANTHROPIC_API_KEY=your-key-here
   ```

3. Run your code - it just works!

## Troubleshooting

**"No API key found"**
- Make sure you set the correct environment variable for your provider
- Check LiteLLM docs for the exact variable name

**"Provider not supported"**
- Check the model name format in LiteLLM docs
- Some providers need specific prefixes (e.g., `azure/`, `ollama/`)

**"Connection error"**
- For Ollama: Check `OLLAMA_BASE_URL` is correct
- For Azure: Check `AZURE_API_BASE` is correct
- For others: Check API key is valid

## Current Configuration

Check your current setup:
```bash
poetry run python -c "from src.config import settings; print(f'Model: {settings.litellm_model}')"
```

## Summary

**To switch providers:**
1. Change `LITELLM_MODEL` in `.env` (or set env var)
2. Set the appropriate `*_API_KEY` environment variable
3. Done! No code changes needed.

That's it! 🎉
