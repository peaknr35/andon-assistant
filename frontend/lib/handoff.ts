// Shift handoff: types, SSE client and reducer. Mirrors ../../_shared/shift-handoff.md
// and backend app/models/handoff.py.
import { BACKEND_URL, postSSE } from "./api";
import type { DecisionAction, Provider } from "./types";

export const HANDOFF_STAGES = [
  { key: "01_notes", label: "Notes" },
  { key: "02_summary", label: "Summary" },
  { key: "03_issues", label: "Issues & risks" },
  { key: "04_brief", label: "Next-shift brief" },
] as const;

export interface HandoffEvent {
  type: "status" | "token" | "stage_output" | "await_approval" | "done" | "error";
  stage?: string | null;
  message?: string | null;
  data?: Record<string, any> | null;
  run_id: string;
  timestamp: string;
}

export interface HandoffGate {
  runId: string;
  stage: string;
  nextStage: string | null;
  artifact: string;
  content: string;
  warnings: string[];
  notes: string;
}

export interface HandoffState {
  runId: string | null;
  line: string;
  shift: string;
  stage: string | null; // stage currently running / last run
  done: Record<string, boolean>;
  streaming: string;
  outputs: Record<string, string>;
  gate: HandoffGate | null;
  brief: string;
  statusMessage: string;
  error: string | null;
  errorCode: string | null;
  running: boolean;
  finished: "complete" | "rejected" | null;
}

export function initialHandoff(overrides: Partial<HandoffState> = {}): HandoffState {
  return {
    runId: null, line: "", shift: "", stage: null, done: {}, streaming: "", outputs: {},
    gate: null, brief: "", statusMessage: "", error: null, errorCode: null, running: false,
    finished: null, ...overrides,
  };
}

export function toGate(d: Record<string, any>): HandoffGate {
  return {
    runId: String(d.run_id ?? ""),
    stage: String(d.stage ?? ""),
    nextStage: (d.next_stage as string | null) ?? null,
    artifact: String(d.artifact ?? ""),
    content: String(d.artifact_content ?? ""),
    warnings: (d.citation_warnings as string[]) ?? [],
    notes: String(d.notes ?? ""),
  };
}

export function applyHandoffEvent(s: HandoffState, e: HandoffEvent): HandoffState {
  const n: HandoffState = { ...s, done: { ...s.done }, outputs: { ...s.outputs } };
  if (e.run_id && e.type !== "error") n.runId = e.run_id;
  switch (e.type) {
    case "status":
      n.stage = e.stage ?? n.stage;
      n.statusMessage = e.message ?? "";
      n.streaming = "";
      n.gate = null;
      n.running = true;
      if (e.stage === "01_notes") n.done["01_notes"] = true;
      break;
    case "token":
      n.streaming += (e.data?.text as string) ?? "";
      break;
    case "stage_output":
      if (e.stage) {
        n.outputs[e.stage] = (e.data?.content as string) ?? "";
        n.done[e.stage] = true;
      }
      n.streaming = "";
      break;
    case "await_approval":
      n.gate = toGate(e.data ?? {});
      n.runId = n.gate.runId || n.runId;
      n.statusMessage = "Waiting for your review.";
      n.running = false;
      n.error = null;
      break;
    case "done": {
      const status = e.data?.status as string;
      n.running = false;
      if (status === "complete") {
        n.brief = (e.data?.brief as string) ?? n.outputs["04_brief"] ?? "";
        n.finished = "complete";
        n.statusMessage = "Brief ready.";
      } else if (status === "rejected") {
        n.gate = null;
        n.finished = "rejected";
        n.statusMessage = "Rejected. The handoff was closed.";
      }
      break;
    }
    case "error":
      n.error = e.message ?? "Unknown error";
      n.errorCode = (e.data?.code as string) ?? null;
      n.running = false;
      if (n.errorCode === "stage_mismatch" || n.errorCode === "run_not_found") n.gate = null;
      break;
  }
  return n;
}

const errEvent = (message: string, code: string): HandoffEvent => ({
  type: "error", message, data: { code }, run_id: "", timestamp: new Date().toISOString(),
});

export interface StartParams {
  notes: string; line: string; shift: string; supervisor?: string;
  provider: Provider; model: string; apiKey: string; signal?: AbortSignal;
}

export function streamHandoff(p: StartParams, onEvent: (e: HandoffEvent) => void) {
  return postSSE<HandoffEvent>(
    "/handoff/stream",
    { notes: p.notes, line: p.line, shift: p.shift, supervisor: p.supervisor || undefined,
      provider: p.provider, model: p.model || undefined, api_key: p.apiKey },
    onEvent, (m, c) => onEvent(errEvent(m, c)), p.signal,
  );
}

export interface DecideParams {
  runId: string; stage: string; action: DecisionAction; editedContent?: string; note?: string;
  provider: Provider; model: string; apiKey: string; signal?: AbortSignal;
}

export function streamHandoffDecision(p: DecideParams, onEvent: (e: HandoffEvent) => void) {
  return postSSE<HandoffEvent>(
    `/handoff/runs/${encodeURIComponent(p.runId)}/decision`,
    { stage: p.stage, action: p.action, edited_content: p.editedContent, note: p.note || undefined,
      provider: p.provider, model: p.model || undefined, api_key: p.apiKey },
    onEvent, (m, c) => onEvent(errEvent(m, c)), p.signal,
  );
}

export interface HandoffRunSummary {
  run_id: string; line: string; shift: string; supervisor: string; created_at: string; status: string;
}

export async function fetchHandoffRuns(): Promise<HandoffRunSummary[]> {
  try {
    const r = await fetch(`${BACKEND_URL}/handoff/runs`);
    return r.ok ? (await r.json()).runs ?? [] : [];
  } catch {
    return [];
  }
}

export async function fetchHandoffRun(runId: string): Promise<Record<string, any> | null> {
  try {
    const r = await fetch(`${BACKEND_URL}/handoff/runs/${encodeURIComponent(runId)}`);
    return r.ok ? r.json() : null;
  } catch {
    return null;
  }
}

// Rebuild view state from GET /handoff/runs/{id} (to resume a paused handoff or view a finished one).
export function stateFromRun(d: Record<string, any>): HandoffState {
  const files = (d.files ?? {}) as Record<string, string>;
  const done: Record<string, boolean> = {};
  for (const [k, v] of Object.entries(d.stage_status ?? {})) done[k] = v === "done";
  const outputs: Record<string, string> = {};
  if (files["02_summary/summary.md"]) outputs["02_summary"] = files["02_summary/summary.md"];
  if (files["03_issues/issues.md"]) outputs["03_issues"] = files["03_issues/issues.md"];
  if (files["04_brief/brief.md"]) outputs["04_brief"] = files["04_brief/brief.md"];
  const status = String(d.status ?? "");
  return initialHandoff({
    runId: d.run_id, line: d.line, shift: d.shift, done, outputs,
    gate: d.awaiting ? toGate(d.awaiting) : null,
    brief: outputs["04_brief"] ?? "",
    finished: status === "complete" ? "complete" : status === "rejected" ? "rejected" : null,
    statusMessage: d.awaiting ? "Waiting for your review." : status,
    error: status === "stopped" ? "Stopped: the notes were too short. See STOP.md in the run folder." : null,
  });
}
