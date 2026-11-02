"use client";

// Evidence balance: how the verified evidence leans (PRD §26 "strong vs weak evidence").
// Form: one 100% stacked bar — polarity, so the diverging pair (contradicts ↔ supports)
// with a neutral gray midpoint. Marks: 2px surface gaps between segments, rounded
// data-ends, hover tooltip per segment, legend with counts, and an sr-only summary.

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const SEGMENTS = [
  { key: "contradicts", label: "Argues against", color: "bg-viz-contradicts" },
  { key: "neutral", label: "Context", color: "bg-viz-neutral" },
  { key: "supports", label: "Supports", color: "bg-viz-supports" },
] as const;

export function EvidenceBalance({
  supports,
  contradicts,
  neutral,
  size = "md",
  legend = true,
  className,
}: {
  supports: number;
  contradicts: number;
  neutral: number;
  size?: "sm" | "md" | "lg";
  legend?: boolean;
  className?: string;
}) {
  const counts = { supports, contradicts, neutral };
  const total = supports + contradicts + neutral;
  const height = size === "sm" ? "h-1.5" : size === "lg" ? "h-3.5" : "h-2.5";
  const summary =
    total === 0
      ? "No evidence yet."
      : `${supports} supporting, ${contradicts} contradicting, ${neutral} context out of ${total} evidence items.`;

  return (
    <figure className={cn("w-full", className)}>
      <figcaption className="sr-only">{summary}</figcaption>
      {total === 0 ? (
        <div className={cn("w-full rounded-full border border-dashed", height)} aria-hidden />
      ) : (
        <div className={cn("flex w-full gap-[2px]", height)} aria-hidden>
          {SEGMENTS.map((s) => {
            const n = counts[s.key];
            if (!n) return null;
            return (
              <Tooltip key={s.key}>
                <TooltipTrigger asChild>
                  <span
                    className={cn("h-full rounded-[4px] transition-[flex-grow] duration-500", s.color)}
                    style={{ flexGrow: n, flexBasis: 0, minWidth: 6 }}
                  />
                </TooltipTrigger>
                <TooltipContent>
                  <span className="font-mono">{n}</span> {s.label.toLowerCase()} ·{" "}
                  {Math.round((n / total) * 100)}%
                </TooltipContent>
              </Tooltip>
            );
          })}
        </div>
      )}
      {legend && (
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground" aria-hidden>
          {SEGMENTS.map((s) => (
            <span key={s.key} className="inline-flex items-center gap-1.5">
              <span className={cn("size-2 rounded-[2px]", s.color)} />
              {s.label}
              <span className="font-mono text-foreground">{counts[s.key]}</span>
            </span>
          ))}
        </div>
      )}
    </figure>
  );
}
