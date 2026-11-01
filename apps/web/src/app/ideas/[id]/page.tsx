"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { HypothesisPanel } from "@/components/analysis/HypothesisPanel";
import { IcpPanel } from "@/components/analysis/IcpPanel";
import { isActive, RunBanner } from "@/components/analysis/RunBanner";
import { UnknownsPanel } from "@/components/analysis/UnknownsPanel";
import { EvidencePanel } from "@/components/research/EvidencePanel";
import { btnPrimary, card } from "@/components/ui";
import { api, type Idea, type IdeaAnalysis, type IdeaResearch } from "@/lib/api";

const POLL_MS = 2500;

export default function IdeaPage() {
  const { id } = useParams<{ id: string }>();
  const [idea, setIdea] = useState<Idea | null>(null);
  const [analysis, setAnalysis] = useState<IdeaAnalysis | null>(null);
  const [research, setResearch] = useState<IdeaResearch | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [a, r] = await Promise.all([api.getAnalysis(id), api.getResearch(id)]);
      setAnalysis(a);
      setResearch(r);
    } catch (err) {
      setError((err as Error).message);
    }
  }, [id]);

  useEffect(() => {
    api.getIdea(id).then(setIdea, (err: Error) => setError(err.message));
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial data load
    refresh();
  }, [id, refresh]);

  const running = isActive(analysis?.latest_run ?? null);
  const verifying = !!research?.imports.some(
    (i) => i.status === "queued" || i.status === "verifying",
  );
  useEffect(() => {
    if (!running && !verifying) return;
    const timer = setInterval(refresh, POLL_MS);
    return () => clearInterval(timer);
  }, [running, verifying, refresh]);

  async function start(kind: "full" | "icps") {
    setStarting(true);
    setError(null);
    try {
      await (kind === "full" ? api.analyze(id) : api.regenerateIcps(id));
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setStarting(false);
    }
  }

  if (error && !idea) {
    return (
      <main className="mx-auto w-full max-w-4xl px-4 py-10">
        <Link href="/" className="text-sm opacity-70 hover:opacity-100">
          ← Ideas
        </Link>
        <p className="mt-4 text-sm text-red-600">{error}</p>
      </main>
    );
  }

  if (!idea || !analysis || !research) {
    return <main className="mx-auto w-full max-w-4xl px-4 py-10 text-sm opacity-70">Loading…</main>;
  }

  const hasHypothesis = analysis.hypothesis !== null;
  const run = analysis.latest_run;

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-4 py-10">
      <header className="flex flex-col gap-2">
        <Link href="/" className="text-sm opacity-70 hover:opacity-100">
          ← Ideas
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">{idea.title}</h1>
            <p className="text-sm opacity-70">{idea.target_market}</p>
          </div>
          <button
            className={btnPrimary}
            onClick={() => start("full")}
            disabled={running || starting}
          >
            {hasHypothesis ? "Re-analyze" : "Analyze idea"}
          </button>
        </div>
      </header>

      <section className={card}>
        <h2 className="text-xs font-medium opacity-60">Your idea</h2>
        <p className="mt-1 text-sm">{idea.description}</p>
        {idea.why_it_matters && (
          <p className="mt-2 text-sm opacity-80">
            <span className="opacity-60">Why it matters: </span>
            {idea.why_it_matters}
          </p>
        )}
      </section>

      <RunBanner run={run} onRetry={() => start(run?.kind ?? "full")} />
      {error && <p className="text-sm text-red-600">{error}</p>}

      {hasHypothesis && (
        <p className="text-sm opacity-70">
          Re-analyzing replaces only untouched AI suggestions. Anything you created or edited is
          kept, and the hypothesis keeps its full version history.
        </p>
      )}

      <HypothesisPanel ideaId={id} hypothesis={analysis.hypothesis} onChange={refresh} />
      <UnknownsPanel
        ideaId={id}
        unknowns={analysis.unknowns}
        findings={research.findings}
        evidenceRefs={Object.fromEntries(research.evidence.map((e) => [e.id, e.ref]))}
        onChange={refresh}
      />
      <EvidencePanel ideaId={id} research={research} onChange={refresh} />
      <IcpPanel
        ideaId={id}
        icps={analysis.icps}
        canRegenerate={hasHypothesis}
        busy={running || starting}
        onRegenerate={() => start("icps")}
        onChange={refresh}
      />
    </main>
  );
}
