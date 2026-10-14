"use client";

import { AlertTriangle, Check, Circle, Loader2, PauseCircle } from "lucide-react";

import type { ResearchState, Stage } from "@/lib/types";

const STAGES: { key: Stage; label: string }[] = [
  { key: "planning", label: "Planning" },
  { key: "researching", label: "Researching" },
  { key: "report", label: "Report" },
];

const ORDER: Record<string, number> = {
  idle: 0,
  planning: 1,
  awaiting: 1.5, // plan done, search not started (or stopped at search)
  researching: 2,
  report: 3,
  done: 4,
  error: 99,
};

export function ProgressStages({ state }: { state: ResearchState }) {
  const cur = ORDER[state.stage] ?? 0;
  return (
    <div className="card p-4">
      <div className="flex flex-wrap items-center gap-3">
        {STAGES.map((s, i) => {
          const n = ORDER[s.key];
          const done = state.stage !== "error" && cur > n;
          const active = state.stage === s.key;
          return (
            <div key={s.key} className="flex items-center gap-2">
              <span
                className="flex h-6 w-6 items-center justify-center rounded-full border"
                style={{
                  borderColor: active ? "var(--accent)" : "var(--border)",
                  background: done ? "var(--accent)" : "transparent",
                  color: done ? "var(--accent-fg)" : "var(--fg)",
                }}
              >
                {done ? (
                  <Check className="h-3.5 w-3.5" />
                ) : active ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Circle className="h-3 w-3" />
                )}
              </span>
              <span
                className="text-sm"
                style={{ color: active || done ? "var(--fg)" : "var(--muted)" }}
              >
                {s.label}
              </span>
              {i < STAGES.length - 1 && (
                <span className="mx-1 h-px w-6" style={{ background: "var(--border)" }} />
              )}
            </div>
          );
        })}
        {state.running && (
          <span className="ml-auto inline-flex items-center gap-1.5 text-xs" style={{ color: "var(--accent)" }}>
            <span className="pulse-dot h-2 w-2 rounded-full" style={{ background: "var(--accent)" }} />
            live
          </span>
        )}
        {state.stage === "awaiting" && (
          <span className="ml-auto inline-flex items-center gap-1 text-xs" style={{ color: "var(--accent)" }}>
            <PauseCircle className="h-3.5 w-3.5" /> waiting for you
          </span>
        )}
        {state.stage === "error" && (
          <span className="ml-auto inline-flex items-center gap-1 text-xs" style={{ color: "#d9534f" }}>
            <AlertTriangle className="h-3.5 w-3.5" /> error
          </span>
        )}
      </div>
      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full" style={{ background: "var(--surface-2)" }}>
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${Math.round((state.progress || 0) * 100)}%`, background: "var(--accent)" }}
        />
      </div>
      {state.statusMessage && (
        <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
          {state.statusMessage}
        </p>
      )}
    </div>
  );
}
