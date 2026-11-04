"use client";

// The validation score (PRD §24): seven dimensions, each with its points, the rule's reason,
// the exhibits behind it and what would raise it. Numbers come from the stored snapshot only.

import { Cite } from "@/components/dossier/Cite";
import { ScoreBar } from "@/components/viz/ScoreBar";
import type { ValidationScore } from "@/lib/api";
import { cn } from "@/lib/utils";

const pct = (v: number | null) => (v === null ? "—" : `${Math.round(v * 100)}%`);

export function ScoreCard({ score }: { score: ValidationScore }) {
  const m = score.metrics;
  return (
    <div className="sheet space-y-6 p-5 sm:p-6">
      <div className="flex flex-wrap items-end gap-x-8 gap-y-4">
        <div>
          <p className="eyebrow">Validation score</p>
          <p className="mt-1 font-display text-6xl leading-none tabular-nums">
            {score.total}
            <span className="text-2xl text-muted-foreground">/100</span>
          </p>
        </div>
        <dl className="grid flex-1 grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-5">
          {[
            ["Validated conversations", String(m.validated_conversations)],
            ["Response rate", pct(m.response_rate)],
            ["Problem confirmed", pct(m.problem_confirmation_rate)],
            ["Interview conversion", pct(m.interview_conversion)],
            ["Commercial", pct(m.commercial_validation)],
          ].map(([label, value], i) => (
            <div key={label} className={cn(i === 0 && "col-span-2 sm:col-span-1")}>
              <dt className="eyebrow !text-[9px]">{label}</dt>
              <dd className="mt-1 font-display text-2xl leading-none tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
      </div>

      <ol className="space-y-5 border-t rule pt-5" aria-label="Score breakdown">
        {score.dimensions.map((d) => (
          <li key={d.key} className="space-y-1.5">
            <ScoreBar value={d.points} max={d.max} label={d.label} className="sm:grid-cols-[minmax(0,12rem)_1fr_3.5rem]" />
            <p className="text-sm leading-relaxed text-muted-foreground">
              {d.reason}
              {d.evidence_ids.slice(0, 8).map((eid) => (
                <Cite key={eid} id={eid} />
              ))}
              {d.evidence_ids.length > 8 && (
                <span className="font-mono text-[10px]"> +{d.evidence_ids.length - 8} more</span>
              )}
            </p>
            {d.points < d.max && d.gaps.length > 0 && (
              <p className="text-xs">
                <span className="eyebrow !text-[9px] mr-1.5">To raise it</span>
                {d.gaps.join(" ")}
              </p>
            )}
          </li>
        ))}
      </ol>
      <p className="font-mono text-[10px] text-muted-foreground">
        Computed by fixed rules from stored evidence (scoring v{score.scoring_version}) · inputs{" "}
        {score.inputs_hash.slice(0, 10)}
      </p>
    </div>
  );
}
