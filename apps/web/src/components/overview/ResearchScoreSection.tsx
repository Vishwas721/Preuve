"use client";

import { useEffect, useState } from "react";

import { useDossier } from "@/components/dossier/DossierProvider";
import { SectionHeading } from "@/components/dossier/layout";
import { Skeleton } from "@/components/ui/skeleton";
import { ScoreBar, ScoreFigure } from "@/components/viz/ScoreBar";
import { api, type ResearchBand, type ResearchScore } from "@/lib/api";

export const BAND_LABEL: Record<ResearchBand, string> = {
  strong: "Strong desk case",
  promising: "Promising",
  weak: "Weak on paper",
};

/** Phase 6: how well verified web research supports the idea, before any customer contact. */
export function ResearchScoreSection() {
  const { id, research, prospects } = useDossier();
  const [score, setScore] = useState<ResearchScore | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Recompute whenever the dossier's research or prospects change; the score is computed live.
  useEffect(() => {
    let alive = true;
    api.getResearchScore(id).then(
      (s) => alive && (setScore(s), setError(null)),
      (e: Error) => alive && setError(e.message),
    );
    return () => {
      alive = false;
    };
  }, [id, research, prospects]);

  return (
    <section aria-labelledby="research-score-title" className="space-y-6">
      <SectionHeading
        index="04"
        title={<span id="research-score-title">Research score</span>}
        kicker="Ranks ideas on verified web evidence alone, so you know which one to take to customers first. It doesn't validate the idea; customers do."
      >
        {score && <ScoreFigure score={score.total} label={BAND_LABEL[score.band]} className="w-28" />}
      </SectionHeading>

      {error && <p className="text-sm text-destructive">Couldn&apos;t load the research score: {error}</p>}
      {!error && !score && <Skeleton className="h-48" />}

      {score && (
        <div className="grid gap-8 lg:grid-cols-[1.2fr_1fr]">
          <div className="space-y-3">
            {score.dimensions.map((d) => (
              <ScoreBar key={d.key} label={d.label} value={d.points} max={d.max} detail={d.reason} />
            ))}
          </div>
          <div>
            <p className="eyebrow mb-3">What would raise it</p>
            {score.dimensions.some((d) => d.gaps.length) ? (
              <ul className="space-y-2 text-sm">
                {score.dimensions.flatMap((d) =>
                  d.gaps.map((g) => (
                    <li key={`${d.key}-${g}`} className="flex gap-2">
                      <span className="mt-0.5 shrink-0 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                        {d.label}
                      </span>
                      <span>{g}</span>
                    </li>
                  )),
                )}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">Nothing more to gain from desk research. Contact customers.</p>
            )}
            <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
              Rules v{score.version} · verified, medium/high-relevance sources only · one count per domain · first-hand sources weigh most · direct competitors reduce open space
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
