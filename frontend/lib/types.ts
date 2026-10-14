// Mirrors ../_shared/api-contract.md. Keep in sync with backend app/models/research.py.

export type Provider = "openai" | "anthropic" | "kimi";

export interface Source {
  title: string;
  url: string;
  snippet: string;
}

export type EventType =
  | "status"
  | "plan"
  | "sources"
  | "finding"
  | "token"
  | "report"
  | "await_approval"
  | "done"
  | "error";

export interface ResearchEvent {
  type: EventType;
  stage?: string | null;
  message?: string | null;
  data?: Record<string, any> | null;
  research_id: string;
  timestamp: string;
}

export interface Finding {
  index: number;
  subquestion: string;
  summary: string;
  sources: Source[];
}

export type Stage =
  | "idle"
  | "planning"
  | "researching"
  | "report"
  | "awaiting"
  | "done"
  | "error";

export type DecisionAction = "approve" | "edit" | "reject";

// A run paused by `await_approval` (see _shared/api-contract.md "Approval gates").
export interface Approval {
  runId: string;
  stage: string; // the stage under review: "01_plan", or "02_search" for a stop
  nextStage: string;
  reason: "review" | "stop";
  artifactPath: string; // relative to the run folder, e.g. "01_plan/plan.md"
  content: string; // the artifact as the backend wrote it
  allowedActions: DecisionAction[];
  stopReason: string | null; // STOP.md text when reason = "stop"
}

export interface ResearchState {
  id: string | null;
  query: string;
  provider: Provider;
  model: string;
  stage: Stage;
  statusMessage: string;
  progress: number; // 0..1
  plan: string[];
  findings: Finding[];
  report: string;
  reportSources: Source[];
  error: string | null;
  startedAt: number | null;
  finishedAt: number | null;
  running: boolean;
  approval: Approval | null; // set while a run waits on a person
}
