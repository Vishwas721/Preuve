"use client";

// Magnitude bars for score components and rubric ratings.
// Form: horizontal bar on a track (single series → single sequential hue, no legend;
// the label names it). Value text stays in ink, never the series colour.

import type { ReactNode } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export function ScoreBar({
  value,
  max,
  label,
  detail,
  className,
}: {
  value: number;
  max: number;
  label: ReactNode;
  detail?: ReactNode;
  className?: string;
}) {
  const pct = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;
  const bar = (
    <div className="h-2 w-full rounded-[4px] bg-viz-track" aria-hidden>
      {pct > 0 && (
        <div
          className="h-full rounded-[4px] bg-viz-seq transition-[width] duration-700 ease-out"
          style={{ width: `max(6px, ${pct * 100}%)` }}
        />
      )}
    </div>
  );
  return (
    <div className={cn("grid grid-cols-[minmax(0,9rem)_1fr_3.5rem] items-center gap-3", className)}>
      <span className="truncate text-sm">{label}</span>
      {detail ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="py-1.5">{bar}</div>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs">{detail}</TooltipContent>
        </Tooltip>
      ) : (
        bar
      )}
      <span className="text-right font-mono text-xs tabular-nums">
        {Number.isInteger(value) ? value : value.toFixed(1)}
        <span className="text-muted-foreground">/{max}</span>
      </span>
    </div>
  );
}

/** A 0–100 score as a hero figure with a thin meter underneath. */
export function ScoreFigure({ score, label = "score", className }: { score: number | null; label?: string; className?: string }) {
  return (
    <div className={cn("w-16 text-right", className)}>
      <div className="font-display text-3xl leading-none tabular-nums">{score ?? "—"}</div>
      <div className="mt-1.5 h-1 w-full rounded-full bg-viz-track" aria-hidden>
        {score !== null && score > 0 && (
          <div className="h-full rounded-full bg-viz-seq" style={{ width: `${Math.min(100, score)}%` }} />
        )}
      </div>
      <div className="eyebrow mt-1 !text-[9px]">{label}</div>
    </div>
  );
}
