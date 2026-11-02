"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  api,
  type Evidence,
  type Idea,
  type IdeaAnalysis,
  type IdeaResearch,
  type ProspectSummary,
} from "@/lib/api";

const POLL_MS = 2500;

interface Dossier {
  id: string;
  idea: Idea | null;
  analysis: IdeaAnalysis | null;
  research: IdeaResearch | null;
  prospects: ProspectSummary[] | null;
  error: string | null;
  /** Analysis run or research import in progress. */
  busy: boolean;
  refresh: () => Promise<void>;
  startAnalysis: (kind: "full" | "icps") => Promise<void>;
  /** Exhibit label per evidence id ("EX-04"), by order in the case. */
  exhibit: (evidenceId: string) => string;
  evidenceById: Record<string, Evidence>;
}

const Ctx = createContext<Dossier | null>(null);

export function useDossier(): Dossier {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useDossier must be used inside <DossierProvider>");
  return ctx;
}

export function DossierProvider({ id, children }: { id: string; children: ReactNode }) {
  const [idea, setIdea] = useState<Idea | null>(null);
  const [analysis, setAnalysis] = useState<IdeaAnalysis | null>(null);
  const [research, setResearch] = useState<IdeaResearch | null>(null);
  const [prospects, setProspects] = useState<ProspectSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(
    () =>
      Promise.all([api.getIdea(id), api.getAnalysis(id), api.getResearch(id), api.listProspects(id)]).then(
        ([i, a, r, p]) => {
          setIdea(i);
          setAnalysis(a);
          setResearch(r);
          setProspects(p);
          setError(null);
        },
        (err: Error) => setError(err.message),
      ),
    [id],
  );

  useEffect(() => {
    refresh();
  }, [refresh]);

  const run = analysis?.latest_run;
  const busy =
    run?.status === "queued" ||
    run?.status === "running" ||
    !!research?.imports.some((i) => i.status === "queued" || i.status === "verifying");

  useEffect(() => {
    if (!busy) return;
    const t = setInterval(refresh, POLL_MS);
    return () => clearInterval(t);
  }, [busy, refresh]);

  const startAnalysis = useCallback(
    async (kind: "full" | "icps") => {
      await (kind === "full" ? api.analyze(id) : api.regenerateIcps(id));
      await refresh();
    },
    [id, refresh],
  );

  const { exhibit, evidenceById } = useMemo(() => {
    const order = new Map((research?.evidence ?? []).map((e, i) => [e.id, i]));
    const byId = Object.fromEntries((research?.evidence ?? []).map((e) => [e.id, e]));
    return {
      exhibit: (eid: string) => {
        const i = order.get(eid);
        return i === undefined ? "EX-??" : `EX-${String(i + 1).padStart(2, "0")}`;
      },
      evidenceById: byId,
    };
  }, [research]);

  const value: Dossier = {
    id,
    idea,
    analysis,
    research,
    prospects,
    error,
    busy,
    refresh,
    startAnalysis,
    exhibit,
    evidenceById,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
