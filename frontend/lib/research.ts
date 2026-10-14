// Pure reducer: fold a ResearchEvent into a ResearchState. Shared by the main
// research view and each compare column so behaviour is identical.
import type { Approval, Finding, Provider, ResearchEvent, ResearchState, Source } from "./types";

export function initialResearchState(
  overrides: Partial<ResearchState> = {},
): ResearchState {
  return {
    id: null,
    query: "",
    provider: "openai",
    model: "",
    stage: "idle",
    statusMessage: "",
    progress: 0,
    plan: [],
    findings: [],
    report: "",
    reportSources: [],
    error: null,
    startedAt: null,
    finishedAt: null,
    running: false,
    approval: null,
    ...overrides,
  };
}

export function applyEvent(state: ResearchState, e: ResearchEvent): ResearchState {
  const next: ResearchState = { ...state };
  if (e.research_id && !next.id) next.id = e.research_id;
  if (!next.startedAt) next.startedAt = Date.now();
  // Any progress event means the run moved past its gate.
  if (["status", "plan", "sources", "finding", "token", "report"].includes(e.type)) {
    next.approval = null;
  }

  switch (e.type) {
    case "status": {
      if (e.stage) next.stage = e.stage as ResearchState["stage"];
      if (e.message) next.statusMessage = e.message;
      const p = e.data?.progress;
      if (typeof p === "number") next.progress = p;
      next.running = true;
      break;
    }
    case "plan": {
      next.stage = "planning";
      next.plan = (e.data?.subquestions as string[]) ?? [];
      // A new (or edited) plan replaces earlier results: no stale findings/report.
      next.findings = [];
      next.report = "";
      next.reportSources = [];
      break;
    }
    case "sources": {
      next.stage = "researching";
      const idx = e.data?.index as number;
      const sources = (e.data?.sources as Source[]) ?? [];
      next.findings = upsertFinding(next.findings, {
        index: idx,
        subquestion: (e.data?.subquestion as string) ?? "",
        summary: findingAt(next.findings, idx)?.summary ?? "",
        sources,
      });
      break;
    }
    case "finding": {
      next.stage = "researching";
      const idx = e.data?.index as number;
      next.findings = upsertFinding(next.findings, {
        index: idx,
        subquestion: (e.data?.subquestion as string) ?? "",
        summary: (e.data?.summary as string) ?? "",
        sources: (e.data?.sources as Source[]) ?? findingAt(next.findings, idx)?.sources ?? [],
      });
      break;
    }
    case "token": {
      next.stage = "report";
      next.report += (e.data?.text as string) ?? "";
      break;
    }
    case "report": {
      next.stage = "report";
      next.report = (e.data?.report as string) ?? next.report;
      next.reportSources = (e.data?.sources as Source[]) ?? [];
      break;
    }
    case "await_approval": {
      next.stage = "awaiting";
      next.approval = toApproval(e.data ?? {});
      next.statusMessage =
        next.approval.reason === "stop"
          ? "Stopped: no usable web sources. Your call."
          : "Plan ready. Review it before the web search runs.";
      next.running = false;
      next.error = null;
      break;
    }
    case "done": {
      const status = (e.data?.status as string | undefined) ?? "complete";
      next.running = false;
      if (status === "paused") break; // stays "awaiting" until a decision is sent
      next.approval = null;
      next.finishedAt = Date.now();
      if (status === "rejected") {
        next.stage = "done";
        next.statusMessage = "Rejected. The run was closed without searching further.";
        break;
      }
      next.stage = "done";
      next.progress = 1;
      break;
    }
    case "error": {
      next.stage = next.approval ? "awaiting" : "error";
      next.error = e.message ?? "Unknown error";
      next.running = false;
      const code = e.data?.code as string | undefined;
      // A stale or missing run can't be decided on any more; drop the panel.
      if (code === "stage_mismatch" || code === "run_not_found") {
        next.approval = null;
        next.stage = "error";
      }
      if (!next.approval) next.finishedAt = Date.now();
      break;
    }
  }
  return next;
}

function toApproval(d: Record<string, any>): Approval {
  return {
    runId: String(d.run_id ?? ""),
    stage: String(d.stage ?? ""),
    nextStage: String(d.next_stage ?? ""),
    reason: d.reason === "stop" ? "stop" : "review",
    artifactPath: String(d.artifact ?? ""),
    content: String(d.artifact_content ?? ""),
    allowedActions: (d.allowed_actions as Approval["allowedActions"]) ?? ["approve", "edit", "reject"],
    stopReason: (d.stop_reason as string | null) ?? null,
  };
}

function findingAt(findings: Finding[], index: number): Finding | undefined {
  return findings.find((f) => f.index === index);
}

function upsertFinding(findings: Finding[], f: Finding): Finding[] {
  const i = findings.findIndex((x) => x.index === f.index);
  if (i === -1) return [...findings, f].sort((a, b) => a.index - b.index);
  const copy = [...findings];
  copy[i] = { ...copy[i], ...f };
  return copy;
}

export function elapsedMs(state: ResearchState): number | null {
  if (!state.startedAt) return null;
  return (state.finishedAt ?? Date.now()) - state.startedAt;
}

export function newRunState(query: string, provider: Provider, model: string): ResearchState {
  return initialResearchState({
    query,
    provider,
    model,
    stage: "planning",
    statusMessage: "Starting...",
    running: true,
    startedAt: Date.now(),
  });
}
