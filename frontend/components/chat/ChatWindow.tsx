"use client";

import { useEffect, useRef, useState } from "react";
import { RotateCcw, Send, Square } from "lucide-react";

import { useApiKeys } from "@/contexts/ApiKeyContext";
import { useChat } from "@/contexts/ChatContext";
import type { Provider } from "@/lib/chatTypes";
import { providerById } from "@/lib/models";
import { Markdown } from "../Markdown";
import { ModelSelector } from "../ModelSelector";
import { MemoryPanel } from "./MemoryPanel";
import { TurnTimeline } from "./TurnTimeline";

export function ChatWindow() {
  const { messages, running, run, stop, reset } = useChat();
  const { keys, hasKey } = useApiKeys();
  const [provider, setProvider] = useState<Provider>("openai");
  const [model, setModel] = useState(providerById("openai").defaultModel);
  const [input, setInput] = useState("");
  const [warn, setWarn] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = () => {
    const m = input.trim();
    if (!m) return;
    if (!hasKey(provider)) {
      setWarn(`Add your ${providerById(provider).label} API key with the Keys button first.`);
      return;
    }
    setWarn(null);
    setInput("");
    run(m, { provider, model, apiKey: keys[provider]! });
  };

  const onKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
      <div className="flex flex-col">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <ModelSelector provider={provider} model={model} onChange={(p, m) => { setProvider(p); setModel(m); }} />
          {messages.length > 0 && (
            <button className="btn btn-ghost" onClick={reset}>
              <RotateCcw className="h-4 w-4" /> New chat
            </button>
          )}
        </div>

        <div className="min-h-[50vh] space-y-4">
          {messages.length === 0 && (
            <div className="pt-16 text-center" style={{ color: "var(--muted)" }}>
              <p className="text-lg">Ask me anything.</p>
              <p className="mt-1 text-sm">
                I can search the web, run deep research, manage a local calendar,
                read/write workspace files, and remember things.
              </p>
            </div>
          )}
          {messages.map((m, i) =>
            m.role === "user" ? (
              <div key={i} className="flex justify-end">
                <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2"
                     style={{ background: "var(--accent)", color: "var(--accent-fg)" }}>
                  {m.content}
                </div>
              </div>
            ) : (
              <div key={i} className="space-y-2">
                {m.activity && (m.activity.running || m.activity.tools.length > 0 || m.activity.phases.length > 0) && (
                  <div className="card p-3"><TurnTimeline activity={m.activity} /></div>
                )}
                {m.content && <div className="card p-4"><Markdown>{m.content}</Markdown></div>}
              </div>
            ),
          )}
          <div ref={endRef} />
        </div>

        <div className="sticky bottom-0 mt-3 pt-2" style={{ background: "var(--bg)" }}>
          <div className="card p-2">
            <textarea
              className="input min-h-[60px] resize-y"
              style={{ border: "none" }}
              placeholder="Message the assistant...  (Cmd/Ctrl+Enter to send)"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKey}
            />
            <div className="mt-1 flex items-center justify-end gap-2">
              {running ? (
                <button className="btn btn-ghost" onClick={stop}><Square className="h-4 w-4" /> Stop</button>
              ) : (
                <button className="btn btn-primary" onClick={send}><Send className="h-4 w-4" /> Send</button>
              )}
            </div>
          </div>
          {warn && <p className="mt-1 text-sm" style={{ color: "#d9534f" }}>{warn}</p>}
        </div>
      </div>

      <div className="hidden lg:block">
        <MemoryPanel refreshKey={`${messages.length}-${running}`} />
      </div>
    </div>
  );
}
