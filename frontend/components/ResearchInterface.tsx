"use client";

import { useState } from "react";
import { RotateCcw, Search, Square } from "lucide-react";

import { useApiKeys } from "@/contexts/ApiKeyContext";
import { useResearch } from "@/contexts/ResearchContext";
import { providerById } from "@/lib/models";
import type { DecisionAction, Provider } from "@/lib/types";
import { ApprovalPanel } from "./ApprovalPanel";
import { FindingCard } from "./FindingCard";
import { ModelSelector } from "./ModelSelector";
import { ProgressStages } from "./ProgressStages";
import { ReportView } from "./ReportView";

export function ResearchInterface() {
  const { main, runMain, stopMain, resetMain, decideMain } = useResearch();
  const { keys, hasKey } = useApiKeys();

  const [query, setQuery] = useState("");
  const [provider, setProvider] = useState<Provider>("openai");
  const [model, setModel] = useState(providerById("openai").defaultModel);
  const [maxSub, setMaxSub] = useState(4);
  const [search, setSearch] = useState(true);
  const [reviewPlan, setReviewPlan] = useState(true);
  const [warn, setWarn] = useState<string | null>(null);

  const running = main.running;
  const showResults = main.stage !== "idle";

  const submit = () => {
    const q = query.trim();
    if (q.length < 3) {
      setWarn("Enter a question (at least 3 characters).");
      return;
    }
    if (!hasKey(provider)) {
      setWarn(`Add your ${providerById(provider).label} API key with the Keys button first.`);
      return;
    }
    setWarn(null);
    runMain({ query: q, provider, model, apiKey: keys[provider]!, maxSubquestions: maxSub, search, reviewPlan });
  };

  const decide = (action: DecisionAction, editedContent?: string, note?: string) => {
    if (!hasKey(main.provider)) {
      setWarn(`Add your ${providerById(main.provider).label} API key with the Keys button to continue.`);
      return;
    }
    setWarn(null);
    decideMain({ action, editedContent, note, apiKey: keys[main.provider]! });
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="space-y-5">
      <section className="pt-8 text-center">
        <h1 className="text-2xl font-semibold sm:text-3xl">What do you want to research?</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
          Plan the question, search the live web, and write a cited report — streamed as it happens.
        </p>
      </section>

      <div className="card p-4">
        <textarea
          className="input min-h-[96px] resize-y"
          placeholder="e.g. What are the tradeoffs between serverless and containers for a small SaaS in 2026?"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <div className="mt-3 flex flex-wrap items-center gap-4">
          <ModelSelector
            provider={provider}
            model={model}
            onChange={(p, m) => {
              setProvider(p);
              setModel(m);
            }}
          />
          <label className="flex items-center gap-2 text-sm" style={{ color: "var(--muted)" }}>
            <span>Depth</span>
            <input
              type="range"
              min={1}
              max={8}
              value={maxSub}
              onChange={(e) => setMaxSub(Number(e.target.value))}
            />
            <span className="tabular-nums">{maxSub}</span>
          </label>
          <label className="flex items-center gap-2 text-sm" style={{ color: "var(--muted)" }}>
            <input type="checkbox" checked={search} onChange={(e) => setSearch(e.target.checked)} />
            Live web search
          </label>
          <label
            className="flex items-center gap-2 text-sm"
            style={{ color: "var(--muted)" }}
            title="Pause after planning so you can edit or approve the sub-questions before any search runs."
          >
            <input type="checkbox" checked={reviewPlan} onChange={(e) => setReviewPlan(e.target.checked)} />
            Review plan first
          </label>
          <div className="ml-auto flex items-center gap-2">
            {running ? (
              <button className="btn btn-ghost" onClick={stopMain}>
                <Square className="h-4 w-4" /> Stop
              </button>
            ) : (
              <button className="btn btn-primary" onClick={submit}>
                <Search className="h-4 w-4" /> Research
              </button>
            )}
            {showResults && !running && (
              <button
                className="btn btn-ghost"
                onClick={() => {
                  resetMain();
                  setQuery("");
                }}
              >
                <RotateCcw className="h-4 w-4" /> New
              </button>
            )}
          </div>
        </div>
        {warn && (
          <p className="mt-2 text-sm" style={{ color: "#d9534f" }}>
            {warn}
          </p>
        )}
      </div>

      {showResults && (
        <div className="space-y-4">
          <div className="text-sm" style={{ color: "var(--muted)" }}>
            Researching: <span style={{ color: "var(--fg)" }}>{main.query}</span> · {main.provider} ·{" "}
            {main.model || "default"}
          </div>
          <ProgressStages state={main} />
          {main.error && (
            <div className="card p-4" style={{ borderColor: "#d9534f" }}>
              <p className="text-sm" style={{ color: "#d9534f" }}>
                {main.error}
              </p>
            </div>
          )}
          {main.approval && (
            <ApprovalPanel approval={main.approval} busy={running} onDecide={decide} />
          )}
          {main.plan.length > 0 && !main.approval && (
            <div className="card p-4">
              <h2
                className="mb-2 text-xs font-semibold uppercase tracking-wide"
                style={{ color: "var(--muted)" }}
              >
                Research plan
              </h2>
              <ol className="list-decimal space-y-1 pl-5 text-sm">
                {main.plan.map((q, i) => (
                  <li key={i}>{q}</li>
                ))}
              </ol>
            </div>
          )}
          {main.findings.length > 0 && (
            <div className="space-y-3">
              <h2
                className="text-xs font-semibold uppercase tracking-wide"
                style={{ color: "var(--muted)" }}
              >
                Findings
              </h2>
              {main.findings.map((f) => (
                <FindingCard key={f.index} finding={f} defaultOpen={main.findings.length <= 3} />
              ))}
            </div>
          )}
          <ReportView state={main} />
        </div>
      )}
    </div>
  );
}
