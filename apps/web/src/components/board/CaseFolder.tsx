"use client";

import { motion } from "motion/react";
import Link from "next/link";

import { EvidenceBalance } from "@/components/viz/EvidenceBalance";
import type { PortfolioItem } from "@/lib/api";
import { plural, relativeTime } from "@/lib/format";
import { STATE_LABELS } from "@/lib/states";
import { cn } from "@/lib/utils";

function Ledger({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="min-w-0">
      <div className="font-mono text-lg leading-none tabular-nums">{value}</div>
      <div className="eyebrow mt-1 !text-[9px]">{label}</div>
    </div>
  );
}

export function CaseFolder({ item, index }: { item: PortfolioItem; index: number }) {
  const ev = item.evidence;
  const exhibits = ev.supports + ev.contradicts + ev.neutral;
  const questions = item.unknowns_open + item.unknowns_answered;

  return (
    <motion.li
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index, 8) * 0.05, duration: 0.35, ease: "easeOut" }}
      className="list-none"
    >
      <Link
        href={`/ideas/${item.id}`}
        className="group block focus-visible:outline-none"
        aria-label={`Open case: ${item.title}`}
      >
        {/* index tab */}
        <div className="flex items-end">
          <div
            className={cn(
              "relative z-10 -mb-px flex items-center gap-2 rounded-t-md border border-b-0 bg-paper px-3 pt-1.5 pb-1",
              "transition-transform duration-300 group-hover:-translate-y-0.5",
            )}
          >
            <span className="font-mono text-[10px] tracking-[0.14em] text-muted-foreground">
              CASE {String(index + 1).padStart(3, "0")}
            </span>
            <span aria-hidden className="h-3 w-px bg-border" />
            <span className="font-mono text-[10px] uppercase tracking-[0.14em]">
              {STATE_LABELS[item.state]}
            </span>
            {item.busy && (
              <span className="relative ml-0.5 flex size-1.5" aria-label="Work in progress">
                <span className="absolute inline-flex size-full animate-ping rounded-full bg-viz-seq opacity-60" />
                <span className="relative inline-flex size-1.5 rounded-full bg-viz-seq" />
              </span>
            )}
          </div>
        </div>

        {/* folder body */}
        <article
          className={cn(
            "sheet relative flex h-full flex-col gap-4 rounded-tl-none p-5 transition-all duration-300",
            "group-hover:-translate-y-0.5 group-hover:shadow-lg group-focus-visible:ring-2 group-focus-visible:ring-ring",
          )}
        >
          <div>
            <p className="eyebrow">{item.target_market}</p>
            <h3 className="mt-1 font-display text-[1.65rem] leading-[1.1] decoration-1 underline-offset-4 group-hover:underline">
              {item.title}
            </h3>
          </div>

          <p className="line-clamp-3 min-h-[3.75rem] font-display text-[1.02rem] italic leading-snug text-ink-soft">
            {item.problem ?? "Not analyzed yet — the hypothesis appears here once the case is opened."}
          </p>

          <div>
            <div className="mb-1.5 flex items-baseline justify-between">
              <span className="eyebrow">Evidence balance</span>
              <span className="font-mono text-[11px] text-muted-foreground">
                {ev.verified} verified{ev.unverifiable ? ` · ${ev.unverifiable} unverifiable` : ""}
              </span>
            </div>
            <EvidenceBalance
              supports={ev.supports}
              contradicts={ev.contradicts}
              neutral={ev.neutral}
              size="sm"
              legend={false}
            />
          </div>

          <div className="grid grid-cols-4 gap-3 border-t rule pt-4">
            <Ledger label="Exhibits" value={exhibits} />
            <Ledger label="Alternatives" value={item.competitors} />
            <Ledger label="Prospects" value={item.prospects} />
            <Ledger label="Top score" value={item.top_score ?? "—"} />
          </div>

          <div className="mt-auto flex items-center justify-between gap-3 text-xs text-muted-foreground">
            <span>
              {questions === 0
                ? "No open questions yet"
                : `${item.unknowns_answered}/${plural(questions, "question")} answered`}
            </span>
            <span className="font-mono">{relativeTime(item.last_activity)}</span>
          </div>
        </article>
      </Link>
    </motion.li>
  );
}
