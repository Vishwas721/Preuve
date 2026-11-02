"use client";

import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { motion } from "motion/react";

import { KindMark, VerificationStamp } from "@/components/dossier/marks";
import type { Evidence, SourceType, Stance } from "@/lib/api";
import { domain } from "@/lib/format";
import { cn } from "@/lib/utils";

export const SOURCE_LABELS: Record<SourceType, string> = {
  job_posting: "Job posting",
  forum: "Forum",
  review: "Review",
  news: "News",
  industry_publication: "Publication",
  company_site: "Company site",
  report: "Report",
  directory: "Directory",
  other: "Other",
};

export const STANCE = {
  supports: { label: "Supports", icon: ArrowUpRight, rule: "bg-viz-supports" },
  contradicts: { label: "Argues against", icon: ArrowDownRight, rule: "bg-viz-contradicts" },
  neutral: { label: "Context", icon: Minus, rule: "bg-viz-neutral" },
} satisfies Record<Stance, { label: string; icon: unknown; rule: string }>;

export function RelevancePips({ relevance }: { relevance: Evidence["relevance"] }) {
  const n = relevance === "high" ? 3 : relevance === "medium" ? 2 : 1;
  return (
    <span className="inline-flex items-center gap-1" title={`${relevance} relevance`}>
      <span className="sr-only">{relevance} relevance</span>
      {[0, 1, 2].map((i) => (
        <span key={i} aria-hidden className={cn("size-1.5 rounded-full", i < n ? "bg-foreground/70" : "bg-viz-track")} />
      ))}
    </span>
  );
}

export function ExhibitCard({
  ev,
  label,
  highlighted,
  onOpen,
  index,
}: {
  ev: Evidence;
  label: string;
  highlighted: boolean;
  onOpen: () => void;
  index: number;
}) {
  const stance = STANCE[ev.stance];
  const Icon = stance.icon;
  return (
    <motion.li
      id={`ev-${ev.id}`}
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index, 12) * 0.025 }}
      className="list-none scroll-mt-28"
    >
      <button
        onClick={onOpen}
        className={cn(
          "sheet group relative block w-full overflow-hidden p-5 pl-6 text-left transition-shadow hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          highlighted && "ring-2 ring-viz-seq",
        )}
        aria-label={`${label}: ${stance.label}. ${ev.statement}`}
      >
        <span aria-hidden className={cn("absolute inset-y-0 left-0 w-[5px]", stance.rule)} />
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-baseline gap-3">
            <span className="font-mono text-sm font-semibold tracking-wider">{label}</span>
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Icon className="size-3.5" aria-hidden /> {stance.label}
            </span>
          </div>
          <VerificationStamp verification={ev.verification} />
        </div>

        <blockquote className="mt-3 font-display text-[1.28rem] italic leading-snug">
          &ldquo;{ev.quote}&rdquo;
        </blockquote>
        <p className="mt-2 text-sm text-ink-soft">{ev.statement}</p>

        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t rule pt-3 text-xs text-muted-foreground">
          <KindMark kind={ev.kind} />
          <span className="eyebrow !text-[10px]">{SOURCE_LABELS[ev.source_type]}</span>
          <span className="font-mono">{domain(ev.url)}</span>
          {ev.company_name && <span>{ev.company_name}</span>}
          <span className="ml-auto">
            <RelevancePips relevance={ev.relevance} />
          </span>
        </div>
      </button>
    </motion.li>
  );
}
