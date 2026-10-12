// Model catalog. Mirrors ../_shared/providers.md and the backend /providers endpoint.
import type { Provider } from "./types";

export interface ProviderInfo {
  id: Provider;
  label: string;
  keyHint: string;
  defaultModel: string;
  models: string[];
  getKeyUrl: string;
}

export const PROVIDERS: ProviderInfo[] = [
  {
    id: "openai",
    label: "OpenAI",
    keyHint: "sk-...",
    defaultModel: "gpt-5.1",
    models: ["gpt-5.1", "gpt-5.1-mini", "gpt-5"],
    getKeyUrl: "https://platform.openai.com/api-keys",
  },
  {
    id: "anthropic",
    label: "Anthropic (Claude)",
    keyHint: "sk-ant-...",
    defaultModel: "claude-opus-5-5",
    models: ["claude-opus-5-5", "claude-opus-5", "claude-opus-4-8", "claude-opus-4-7", "claude-sonnet-5-5", "claude-sonnet-5", "claude-haiku-5-5", "claude-haiku-4-5", "claude-fable-5-1"],
    getKeyUrl: "https://console.anthropic.com/settings/keys",
  },
  {
    id: "kimi",
    label: "Kimi K2 (Moonshot)",
    keyHint: "sk-...",
    defaultModel: "kimi-k2-0905-preview",
    models: ["kimi-k2-0905-preview", "kimi-k2-turbo-preview", "kimi-k2-thinking"],
    getKeyUrl: "https://platform.moonshot.ai/console/api-keys",
  },
];

export function providerById(id: Provider): ProviderInfo {
  return PROVIDERS.find((p) => p.id === id) ?? PROVIDERS[0];
}

export function allModels(): { provider: Provider; model: string; label: string }[] {
  return PROVIDERS.flatMap((p) =>
    p.models.map((m) => ({ provider: p.id, model: m, label: `${p.label} · ${m}` })),
  );
}
