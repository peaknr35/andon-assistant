# Provider & Model Matrix

Verified 2026-10-05. All model IDs are overridable by the client; these are the
defaults used when `model` is omitted. The frontend catalog mirrors this file
(`frontend/lib/models.ts`) and the backend defaults live in `backend/app/config.py`.

| provider | SDK | base_url | default model | other offered models |
|---|---|---|---|---|
| `openai` | `openai` | (SDK default) | `gpt-5.1` | `gpt-5.1-mini`, `gpt-5` |
| `anthropic` | `anthropic` | (SDK default) | `claude-opus-5-5` | `claude-opus-5`, `claude-opus-4-8`, `claude-opus-4-7`, `claude-sonnet-5-5`, `claude-sonnet-5`, `claude-haiku-5-5`, `claude-haiku-4-5`, `claude-fable-5-1` |
| `kimi` | `openai` | `https://api.moonshot.ai/v1` | `kimi-k2-0905-preview` | `kimi-k2-turbo-preview`, `kimi-k2-thinking` |

## Why `openai` SDK for Kimi
Moonshot's Kimi K2 exposes an OpenAI-compatible Chat Completions API. We reuse the
`openai` SDK and only change `base_url`. One code path (`OpenAICompatibleClient`)
serves both `openai` and `kimi`.

## Anthropic notes (important for multi-model safety)
Because the user may pick ANY Anthropic model, the Anthropic client does NOT send
`thinking` or `output_config` params -- some models (e.g. Haiku 4.5) reject the
`effort`/adaptive settings that others require. Omitting them lets each model use
its own defaults and keeps one code path valid across all of them. Uses
`messages.stream()` and reads `text_stream`.

## Key formats (informational only; we do not hard-validate provider prefixes)
- OpenAI: `sk-...`
- Anthropic: `sk-ant-...`
- Kimi/Moonshot: `sk-...`

## Getting keys
- OpenAI: https://platform.openai.com/api-keys
- Anthropic: https://console.anthropic.com/settings/keys
- Kimi/Moonshot: https://platform.moonshot.ai (console -> API keys)
