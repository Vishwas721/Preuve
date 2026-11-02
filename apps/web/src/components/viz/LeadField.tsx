"use client";

// Lead field: every prospect as a dot on one 0–100 axis.
// Form: dot plot (single series → one sequential hue, no legend; title names it).
// Marks ≥8px with a 2px surface ring so overlapping dots stay separable; per-dot
// tooltip; recessive axis; sr-only list as the table alternative.

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { ProspectSummary } from "@/lib/api";
import { cn } from "@/lib/utils";

export function LeadField({
  prospects,
  onPick,
  className,
}: {
  prospects: ProspectSummary[];
  onPick?: (id: string) => void;
  className?: string;
}) {
  const scored = prospects.filter((p) => p.score !== null);
  // stack dots that share a score so none hide behind another
  const lanes = new Map<number, number>();
  const dots = scored.map((p) => {
    const lane = lanes.get(p.score!) ?? 0;
    lanes.set(p.score!, lane + 1);
    return { p, lane };
  });
  const rows = Math.max(1, ...[...lanes.values()]);

  return (
    <figure className={cn("w-full", className)}>
      <figcaption className="sr-only">
        Lead scores:{" "}
        {scored.map((p) => `${p.name} ${p.score}`).join(", ")}
      </figcaption>
      <div className="relative" style={{ height: 18 + rows * 12 }} aria-hidden>
        {[0, 25, 50, 75, 100].map((t) => (
          <span
            key={t}
            className="absolute bottom-0 h-full border-l border-dashed border-rule"
            style={{ left: `${t}%` }}
          />
        ))}
        {dots.map(({ p, lane }) => (
          <Tooltip key={p.id}>
            <TooltipTrigger asChild>
              <button
                type="button"
                tabIndex={-1}
                onClick={() => onPick?.(p.id)}
                className="absolute size-[10px] -translate-x-1/2 rounded-full bg-viz-seq ring-2 ring-paper transition-transform hover:scale-150"
                style={{ left: `${p.score}%`, bottom: 4 + lane * 12 }}
              />
            </TooltipTrigger>
            <TooltipContent>
              {p.name} · <span className="font-mono">{p.score}</span>
            </TooltipContent>
          </Tooltip>
        ))}
      </div>
      <div className="mt-1 flex justify-between font-mono text-[10px] text-muted-foreground" aria-hidden>
        {[0, 25, 50, 75, 100].map((t) => (
          <span key={t}>{t}</span>
        ))}
      </div>
    </figure>
  );
}
