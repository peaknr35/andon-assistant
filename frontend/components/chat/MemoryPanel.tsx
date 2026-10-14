"use client";

import { useCallback, useEffect, useState } from "react";
import { Brain, Check, RefreshCw, X } from "lucide-react";

import { decideCandidate, fetchCandidates, fetchMemory, fetchTrace } from "@/lib/api";
import type { MemoryCandidate, MemoryFact, ToolRun } from "@/lib/chatTypes";

// One proposed fact: editable text, approve (saves the edited text) or reject.
function CandidateRow({ c, onDone }: { c: MemoryCandidate; onDone: () => void }) {
  const [text, setText] = useState(c.text);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const act = async (action: "approve" | "reject") => {
    setBusy(true);
    const ok = await decideCandidate(c.id, action, action === "approve" ? text : undefined);
    setBusy(false);
    setFailed(!ok);
    onDone();
  };
  return (
    <li className="space-y-1">
      <div className="flex items-start gap-1.5">
        <textarea
          className="input resize-none !py-1 text-sm"
          rows={Math.min(4, Math.max(1, Math.ceil(text.length / 30)))}
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={busy}
          title={c.reason}
          aria-label="Proposed fact"
        />
        <button className="btn btn-ghost !px-2 !py-1" onClick={() => void act("approve")} disabled={busy} aria-label="Approve" title="Save to memory">
          <Check className="h-3.5 w-3.5" style={{ color: "#38b36b" }} />
        </button>
        <button className="btn btn-ghost !px-2 !py-1" onClick={() => void act("reject")} disabled={busy} aria-label="Reject" title="Discard (won't be proposed again)">
          <X className="h-3.5 w-3.5" style={{ color: "#d9534f" }} />
        </button>
      </div>
      {failed && <p className="text-xs" style={{ color: "#d9534f" }}>Could not save that decision.</p>}
    </li>
  );
}

export function MemoryPanel({ refreshKey }: { refreshKey?: number | string }) {
  const [facts, setFacts] = useState<MemoryFact[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [runs, setRuns] = useState<ToolRun[]>([]);
  const [review, setReview] = useState(false);
  const [pending, setPending] = useState<MemoryCandidate[]>([]);

  const load = useCallback(async () => {
    const m = await fetchMemory();
    setFacts(m.facts ?? []);
    setCounts(m.counts ?? {});
    const cands = await fetchCandidates();
    setReview(cands.review);
    setPending(cands.candidates ?? []);
    const t = await fetchTrace();
    setRuns(t.tool_runs ?? []);
  }, []);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  return (
    <div className="card p-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Brain className="h-4 w-4" /> Memory
        </h2>
        <button className="btn btn-ghost !px-2 !py-1" onClick={() => void load()} aria-label="Refresh">
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="mb-3 flex flex-wrap gap-1.5">
        {Object.entries(counts).map(([k, v]) => (
          <span key={k} className="chip">{k}: {v}</span>
        ))}
      </div>
      {review && (
        <div className="mb-3">
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--muted)" }}>
            Waiting for your review ({pending.length})
          </h3>
          {pending.length ? (
            <ul className="space-y-1.5">
              {pending.map((c) => <CandidateRow key={c.id} c={c} onDone={() => void load()} />)}
            </ul>
          ) : (
            <p className="text-xs" style={{ color: "var(--muted)" }}>Nothing waiting. New facts the assistant picks up land here first.</p>
          )}
        </div>
      )}
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--muted)" }}>
        Facts
      </h3>
      <ul className="mb-3 space-y-1 text-sm">
        {facts.length ? facts.slice(0, 25).map((f) => (
          <li key={f.id} className="flex gap-2">
            <span title={f.source} style={{ color: f.source === "auto" ? "var(--muted)" : "#38b36b" }}>.</span>
            <span>{f.text}</span>
          </li>
        )) : <li style={{ color: "var(--muted)" }}>No memories yet.</li>}
      </ul>
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--muted)" }}>
        Recent tools
      </h3>
      <ul className="space-y-1 text-xs font-mono" style={{ color: "var(--muted)" }}>
        {runs.slice(0, 12).map((r, i) => (
          <li key={i}>{r.ok ? "+" : "x"} {r.tool}</li>
        ))}
      </ul>
    </div>
  );
}
