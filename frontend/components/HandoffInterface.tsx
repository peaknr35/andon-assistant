"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Check, ClipboardCopy, Download, Loader2, PauseCircle, Play, RotateCcw, X } from "lucide-react";

import { useApiKeys } from "@/contexts/ApiKeyContext";
import {
  HANDOFF_STAGES, applyHandoffEvent, fetchHandoffRun, fetchHandoffRuns, initialHandoff, stateFromRun,
  streamHandoff, streamHandoffDecision,
  type HandoffEvent, type HandoffRunSummary, type HandoffState,
} from "@/lib/handoff";
import { providerById } from "@/lib/models";
import { loadSession, saveSession } from "@/lib/storage";
import type { DecisionAction, Provider } from "@/lib/types";
import { Markdown } from "./Markdown";
import { ModelSelector } from "./ModelSelector";

const SESSION_KEY = "andon.handoff.v1";
const SHIFTS = ["Day", "Afternoon", "Night"];
const GATE_TITLE: Record<string, string> = {
  "02_summary": "Review the shift summary",
  "03_issues": "Review issues & risks",
};

function Stages({ s }: { s: HandoffState }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      {HANDOFF_STAGES.map((st, i) => {
        const done = !!s.done[st.key];
        const waiting = s.gate?.stage === st.key;
        const active = s.running && s.stage === st.key && !done;
        return (
          <div key={st.key} className="flex items-center gap-2 text-sm">
            <span className="flex h-6 w-6 items-center justify-center rounded-full border"
              style={{ borderColor: active || waiting ? "var(--accent)" : "var(--border)",
                       background: done && !waiting ? "var(--accent)" : "transparent",
                       color: done && !waiting ? "var(--accent-fg)" : "var(--fg)" }}>
              {waiting ? <PauseCircle className="h-3.5 w-3.5" style={{ color: "var(--accent)" }} />
                : done ? <Check className="h-3.5 w-3.5" />
                : active ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                : <span className="text-xs">{i + 1}</span>}
            </span>
            <span style={{ color: done || active || waiting ? "var(--fg)" : "var(--muted)" }}>{st.label}</span>
            {i < HANDOFF_STAGES.length - 1 && <span className="mx-1 h-px w-5" style={{ background: "var(--border)" }} />}
          </div>
        );
      })}
    </div>
  );
}

function GatePanel({ s, busy, onDecide }: {
  s: HandoffState; busy: boolean;
  onDecide: (a: DecisionAction, edited?: string, note?: string) => void;
}) {
  const gate = s.gate!;
  const [text, setText] = useState(gate.content);
  const [note, setNote] = useState("");
  const [showNotes, setShowNotes] = useState(false);
  useEffect(() => { setText(gate.content); setNote(""); }, [gate.stage, gate.content]);
  const edited = text.replace(/\r\n/g, "\n").trim() !== gate.content.trim();
  const numbered = gate.notes.split("\n").map((l, i) => (l.trim() ? `L${i + 1}: ${l}` : "")).filter(Boolean).join("\n");

  return (
    <div className="card p-4" style={{ borderColor: "var(--accent)" }}>
      <div className="mb-2 flex items-center gap-2">
        <PauseCircle className="h-4 w-4" style={{ color: "var(--accent)" }} />
        <h2 className="text-sm font-semibold">{GATE_TITLE[gate.stage] ?? `Review ${gate.stage}`}</h2>
        <span className="ml-auto font-mono text-xs" style={{ color: "var(--muted)" }}>{gate.artifact}</span>
      </div>
      {gate.warnings.length > 0 && (
        <div className="mb-3 rounded p-3 text-xs" style={{ background: "rgba(217,149,0,0.12)", color: "var(--fg)" }}>
          <div className="mb-1 flex items-center gap-1.5 font-semibold" style={{ color: "#b07800" }}>
            <AlertTriangle className="h-3.5 w-3.5" /> Citation check: {gate.warnings.length} to look at before approving
          </div>
          <ul className="list-disc space-y-0.5 pl-5">{gate.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </div>
      )}
      <p className="mb-2 text-xs" style={{ color: "var(--muted)" }}>
        Every line should end with the note line it came from, like [L4]. Fix anything wrong; the next stage reads exactly this text.{" "}
        <button className="underline" onClick={() => setShowNotes((v) => !v)}>
          {showNotes ? "Hide" : "Show"} numbered notes
        </button>
      </p>
      {showNotes && (
        <pre className="mb-2 max-h-56 overflow-auto whitespace-pre-wrap rounded p-3 text-xs"
          style={{ background: "var(--surface-2)" }}>{numbered}</pre>
      )}
      <textarea className="input resize-y font-mono text-sm" value={text} spellCheck={false} disabled={busy}
        rows={Math.min(28, Math.max(10, text.split("\n").length + 2))} onChange={(e) => setText(e.target.value)} />
      <input className="input mt-2 text-sm" placeholder="Note for the run log (optional)" value={note}
        disabled={busy} onChange={(e) => setNote(e.target.value)} />
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button className="btn btn-primary" disabled={busy}
          onClick={() => (edited ? onDecide("edit", text, note) : onDecide("approve", undefined, note))}>
          <Check className="h-4 w-4" /> {edited ? "Approve with my edits" : "Approve"}
        </button>
        {edited && <button className="btn btn-ghost" disabled={busy} onClick={() => setText(gate.content)}>Undo edits</button>}
        <button className="btn btn-ghost ml-auto" disabled={busy} onClick={() => onDecide("reject", undefined, note)}>
          <X className="h-4 w-4" /> Reject
        </button>
      </div>
    </div>
  );
}

export function HandoffInterface() {
  const { keys, hasKey } = useApiKeys();
  const [provider, setProvider] = useState<Provider>("anthropic");
  const [model, setModel] = useState(providerById("anthropic").defaultModel);
  const [line, setLine] = useState("");
  const [shift, setShift] = useState("Day");
  const [supervisor, setSupervisor] = useState("");
  const [notes, setNotes] = useState("");
  const [warn, setWarn] = useState<string | null>(null);
  const [s, setS] = useState<HandoffState>(() => initialHandoff());
  const [recent, setRecent] = useState<HandoffRunSummary[]>([]);
  const [copied, setCopied] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    const saved = loadSession<HandoffState | null>(SESSION_KEY, null);
    if (saved) setS({ ...saved, running: false });
    setHydrated(true);
  }, []);
  useEffect(() => { if (hydrated) saveSession(SESSION_KEY, s); }, [s, hydrated]);
  const refreshRecent = useCallback(() => { void fetchHandoffRuns().then(setRecent); }, []);
  useEffect(() => { refreshRecent(); }, [refreshRecent, s.gate?.stage, s.finished]);

  const onEvent = (e: HandoffEvent) => setS((prev) => applyHandoffEvent(prev, e));
  const needKey = (): string | null => {
    if (!hasKey(provider)) {
      setWarn(`Add your ${providerById(provider).label} API key with the Keys button first.`);
      return null;
    }
    setWarn(null);
    return keys[provider]!;
  };

  const start = () => {
    if (!line.trim()) return setWarn("Enter the line or area.");
    if (notes.trim().split(/\s+/).length < 15) return setWarn("Paste the end-of-shift notes (at least 15 words).");
    const apiKey = needKey();
    if (!apiKey) return;
    abort.current?.abort();
    abort.current = new AbortController();
    setS(initialHandoff({ line: line.trim(), shift, running: true, stage: "01_notes", statusMessage: "Starting..." }));
    void streamHandoff({ notes, line: line.trim(), shift, supervisor, provider, model, apiKey,
                         signal: abort.current.signal }, onEvent);
  };

  const decide = (action: DecisionAction, editedContent?: string, note?: string) => {
    if (!s.gate || !s.runId) return;
    const apiKey = needKey();
    if (!apiKey) return;
    abort.current?.abort();
    abort.current = new AbortController();
    setS((p) => ({ ...p, running: true, error: null, statusMessage: "Sending your decision..." }));
    void streamHandoffDecision({ runId: s.runId, stage: s.gate.stage, action, editedContent, note,
                                 provider, model, apiKey, signal: abort.current.signal }, onEvent);
  };

  const openRun = async (runId: string) => {
    const d = await fetchHandoffRun(runId);
    if (!d) return;
    abort.current?.abort();
    setS(stateFromRun(d));
    if (d.provider) {
      setProvider(d.provider as Provider);
      setModel(d.model || providerById(d.provider as Provider).defaultModel);
    }
  };

  const copyBrief = async () => {
    try {
      await navigator.clipboard.writeText(s.brief);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard blocked */ }
  };
  const downloadBrief = () => {
    const url = URL.createObjectURL(new Blob([s.brief], { type: "text/markdown" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `handoff-${(s.line || "line").replace(/\W+/g, "-")}-${s.shift || "shift"}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const started = s.runId !== null || s.running;

  return (
    <div className="space-y-5">
      <section className="pt-8 text-center">
        <h1 className="text-2xl font-semibold sm:text-3xl">Shift handoff</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
          Paste your end-of-shift notes. You review the summary and the issues before the next-shift brief is written.
          Every line cites the note it came from.
        </p>
      </section>

      {!started && (
        <div className="card space-y-3 p-4">
          <div className="flex flex-wrap gap-2">
            <input className="input !w-auto flex-1" placeholder="Line / area (e.g. Line 4)" value={line}
              onChange={(e) => setLine(e.target.value)} aria-label="Line" />
            <select className="input !w-auto" value={shift} onChange={(e) => setShift(e.target.value)} aria-label="Shift">
              {SHIFTS.map((x) => <option key={x}>{x}</option>)}
            </select>
            <input className="input !w-auto flex-1" placeholder="Outgoing supervisor (optional)" value={supervisor}
              onChange={(e) => setSupervisor(e.target.value)} aria-label="Supervisor" />
          </div>
          <textarea className="input min-h-[220px] resize-y font-mono text-sm" value={notes}
            onChange={(e) => setNotes(e.target.value)} aria-label="Shift notes"
            placeholder={"Raw notes, as you'd jot them. One thing per line works best.\ne.g.\nNear miss at station 6 - forklift, blind corner, no one hurt\nTorque gun T-12 drifting high, 3 parts in red bin\nRan 412 of 450\nC2 jammed twice, 35 min down, ticket 8812"} />
          <div className="flex flex-wrap items-center gap-3">
            <ModelSelector provider={provider} model={model} onChange={(p, m) => { setProvider(p); setModel(m); }} />
            <button className="btn btn-primary ml-auto" onClick={start}><Play className="h-4 w-4" /> Start handoff</button>
          </div>
          {warn && <p className="text-sm" style={{ color: "#d9534f" }}>{warn}</p>}
        </div>
      )}

      {started && (
        <div className="space-y-4">
          <div className="card space-y-3 p-4">
            <div className="flex items-center gap-2 text-sm" style={{ color: "var(--muted)" }}>
              <span><span style={{ color: "var(--fg)" }}>{s.line}</span> · {s.shift}</span>
              <button className="btn btn-ghost ml-auto !py-1" disabled={s.running}
                onClick={() => { abort.current?.abort(); setS(initialHandoff()); }}>
                <RotateCcw className="h-4 w-4" /> New handoff
              </button>
            </div>
            <Stages s={s} />
            {s.statusMessage && <p className="text-sm" style={{ color: "var(--muted)" }}>{s.statusMessage}</p>}
          </div>

          {s.error && (
            <div className="card p-4" style={{ borderColor: "#d9534f" }}>
              <p className="text-sm" style={{ color: "#d9534f" }}>{s.error}</p>
            </div>
          )}
          {warn && <p className="text-sm" style={{ color: "#d9534f" }}>{warn}</p>}

          {s.running && s.streaming && (
            <div className="card p-4">
              <pre className="whitespace-pre-wrap text-sm">{s.streaming}</pre>
            </div>
          )}

          {s.gate && !s.running && <GatePanel s={s} busy={s.running} onDecide={decide} />}

          {s.finished === "complete" && s.brief && (
            <div className="card p-5">
              <div className="mb-3 flex items-center gap-2">
                <h2 className="text-sm font-semibold">Next-shift brief</h2>
                <button className="btn btn-ghost ml-auto !py-1" onClick={() => void copyBrief()}>
                  <ClipboardCopy className="h-4 w-4" /> {copied ? "Copied" : "Copy"}
                </button>
                <button className="btn btn-ghost !py-1" onClick={downloadBrief}>
                  <Download className="h-4 w-4" /> .md
                </button>
              </div>
              <Markdown>{s.brief}</Markdown>
            </div>
          )}
        </div>
      )}

      {recent.length > 0 && (
        <div className="card p-4">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--muted)" }}>
            Recent handoffs
          </h2>
          <ul className="space-y-1 text-sm">
            {recent.slice(0, 8).map((r) => (
              <li key={r.run_id} className="flex items-center gap-2">
                <button className="underline-offset-2 hover:underline" onClick={() => void openRun(r.run_id)}>
                  {r.line} · {r.shift}
                </button>
                <span className="text-xs" style={{ color: "var(--muted)" }}>{new Date(r.created_at).toLocaleString()}</span>
                <span className="chip ml-auto"
                  style={r.status.startsWith("awaiting") ? { color: "var(--accent)" } : undefined}>{r.status}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
