"use client";

import { useEffect, useState } from "react";
import { Check, OctagonAlert, PauseCircle, X } from "lucide-react";

import type { Approval, DecisionAction } from "@/lib/types";

interface Props {
  approval: Approval;
  busy: boolean;
  onDecide: (action: DecisionAction, editedContent?: string, note?: string) => void;
}

// The human-in-the-loop gate: the stage's output file, editable, with
// approve / approve-with-edits / reject. For an andon STOP it shows STOP.md first.
export function ApprovalPanel({ approval, busy, onDecide }: Props) {
  const [text, setText] = useState(approval.content);
  const [note, setNote] = useState("");

  // A new gate (or a re-sent one) resets the editor.
  useEffect(() => {
    setText(approval.content);
    setNote("");
  }, [approval.runId, approval.stage, approval.content]);

  const edited = text.replace(/\r\n/g, "\n").trim() !== approval.content.trim();
  const stop = approval.reason === "stop";
  const can = (a: DecisionAction) => approval.allowedActions.includes(a);

  const proceed = () => (edited ? onDecide("edit", text, note) : onDecide("approve", undefined, note));

  return (
    <div className="card p-4" style={{ borderColor: stop ? "#d9534f" : "var(--accent)" }}>
      <div className="mb-2 flex items-center gap-2">
        {stop ? (
          <OctagonAlert className="h-4 w-4" style={{ color: "#d9534f" }} />
        ) : (
          <PauseCircle className="h-4 w-4" style={{ color: "var(--accent)" }} />
        )}
        <h2 className="text-sm font-semibold">
          {stop ? "Andon stop: no usable web sources" : "Review the plan before searching"}
        </h2>
        <span className="ml-auto font-mono text-xs" style={{ color: "var(--muted)" }}>
          {approval.artifactPath}
        </span>
      </div>

      {stop && approval.stopReason && (
        <pre
          className="mb-3 whitespace-pre-wrap rounded p-3 text-xs"
          style={{ background: "var(--surface-2)", color: "var(--fg)" }}
        >
          {approval.stopReason}
        </pre>
      )}

      <p className="mb-2 text-xs" style={{ color: "var(--muted)" }}>
        The next stage searches exactly the numbered lines. Reword, add or delete them, then continue.
      </p>
      <textarea
        className="input resize-y font-mono text-sm"
        rows={Math.min(24, Math.max(8, text.split("\n").length + 2))}
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={busy}
        spellCheck={false}
      />
      <input
        className="input mt-2 text-sm"
        placeholder="Note for the run log (optional)"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        disabled={busy}
      />

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {(edited ? can("edit") : can("approve")) && (
          <button className="btn btn-primary" onClick={proceed} disabled={busy}>
            <Check className="h-4 w-4" />
            {edited
              ? stop
                ? "Save plan & retry search"
                : "Approve with my edits"
              : stop
                ? "Retry search"
                : "Approve & search"}
          </button>
        )}
        {edited && (
          <button className="btn btn-ghost" onClick={() => setText(approval.content)} disabled={busy}>
            Undo edits
          </button>
        )}
        {can("reject") && (
          <button
            className="btn btn-ghost ml-auto"
            onClick={() => onDecide("reject", undefined, note)}
            disabled={busy}
          >
            <X className="h-4 w-4" /> {stop ? "Close run" : "Reject"}
          </button>
        )}
      </div>
    </div>
  );
}
