// SSE client for both the research stream and the agent chat turn. We POST (so
// EventSource is unusable) and parse the text/event-stream body from a fetch
// ReadableStream. One shared reader; two typed entry points.
import type { DecisionAction, Provider, ResearchEvent } from "./types";
import type { MemoryCandidate, TurnEvent } from "./chatTypes";

export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL?.replace(/\/$/, "") || "http://localhost:8080";

export async function postSSE<T>(
  path: string,
  body: unknown,
  onEvent: (e: T) => void,
  onError: (message: string, code: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (err: any) {
    if (err?.name === "AbortError") return;
    onError(`Could not reach the backend at ${BACKEND_URL}.`, "network");
    return;
  }
  if (!res.ok || !res.body) {
    let msg = `Request failed (${res.status}).`;
    try {
      const b = await res.json();
      if (b?.detail) {
        msg = typeof b.detail === "string"
          ? b.detail
          : b.detail?.[0]?.msg ? `Invalid request: ${b.detail[0].msg}` : JSON.stringify(b.detail);
      }
    } catch {
      /* non-JSON */
    }
    onError(msg, res.status === 422 ? "validation" : "provider");
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        for (const line of frame.split("\n")) {
          const t = line.trimStart();
          if (!t.startsWith("data:")) continue;
          const payload = t.slice(5).trim();
          if (!payload) continue;
          try {
            onEvent(JSON.parse(payload) as T);
          } catch {
            /* ignore malformed frame */
          }
        }
      }
    }
  } catch (err: any) {
    if (err?.name !== "AbortError") onError("The stream was interrupted.", "network");
  }
}

// --- research ---
export interface StreamParams {
  query: string;
  provider: Provider;
  model: string;
  apiKey: string;
  maxSubquestions?: number;
  search?: boolean;
  reviewPlan?: boolean;
  signal?: AbortSignal;
}

export async function streamResearch(
  params: StreamParams,
  onEvent: (e: ResearchEvent) => void,
): Promise<void> {
  await postSSE<ResearchEvent>(
    "/research/stream",
    {
      query: params.query,
      provider: params.provider,
      model: params.model || undefined,
      api_key: params.apiKey,
      max_subquestions: params.maxSubquestions ?? 4,
      search: params.search ?? true,
      review_plan: params.reviewPlan ?? false,
    },
    onEvent,
    (message, code) =>
      onEvent({ type: "error", stage: "error", message, data: { code }, research_id: "", timestamp: new Date().toISOString() }),
    params.signal,
  );
}

const researchError = (message: string, code: string): ResearchEvent => ({
  type: "error", stage: "error", message, data: { code }, research_id: "", timestamp: new Date().toISOString(),
});

// Resume a run paused by `await_approval`. Streams the rest of the run.
export interface DecisionParams {
  runId: string;
  stage: string;
  action: DecisionAction;
  editedContent?: string;
  note?: string;
  provider: Provider;
  model: string;
  apiKey: string;
  signal?: AbortSignal;
}

export async function streamDecision(
  params: DecisionParams,
  onEvent: (e: ResearchEvent) => void,
): Promise<void> {
  await postSSE<ResearchEvent>(
    `/research/runs/${encodeURIComponent(params.runId)}/decision`,
    {
      stage: params.stage,
      action: params.action,
      edited_content: params.editedContent,
      note: params.note || undefined,
      provider: params.provider,
      model: params.model || undefined,
      api_key: params.apiKey,
    },
    onEvent,
    (message, code) => onEvent(researchError(message, code)),
    params.signal,
  );
}

// --- chat (agent turn) ---
export interface ChatParams {
  message: string;
  provider: Provider;
  model: string;
  apiKey: string;
  conversationId?: number | null;
  backend?: string;
  signal?: AbortSignal;
}

export async function streamChat(
  params: ChatParams,
  onEvent: (e: TurnEvent) => void,
): Promise<void> {
  await postSSE<TurnEvent>(
    "/chat/stream",
    {
      message: params.message,
      provider: params.provider,
      model: params.model || undefined,
      api_key: params.apiKey,
      conversation_id: params.conversationId ?? undefined,
      backend: params.backend || undefined,
    },
    onEvent,
    (message, code) =>
      onEvent({ type: "error", phase: "error", message, data: { code }, turn_id: "", timestamp: new Date().toISOString() }),
    params.signal,
  );
}

// --- read-only memory/trace ---
export async function fetchCandidates(): Promise<{ review: boolean; candidates: MemoryCandidate[]; folder: string | null }> {
  try {
    const r = await fetch(`${BACKEND_URL}/memory/candidates`);
    return r.ok ? r.json() : { review: false, candidates: [], folder: null };
  } catch {
    return { review: false, candidates: [], folder: null };
  }
}

// Approve (optionally with edited text) or reject one proposed fact. Returns false on failure.
export async function decideCandidate(id: string, action: "approve" | "reject", text?: string): Promise<boolean> {
  try {
    const r = await fetch(`${BACKEND_URL}/memory/candidates/${encodeURIComponent(id)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, text }),
    });
    return r.ok;
  } catch {
    return false;
  }
}

export async function fetchMemory(): Promise<{ facts: any[]; counts: Record<string, number> }> {
  try {
    const r = await fetch(`${BACKEND_URL}/memory`);
    return r.ok ? r.json() : { facts: [], counts: {} };
  } catch {
    return { facts: [], counts: {} };
  }
}

export async function fetchTrace(): Promise<{ tool_runs: any[] }> {
  try {
    const r = await fetch(`${BACKEND_URL}/trace`);
    return r.ok ? r.json() : { tool_runs: [] };
  } catch {
    return { tool_runs: [] };
  }
}
