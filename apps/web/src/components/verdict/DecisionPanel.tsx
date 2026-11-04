"use client";

// The decision engine's output (PRD §26): a verdict that explains itself, with the evidence
// behind it, its weak spots, the biggest uncertainty and what to do next.

import { ArrowRight } from "lucide-react";

import { Cite } from "@/components/dossier/Cite";
import { Stamp } from "@/components/dossier/marks";
import type { DecisionPoint, Recommendation, ValidationScore } from "@/lib/api";
import { STATE_LABELS } from "@/lib/states";

export const RECOMMENDATION: Record<Recommendation, { label: string; tone: "good" | "warning" | "ink" }> = {
  build: { label: "Build", tone: "good" },
  iterate: { label: "Iterate", tone: "warning" },
  investigate: { label: "Investigate further", tone: "ink" },
  abandon: { label: "Abandon", tone: "warning" },
};

function Points({ title, points, empty }: { title: string; points: DecisionPoint[]; empty: string }) {
  return (
    <div>
      <p className="eyebrow mb-2">{title}</p>
      {points.length === 0 ? (
        <p className="text-sm text-muted-foreground">{empty}</p>
      ) : (
        <ul className="space-y-2">
          {points.map((p, i) => (
            <li key={i} className="text-sm leading-relaxed">
              {p.text}
              {p.evidence_ids.slice(0, 6).map((eid) => (
                <Cite key={eid} id={eid} />
              ))}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function DecisionPanel({ score }: { score: ValidationScore }) {
  const d = score.decision;
  const rec = RECOMMENDATION[score.recommendation];
  return (
    <div className="sheet space-y-6 p-5 sm:p-6">
      <div className="flex flex-wrap items-center gap-3">
        <Stamp tone={rec.tone}>{rec.label}</Stamp>
        <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
          State · {STATE_LABELS[score.state]}
        </span>
      </div>
      <div>
        <h3 className="font-display text-3xl leading-tight sm:text-4xl">{d.headline}</h3>
        <p className="mt-2 text-sm text-muted-foreground">{d.why}</p>
      </div>

      <div className="grid gap-6 border-t rule pt-5 md:grid-cols-2">
        <Points title="Strong evidence" points={d.strong} empty="No evidence found." />
        <Points title="Weak evidence" points={d.weak} empty="No weak spots recorded." />
      </div>

      <div className="border-t rule pt-5">
        <p className="eyebrow mb-2">Biggest uncertainty</p>
        <p className="text-sm leading-relaxed">{d.uncertainty}</p>
      </div>

      {d.next_actions.length > 0 && (
        <div className="border-t rule pt-5">
          <p className="eyebrow mb-2">Next actions</p>
          <ol className="space-y-2">
            {d.next_actions.map((a, i) => (
              <li key={i} className="grid grid-cols-[1.25rem_1fr] gap-2 text-sm leading-snug">
                <ArrowRight className="mt-0.5 size-3.5 text-muted-foreground" aria-hidden />
                <span>{a}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
