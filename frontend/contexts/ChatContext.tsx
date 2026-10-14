"use client";

import {
  createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode,
} from "react";

import { streamChat } from "@/lib/api";
import { emptyActivity, type ChatMessage, type Provider, type TurnEvent } from "@/lib/chatTypes";
import { loadSession, saveSession } from "@/lib/storage";

interface RunOpts {
  provider: Provider;
  model: string;
  apiKey: string;
  backend?: string;
}

interface ChatContextValue {
  messages: ChatMessage[];
  running: boolean;
  conversationId: number | null;
  run: (message: string, opts: RunOpts) => void;
  stop: () => void;
  reset: () => void;
}

const ChatContext = createContext<ChatContextValue | null>(null);
const KEY = "drs.chat.v1";

export function ChatProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [running, setRunning] = useState(false);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    const s = loadSession<{ messages: ChatMessage[]; conversationId: number | null } | null>(KEY, null);
    if (s) {
      setMessages((s.messages ?? []).map((m) =>
        m.activity ? { ...m, activity: { ...m.activity, running: false } } : m));
      setConversationId(s.conversationId ?? null);
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) saveSession(KEY, { messages, conversationId });
  }, [messages, conversationId, hydrated]);

  const run = useCallback((message: string, opts: RunOpts) => {
    abort.current?.abort();
    const ctrl = new AbortController();
    abort.current = ctrl;
    setRunning(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: message },
      { role: "assistant", content: "", activity: emptyActivity() },
    ]);

    const apply = (e: TurnEvent) => {
      setMessages((prev) => {
        const copy = [...prev];
        const idx = copy.length - 1;
        const last = copy[idx];
        if (!last || last.role !== "assistant") return prev;
        const a = { ...(last.activity ?? emptyActivity()) };
        a.phases = [...a.phases];
        a.tools = a.tools.map((t) => ({ ...t }));
        let content = last.content;
        switch (e.type) {
          case "phase":
            if (e.phase) {
              a.phase = e.phase;
              if (!a.phases.includes(e.phase)) a.phases.push(e.phase);
            }
            break;
          case "memory":
            {
              const items = (e.data?.items as string[]) ?? [];
              if (e.name === "save") a.saved = items;
              else if (e.name === "propose") a.proposed = items;
              else if (e.name === "promote") a.promoted = items;
              else a.recalled = items;
            }
            break;
          case "tool_call":
            a.tools.push({ name: e.name ?? "", args: e.data?.args, running: true });
            break;
          case "tool_result": {
            for (let i = a.tools.length - 1; i >= 0; i--) {
              if (a.tools[i].name === e.name && a.tools[i].running) {
                a.tools[i] = { ...a.tools[i], result: e.data?.result, ok: e.data?.ok, running: false };
                break;
              }
            }
            break;
          }
          case "token":
            content += (e.data?.text as string) ?? "";
            break;
          case "final":
            content = e.message ?? content;
            break;
          case "error":
            a.running = false;
            content = content || `\u26a0 ${e.message ?? "error"}`;
            break;
          case "done":
            a.running = false;
            break;
        }
        copy[idx] = { ...last, content, activity: a };
        return copy;
      });
      if (e.type === "done") {
        setRunning(false);
        const cid = e.data?.conversation_id;
        if (typeof cid === "number") setConversationId(cid);
      } else if (e.type === "error") {
        setRunning(false);
      }
    };

    void streamChat(
      {
        message, provider: opts.provider, model: opts.model, apiKey: opts.apiKey,
        conversationId, backend: opts.backend, signal: ctrl.signal,
      },
      apply,
    );
  }, [conversationId]);

  const stop = useCallback(() => {
    abort.current?.abort();
    setRunning(false);
    setMessages((prev) => {
      const copy = [...prev];
      const last = copy[copy.length - 1];
      if (last?.activity) copy[copy.length - 1] = { ...last, activity: { ...last.activity, running: false } };
      return copy;
    });
  }, []);

  const reset = useCallback(() => {
    abort.current?.abort();
    setMessages([]);
    setConversationId(null);
    setRunning(false);
  }, []);

  return (
    <ChatContext.Provider value={{ messages, running, conversationId, run, stop, reset }}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChat(): ChatContextValue {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be used within <ChatProvider>");
  return ctx;
}
