"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { streamDecision, streamResearch } from "@/lib/api";
import { applyEvent, initialResearchState, newRunState } from "@/lib/research";
import { loadSession, saveSession } from "@/lib/storage";
import type { DecisionAction, Provider, ResearchState } from "@/lib/types";

export interface RunParams {
  query: string;
  provider: Provider;
  model: string;
  apiKey: string;
  maxSubquestions: number;
  search: boolean;
  reviewPlan: boolean;
}

export interface DecisionInput {
  action: DecisionAction;
  editedContent?: string;
  note?: string;
  apiKey: string; // read from the key manager at click time; never kept in state
}

export interface CompareTarget {
  provider: Provider;
  model: string;
  apiKey: string;
}

interface ResearchContextValue {
  main: ResearchState;
  runMain: (p: RunParams) => void;
  stopMain: () => void;
  resetMain: () => void;
  decideMain: (d: DecisionInput) => void;

  compareQuery: string;
  compareColumns: ResearchState[];
  runCompare: (
    query: string,
    targets: CompareTarget[],
    opts: { maxSubquestions: number; search: boolean },
  ) => void;
  stopCompare: () => void;
  resetCompare: () => void;
}

const MAIN_KEY = "drs.main.v1";
const COMPARE_KEY = "drs.compare.v1";

const ResearchContext = createContext<ResearchContextValue | null>(null);

export function ResearchProvider({ children }: { children: ReactNode }) {
  const [main, setMain] = useState<ResearchState>(() => initialResearchState());
  const [compareQuery, setCompareQuery] = useState("");
  const [compareColumns, setCompareColumns] = useState<ResearchState[]>([]);
  const [hydrated, setHydrated] = useState(false);

  const mainAbort = useRef<AbortController | null>(null);
  const compareAborts = useRef<AbortController[]>([]);

  // Hydrate persisted state (coerce any "running" flag off -- the stream is gone).
  useEffect(() => {
    const m = loadSession<ResearchState | null>(MAIN_KEY, null);
    if (m) setMain({ ...m, running: false });
    const c = loadSession<{ query: string; columns: ResearchState[] } | null>(COMPARE_KEY, null);
    if (c) {
      setCompareQuery(c.query ?? "");
      setCompareColumns((c.columns ?? []).map((col) => ({ ...col, running: false })));
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) saveSession(MAIN_KEY, main);
  }, [main, hydrated]);

  useEffect(() => {
    if (hydrated) saveSession(COMPARE_KEY, { query: compareQuery, columns: compareColumns });
  }, [compareQuery, compareColumns, hydrated]);

  const runMain = useCallback((p: RunParams) => {
    mainAbort.current?.abort();
    const ctrl = new AbortController();
    mainAbort.current = ctrl;
    setMain(newRunState(p.query, p.provider, p.model));
    void streamResearch(
      {
        query: p.query,
        provider: p.provider,
        model: p.model,
        apiKey: p.apiKey,
        maxSubquestions: p.maxSubquestions,
        search: p.search,
        reviewPlan: p.reviewPlan,
        signal: ctrl.signal,
      },
      (e) => setMain((prev) => applyEvent(prev, e)),
    );
  }, []);

  const mainRef = useRef(main);
  mainRef.current = main;

  const decideMain = useCallback((d: DecisionInput) => {
    const cur = mainRef.current;
    if (!cur.approval || cur.running) return;
    mainAbort.current?.abort();
    const ctrl = new AbortController();
    mainAbort.current = ctrl;
    setMain((prev) => ({ ...prev, running: true, error: null, statusMessage: "Sending your decision..." }));
    void streamDecision(
      {
        runId: cur.approval.runId,
        stage: cur.approval.stage,
        action: d.action,
        editedContent: d.editedContent,
        note: d.note,
        provider: cur.provider,
        model: cur.model,
        apiKey: d.apiKey,
        signal: ctrl.signal,
      },
      (e) => setMain((prev) => applyEvent(prev, e)),
    );
  }, []);

  const stopMain = useCallback(() => {
    mainAbort.current?.abort();
    setMain((prev) =>
      prev.running ? { ...prev, running: false, statusMessage: "Stopped." } : prev,
    );
  }, []);

  const resetMain = useCallback(() => {
    mainAbort.current?.abort();
    setMain(initialResearchState());
  }, []);

  const runCompare = useCallback(
    (query: string, targets: CompareTarget[], opts: { maxSubquestions: number; search: boolean }) => {
      compareAborts.current.forEach((c) => c.abort());
      compareAborts.current = targets.map(() => new AbortController());
      setCompareQuery(query);
      setCompareColumns(targets.map((t) => newRunState(query, t.provider, t.model)));
      targets.forEach((t, i) => {
        void streamResearch(
          {
            query,
            provider: t.provider,
            model: t.model,
            apiKey: t.apiKey,
            maxSubquestions: opts.maxSubquestions,
            search: opts.search,
            signal: compareAborts.current[i].signal,
          },
          (e) =>
            setCompareColumns((prev) => {
              const copy = [...prev];
              if (copy[i]) copy[i] = applyEvent(copy[i], e);
              return copy;
            }),
        );
      });
    },
    [],
  );

  const stopCompare = useCallback(() => {
    compareAborts.current.forEach((c) => c.abort());
    setCompareColumns((prev) => prev.map((c) => (c.running ? { ...c, running: false } : c)));
  }, []);

  const resetCompare = useCallback(() => {
    compareAborts.current.forEach((c) => c.abort());
    setCompareQuery("");
    setCompareColumns([]);
  }, []);

  const value: ResearchContextValue = {
    main,
    runMain,
    stopMain,
    resetMain,
    decideMain,
    compareQuery,
    compareColumns,
    runCompare,
    stopCompare,
    resetCompare,
  };

  return <ResearchContext.Provider value={value}>{children}</ResearchContext.Provider>;
}

export function useResearch(): ResearchContextValue {
  const ctx = useContext(ResearchContext);
  if (!ctx) throw new Error("useResearch must be used within <ResearchProvider>");
  return ctx;
}
