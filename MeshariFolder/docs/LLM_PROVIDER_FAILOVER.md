# Multi-Provider LLM Failover

## Overview

The backend now supports multiple LLM providers instead of being hard-wired to Anthropic. Each developer configures their own **priority-ordered list** of providers in `backend/.env`. At runtime, the app tries each provider in order and automatically falls over to the next one if a provider is unavailable (missing/invalid key, no credit, rate-limited, or unreachable).

This makes the platform provider-agnostic and easy to extend with new providers in the future.

## Supported Providers

- Anthropic
- OpenAI
- DeepSeek
- Qwen (OpenAI-compatible API)

## Configuration

Set your own priority order in `backend/.env`:

```env
LLM_PROVIDER_PRIORITY=anthropic,openai,deepseek,qwen

ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
DEEPSEEK_API_KEY=...
QWEN_API_KEY=...
```

- List 2-4 providers, in the order you want them tried.
- Only providers with a non-empty API key are used; the rest are skipped automatically.
- Each teammate can use a different set/order depending on which keys they have (e.g. Qwen first, DeepSeek second).

## How Failover Works

1. The app resolves your configured provider chain from `LLM_PROVIDER_PRIORITY`, keeping only providers that have a key set.
2. It calls the first provider in the chain.
3. If that call fails with an availability-related error (auth error, rate limit, no credit, connection error), it automatically retries with the next provider in the chain.
4. If all configured providers fail, the API returns a clear `503` error instead of crashing.
5. If no provider has a key configured at all, the API returns a `503` explaining that `LLM_PROVIDER_PRIORITY` / API keys need to be set.

## Files Changed

| File | Change |
|---|---|
| `backend/app/config.py` | Added per-provider settings (keys, models, base URLs) and `LLM_PROVIDER_PRIORITY`. |
| `backend/.env.example` | Added example values for all providers and the priority variable. |
| `backend/requirements.txt` | Added `openai` and `langchain-openai`. |
| `backend/app/agents/llm_client.py` | Core provider abstraction: resolves the provider chain and runs the failover loop for both tool calls and agentic replies. |
| `backend/app/agents/manager.py` | Updated to use the normalized reply shape from `llm_client`. |
| `backend/app/agents/co_reviewers.py` | Updated to use the normalized reply shape. |
| `backend/app/agents/roundtable.py` | Updated to use the normalized reply shape. |
| `backend/app/agents/meeting.py` | Migrated off the removed single-client function to the new failover client. |
| `backend/app/agents/graph/models.py` | LangGraph models now built as a provider chain instead of a single model. |
| `backend/app/agents/graph/onboarding_graph.py` | Tool schemas and forced tool-calling updated to work across providers with failover. |
| `backend/app/main.py` | Added a clean `503` error handler for "all providers failed" / missing configuration. |

## Notes

- No code changes are required to add a new provider's *model choice* - just add its key and put it in `LLM_PROVIDER_PRIORITY`.
- Adding a brand-new provider (beyond the four above) requires adding its settings in `config.py` and its client setup in `llm_client.py`.