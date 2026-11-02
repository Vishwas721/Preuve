"use client";

import { RotateCcw, Search } from "lucide-react";
import { AnimatePresence } from "motion/react";
import { useEffect, useMemo, useState } from "react";

import { useDossier } from "@/components/dossier/DossierProvider";
import { EmptyState, SectionHeading, SheetSkeleton } from "@/components/dossier/layout";
import { ExhibitCard, SOURCE_LABELS } from "@/components/evidence/ExhibitCard";
import { ExhibitSheet } from "@/components/evidence/ExhibitSheet";
import { ResearchLog } from "@/components/evidence/ResearchLog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Evidence } from "@/lib/api";
import { domain } from "@/lib/format";

type Filters = {
  q: string;
  stance: "all" | Evidence["stance"];
  kind: "all" | Evidence["kind"];
  verification: "all" | Evidence["verification"];
  source: "all" | Evidence["source_type"];
  question: "all" | string;
};
const NONE: Filters = { q: "", stance: "all", kind: "all", verification: "all", source: "all", question: "all" };

export default function EvidenceExplorer() {
  const { id, research, analysis, exhibit } = useDossier();
  const [f, setF] = useState<Filters>(NONE);
  const [openId, setOpenId] = useState<string | null>(null);
  const [highlight, setHighlight] = useState<string | null>(null);

  const all = useMemo(() => research?.evidence ?? [], [research]);
  const visible = all.filter((e) => {
    const q = f.q.trim().toLowerCase();
    return (
      (!q || `${e.quote} ${e.statement} ${domain(e.url)} ${e.company_name ?? ""}`.toLowerCase().includes(q)) &&
      (f.stance === "all" || e.stance === f.stance) &&
      (f.kind === "all" || e.kind === f.kind) &&
      (f.verification === "all" || e.verification === f.verification) &&
      (f.source === "all" || e.source_type === f.source) &&
      (f.question === "all" || e.unknown_ids.includes(f.question))
    );
  });
  const count = (pred: (e: Evidence) => boolean) => all.filter(pred).length;
  const sources = [...new Set(all.map((e) => e.source_type))];

  // Deep links from citations: /evidence#ev-<id> scrolls to and highlights the exhibit.
  useEffect(() => {
    if (!all.length) return;
    const target = window.location.hash.replace("#ev-", "");
    if (!target) return;
    const el = document.getElementById(`ev-${target}`);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
    const on = setTimeout(() => setHighlight(target), 0);
    const off = setTimeout(() => setHighlight(null), 2600);
    return () => {
      clearTimeout(on);
      clearTimeout(off);
    };
  }, [all.length]);

  if (!research) return <SheetSkeleton lines={6} />;
  const filtered = JSON.stringify(f) !== JSON.stringify(NONE);
  const open = all.find((e) => e.id === openId) ?? null;

  return (
    <div className="space-y-12">
      <section className="space-y-5" aria-labelledby="exhibits-title">
        <SectionHeading
          title={<span id="exhibits-title">Exhibits</span>}
          kicker="Every quote here was found on its source page by Preuve itself — not just reported by the researcher."
        />

        {all.length === 0 ? (
          <EmptyState title="No evidence found.">
            Run <code className="rounded bg-muted px-1 font-mono text-xs">/research-idea {id}</code> in Claude Code.
            Preuve verifies every quote before it enters the case.
          </EmptyState>
        ) : (
          <>
            {/* filter bar */}
            <div className="sheet space-y-3 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative min-w-52 flex-1">
                  <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    aria-label="Search exhibits"
                    placeholder="Search quotes, sources, companies…"
                    className="pl-8"
                    value={f.q}
                    onChange={(e) => setF({ ...f, q: e.target.value })}
                  />
                </div>
                <ToggleGroup
                  type="single"
                  variant="outline"
                  size="sm"
                  value={f.stance}
                  onValueChange={(v) => setF({ ...f, stance: (v || "all") as Filters["stance"] })}
                  aria-label="Stance"
                >
                  <ToggleGroupItem value="all">All {all.length}</ToggleGroupItem>
                  <ToggleGroupItem value="supports">
                    <span className="size-2 rounded-[2px] bg-viz-supports" aria-hidden /> Supports {count((e) => e.stance === "supports")}
                  </ToggleGroupItem>
                  <ToggleGroupItem value="contradicts">
                    <span className="size-2 rounded-[2px] bg-viz-contradicts" aria-hidden /> Against {count((e) => e.stance === "contradicts")}
                  </ToggleGroupItem>
                  <ToggleGroupItem value="neutral">
                    <span className="size-2 rounded-[2px] bg-viz-neutral" aria-hidden /> Context {count((e) => e.stance === "neutral")}
                  </ToggleGroupItem>
                </ToggleGroup>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Select value={f.kind} onValueChange={(v) => setF({ ...f, kind: v as Filters["kind"] })}>
                  <SelectTrigger size="sm" aria-label="Kind" className="w-36">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Any kind</SelectItem>
                    <SelectItem value="fact">Facts {count((e) => e.kind === "fact")}</SelectItem>
                    <SelectItem value="inference">Inferences {count((e) => e.kind === "inference")}</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={f.verification} onValueChange={(v) => setF({ ...f, verification: v as Filters["verification"] })}>
                  <SelectTrigger size="sm" aria-label="Verification" className="w-40">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Any verification</SelectItem>
                    <SelectItem value="verified">Verified {count((e) => e.verification === "verified")}</SelectItem>
                    <SelectItem value="unverifiable">Unverifiable {count((e) => e.verification === "unverifiable")}</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={f.source} onValueChange={(v) => setF({ ...f, source: v as Filters["source"] })}>
                  <SelectTrigger size="sm" aria-label="Source type" className="w-40">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Any source</SelectItem>
                    {sources.map((s) => (
                      <SelectItem key={s} value={s}>
                        {SOURCE_LABELS[s]} {count((e) => e.source_type === s)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select value={f.question} onValueChange={(v) => setF({ ...f, question: v })}>
                  <SelectTrigger size="sm" aria-label="Question" className="w-56">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="max-w-md">
                    <SelectItem value="all">Any question</SelectItem>
                    {(analysis?.unknowns ?? []).map((u, i) => (
                      <SelectItem key={u.id} value={u.id}>
                        Q-{String(i + 1).padStart(2, "0")} · {u.question.slice(0, 60)}
                        {u.question.length > 60 ? "…" : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <span className="ml-auto font-mono text-xs text-muted-foreground" aria-live="polite">
                  {visible.length} of {all.length}
                </span>
                {filtered && (
                  <Button variant="ghost" size="sm" onClick={() => setF(NONE)}>
                    <RotateCcw /> Reset
                  </Button>
                )}
              </div>
            </div>

            {visible.length === 0 ? (
              <EmptyState title="No evidence found.">Nothing matches these filters.</EmptyState>
            ) : (
              <ul className="grid gap-4 xl:grid-cols-2">
                <AnimatePresence initial={false}>
                  {visible.map((ev, i) => (
                    <ExhibitCard
                      key={ev.id}
                      ev={ev}
                      index={i}
                      label={exhibit(ev.id)}
                      highlighted={highlight === ev.id}
                      onOpen={() => setOpenId(ev.id)}
                    />
                  ))}
                </AnimatePresence>
              </ul>
            )}
          </>
        )}
      </section>

      <ResearchLog />
      <ExhibitSheet ev={open} label={open ? exhibit(open.id) : ""} onOpenChange={(o) => !o && setOpenId(null)} />
    </div>
  );
}
