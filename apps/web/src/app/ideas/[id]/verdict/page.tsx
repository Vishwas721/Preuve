"use client";

import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { useDossier } from "@/components/dossier/DossierProvider";
import { EmptyState, ErrorState, SectionHeading, SheetSkeleton } from "@/components/dossier/layout";
import { Button } from "@/components/ui/button";
import { DecisionPanel } from "@/components/verdict/DecisionPanel";
import { Experiments } from "@/components/verdict/Experiments";
import { Reports } from "@/components/verdict/Reports";
import { ScoreCard } from "@/components/verdict/ScoreCard";
import { api, type ScoreStatus } from "@/lib/api";
import { relativeTime } from "@/lib/format";

export default function VerdictPage() {
  const { id, refresh } = useDossier();
  const [status, setStatus] = useState<ScoreStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    () =>
      api.getScore(id).then(
        (s) => {
          setStatus(s);
          setError(null);
        },
        (e: Error) => setError(e.message),
      ),
    [id],
  );
  useEffect(() => {
    load();
  }, [load]);

  async function recompute() {
    setBusy(true);
    try {
      await api.recomputeScore(id);
      await Promise.all([load(), refresh()]); // the idea's state may have moved
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (error && !status) return <ErrorState message={error} onRetry={load} />;
  if (!status) return <SheetSkeleton lines={8} />;
  const score = status.score;

  return (
    <div className="space-y-12">
      <section className="space-y-5" aria-labelledby="verdict-title">
        <SectionHeading
          title={<span id="verdict-title">Verdict</span>}
          kicker={
            score
              ? `Scored ${relativeTime(score.created_at)} from stored evidence. No model touches these numbers.`
              : "Score the evidence collected so far. Fixed rules, no model."
          }
        >
          <Button size="sm" onClick={recompute} disabled={busy}>
            <RefreshCw className={busy ? "animate-spin" : undefined} /> {score ? "Recompute" : "Score the evidence"}
          </Button>
        </SectionHeading>

        {score && status.stale && (
          <div role="status" className="rounded-md border border-status-warning/40 bg-status-warning/5 px-4 py-2.5 text-sm">
            The evidence changed since this score was computed.{" "}
            <button className="underline underline-offset-4" onClick={recompute} disabled={busy}>
              Recompute
            </button>
          </div>
        )}

        {!score ? (
          <EmptyState title="Not scored yet.">
            The score combines research, replies, interviews and commitments by fixed rules, and tells you plainly
            when the evidence is too weak to build.
          </EmptyState>
        ) : (
          <div className="space-y-6">
            <DecisionPanel score={score} />
            <ScoreCard score={score} />
          </div>
        )}
      </section>

      <Experiments />
      <Reports onGenerated={() => Promise.all([load(), refresh()])} />
    </div>
  );
}
