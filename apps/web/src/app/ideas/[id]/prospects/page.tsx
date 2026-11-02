"use client";

import { ChevronRight, RefreshCw, Search } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { toast } from "sonner";

import { useDossier } from "@/components/dossier/DossierProvider";
import { EmptyState, SectionHeading, SheetSkeleton } from "@/components/dossier/layout";
import { ProspectSheet } from "@/components/prospects/ProspectSheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { LeadField } from "@/components/viz/LeadField";
import { api, type ProspectStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

const STATUS: Record<ProspectStatus, string> = { new: "New", shortlisted: "Shortlisted", excluded: "Excluded" };

export default function ProspectExplorer() {
  const { id, prospects, refresh, analysis } = useDossier();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<"all" | ProspectStatus>("all");
  const [minScore, setMinScore] = useState(0);
  const [withContact, setWithContact] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);

  if (!prospects) return <SheetSkeleton lines={8} />;

  const primary = analysis?.icps.find((i) => i.is_primary);
  const visible = prospects.filter(
    (p) =>
      (!q || `${p.name} ${p.domain} ${p.location ?? ""} ${p.top_contact_role ?? ""}`.toLowerCase().includes(q.toLowerCase())) &&
      (status === "all" || p.status === status) &&
      (p.score ?? 0) >= minScore &&
      (!withContact || p.contacts > 0),
  );
  const count = (s: ProspectStatus) => prospects.filter((p) => p.status === s).length;

  return (
    <div className="space-y-6">
      <SectionHeading
        title="Prospects"
        kicker={
          primary
            ? `Companies matched to “${primary.name}”, ranked by an explainable lead score.`
            : "Companies matched to the primary profile, ranked by an explainable lead score."
        }
      >
        <Button
          variant="outline"
          size="sm"
          onClick={() =>
            api.rescoreProspects(id).then(
              (r) => {
                toast(`Rescored ${r.rescored} companies`);
                return refresh();
              },
              (e: Error) => toast.error(e.message),
            )
          }
        >
          <RefreshCw /> Rescore
        </Button>
      </SectionHeading>

      {prospects.length === 0 ? (
        <EmptyState title="No prospects yet.">
          Run <code className="rounded bg-muted px-1 font-mono text-xs">/research-idea {id}</code> (method v3) to find
          companies that match the primary profile.
        </EmptyState>
      ) : (
        <>
          <div className="sheet p-5">
            <div className="mb-3 flex items-baseline justify-between">
              <p className="eyebrow">Lead field · {prospects.length} companies</p>
              <p className="text-xs text-muted-foreground">click a dot to open</p>
            </div>
            <LeadField prospects={prospects} onPick={setOpenId} />
          </div>

          <div className="sheet flex flex-wrap items-center gap-x-5 gap-y-3 p-3">
            <div className="relative min-w-48 flex-1">
              <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                aria-label="Search prospects"
                placeholder="Company, city, role…"
                className="pl-8"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
            </div>
            <ToggleGroup
              type="single"
              variant="outline"
              size="sm"
              value={status}
              onValueChange={(v) => setStatus((v || "all") as typeof status)}
              aria-label="Status"
            >
              <ToggleGroupItem value="all">All</ToggleGroupItem>
              {(Object.keys(STATUS) as ProspectStatus[]).map((s) => (
                <ToggleGroupItem key={s} value={s}>
                  {STATUS[s]} {count(s)}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
            <div className="flex w-48 items-center gap-3">
              <Label htmlFor="min-score" className="shrink-0 text-xs text-muted-foreground">
                Min <span className="font-mono text-foreground">{minScore}</span>
              </Label>
              <Slider id="min-score" aria-label="Minimum score" min={0} max={100} step={5} value={[minScore]} onValueChange={([v]) => setMinScore(v)} />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={withContact} onChange={(e) => setWithContact(e.target.checked)} className="accent-foreground" />
              Has a contact
            </label>
            <span className="ml-auto font-mono text-xs text-muted-foreground" aria-live="polite">
              {visible.length} of {prospects.length}
            </span>
          </div>

          {visible.length === 0 ? (
            <EmptyState title="No prospects match.">Loosen the filters.</EmptyState>
          ) : (
            <ol className="sheet divide-y divide-border overflow-hidden">
              {visible.map((p, i) => (
                <motion.li
                  key={p.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: Math.min(i, 15) * 0.02 }}
                >
                  <button
                    onClick={() => setOpenId(p.id)}
                    className={cn(
                      "grid w-full grid-cols-[2.5rem_4.5rem_minmax(0,1fr)_auto] items-center gap-4 px-4 py-3.5 text-left transition-colors hover:bg-accent/50 focus-visible:bg-accent focus-visible:outline-none sm:grid-cols-[2.5rem_4.5rem_minmax(0,1fr)_12rem_8rem_auto]",
                      p.status === "excluded" && "opacity-55",
                    )}
                    aria-label={`${p.name}, score ${p.score ?? "none"}`}
                  >
                    <span className="font-mono text-xs text-muted-foreground">{String(i + 1).padStart(2, "0")}</span>
                    <span>
                      <span className="block font-display text-3xl leading-none tabular-nums">{p.score ?? "—"}</span>
                      <span className="mt-1 block h-1 w-full rounded-full bg-viz-track" aria-hidden>
                        <span className="block h-full rounded-full bg-viz-seq" style={{ width: `${p.score ?? 0}%` }} />
                      </span>
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate font-display text-xl leading-tight">{p.name}</span>
                      <span className="block truncate font-mono text-[11px] text-muted-foreground">
                        {p.domain}
                        {p.location ? ` · ${p.location}` : ""}
                      </span>
                    </span>
                    <span className="hidden truncate text-sm text-ink-soft sm:block">
                      {p.top_contact_role ?? <span className="text-muted-foreground">no contact</span>}
                      {p.contacts > 1 ? ` +${p.contacts - 1}` : ""}
                    </span>
                    <span className="hidden sm:block">
                      <span
                        className={cn(
                          "rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider",
                          p.status === "shortlisted" && "border-foreground bg-foreground text-background",
                        )}
                      >
                        {STATUS[p.status]}
                      </span>
                    </span>
                    <ChevronRight className="size-4 text-muted-foreground" aria-hidden />
                  </button>
                </motion.li>
              ))}
            </ol>
          )}
        </>
      )}
      <ProspectSheet companyId={openId} onOpenChange={(o) => !o && setOpenId(null)} onChanged={() => undefined} />
    </div>
  );
}
