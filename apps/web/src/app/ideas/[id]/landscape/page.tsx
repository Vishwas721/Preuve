"use client";

import { ExternalLink, MoreHorizontal, Plus } from "lucide-react";
import { motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { ClaimList, Cite } from "@/components/dossier/Cite";
import { useDossier } from "@/components/dossier/DossierProvider";
import { EmptyState, SectionHeading, SheetSkeleton } from "@/components/dossier/layout";
import { Provenance } from "@/components/dossier/marks";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { api, type Competitor, type CompetitorInput, type CompetitorKind } from "@/lib/api";
import { domain } from "@/lib/format";

const LANES: { key: CompetitorKind; label: string; hint: string }[] = [
  { key: "direct", label: "Direct", hint: "Same problem, same job" },
  { key: "indirect", label: "Indirect", hint: "Part of the job, inside something bigger" },
  { key: "manual", label: "Manual", hint: "Spreadsheets, email, chat, paper" },
  { key: "service", label: "Services", hint: "People paid to do it" },
];

function CompetitorSheet({
  initial,
  editing,
  open,
  onOpenChange,
}: {
  initial: CompetitorInput;
  editing?: Competitor;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const { id, refresh } = useDossier();
  const [form, setForm] = useState<CompetitorInput>(initial);
  async function save(e: FormEvent) {
    e.preventDefault();
    const data = { ...form, url: form.url?.trim() || null, pricing_note: form.pricing_note?.trim() || null };
    try {
      if (editing) await api.updateCompetitor(id, editing.id, data);
      else await api.createCompetitor(id, data);
      toast.success(editing ? "Saved" : "Added to the landscape");
      onOpenChange(false);
      await refresh();
    } catch (err) {
      toast.error((err as Error).message);
    }
  }
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <form onSubmit={save} className="flex h-full flex-col">
          <SheetHeader>
            <SheetTitle className="font-display text-2xl font-normal">
              {editing ? `Edit ${editing.name}` : "Add an alternative"}
            </SheetTitle>
            <SheetDescription>
              {editing ? "Your wording is kept when research is re-imported." : "Anything customers use today instead of you."}
            </SheetDescription>
          </SheetHeader>
          <div className="flex-1 space-y-4 px-4">
            <div className="space-y-1.5">
              <Label htmlFor="c-name">Name</Label>
              <Input id="c-name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label>Kind</Label>
              <Select value={form.kind} onValueChange={(v) => setForm({ ...form, kind: v as CompetitorKind })}>
                <SelectTrigger aria-label="Kind" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LANES.map((l) => (
                    <SelectItem key={l.key} value={l.key}>
                      {l.label} — {l.hint}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="c-url">Website (optional)</Label>
              <Input id="c-url" placeholder="https://" value={form.url ?? ""} onChange={(e) => setForm({ ...form, url: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="c-desc">What it covers</Label>
              <Textarea id="c-desc" required rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="c-price">Public pricing (optional)</Label>
              <Input id="c-price" value={form.pricing_note ?? ""} onChange={(e) => setForm({ ...form, pricing_note: e.target.value })} />
            </div>
          </div>
          <SheetFooter>
            <Button type="submit">{editing ? "Save" : "Add alternative"}</Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}

function CompetitorCard({ comp, index }: { comp: Competitor; index: number }) {
  const { id, refresh, evidenceById } = useDossier();
  const [editing, setEditing] = useState(false);
  const linked = comp.evidence_ids.map((e) => evidenceById[e]).filter(Boolean);
  const onlyUnverifiable = linked.length > 0 && linked.every((e) => e.verification === "unverifiable");

  return (
    <motion.li
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className="sheet list-none space-y-3 p-4"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="font-display text-xl leading-tight">{comp.name}</h3>
          {comp.url && (
            <a
              href={comp.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 font-mono text-[11px] text-muted-foreground hover:text-foreground"
            >
              {domain(comp.url)} <ExternalLink className="size-3" />
            </a>
          )}
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon-xs" aria-label={`Actions for ${comp.name}`}>
              <MoreHorizontal />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={() => setEditing(true)}>Edit</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              variant="destructive"
              onSelect={() =>
                api.updateCompetitor(id, comp.id, { status: "dismissed" }).then(
                  () => {
                    toast(`${comp.name} dismissed`);
                    return refresh();
                  },
                  (e: Error) => toast.error(e.message),
                )
              }
            >
              Dismiss
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <p className="text-sm leading-relaxed text-ink-soft">{comp.description}</p>
      {comp.pricing_note && (
        <p className="rounded border border-dashed px-2 py-1 font-mono text-[11px]">{comp.pricing_note}</p>
      )}
      {comp.sentiment.length > 0 && (
        <div>
          <p className="eyebrow mb-1">What customers say</p>
          <ClaimList claims={comp.sentiment} />
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2 border-t rule pt-3">
        {comp.source === "user" ? (
          <Provenance source="user" />
        ) : (
          <Provenance source="research" className={comp.user_edited ? "border-dashed" : undefined} />
        )}
        {onlyUnverifiable && (
          <span className="text-[11px] text-status-warning-ink">only unverifiable evidence</span>
        )}
        <span className="ml-auto">
          {comp.evidence_ids.map((e) => (
            <Cite key={e} id={e} />
          ))}
        </span>
      </div>
      {editing && (
        <CompetitorSheet
          editing={comp}
          initial={{ name: comp.name, kind: comp.kind, url: comp.url ?? "", description: comp.description, pricing_note: comp.pricing_note ?? "" }}
          open={editing}
          onOpenChange={setEditing}
        />
      )}
    </motion.li>
  );
}

export default function Landscape() {
  const { research } = useDossier();
  const [adding, setAdding] = useState(false);
  if (!research) return <SheetSkeleton lines={5} />;

  return (
    <div className="space-y-10">
      <section className="space-y-5" aria-labelledby="solved-title">
        <SectionHeading
          title={<span id="solved-title">How it&apos;s solved today</span>}
          kicker="Before asking whether customers want you, know what they already use — including the boring answer."
        >
          <Button variant="outline" size="sm" onClick={() => setAdding(true)}>
            <Plus /> Add alternative
          </Button>
        </SectionHeading>
        {research.current_solutions.length > 0 ? (
          <div className="sheet p-5 sm:p-6">
            <ClaimList claims={research.current_solutions} />
          </div>
        ) : (
          <EmptyState title="No evidence found.">
            The research summary of current solutions appears here after a method v2+ import.
          </EmptyState>
        )}
      </section>

      <section aria-label="Alternatives by kind" className="grid gap-6 md:grid-cols-2 2xl:grid-cols-4">
        {LANES.map((lane) => {
          const items = research.competitors.filter((c) => c.kind === lane.key);
          return (
            <div key={lane.key} className="min-w-0">
              <div className="mb-3 flex items-baseline justify-between border-b-2 border-foreground pb-2">
                <h2 className="font-display text-2xl">{lane.label}</h2>
                <span className="font-mono text-xs text-muted-foreground">{items.length}</span>
              </div>
              <p className="mb-3 text-xs text-muted-foreground">{lane.hint}</p>
              {items.length === 0 ? (
                <p className="rounded-md border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">
                  No evidence found.
                </p>
              ) : (
                <ul className="space-y-3">
                  {items.map((c, i) => (
                    <CompetitorCard key={c.id} comp={c} index={i} />
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </section>
      <CompetitorSheet
        key={String(adding)}
        initial={{ name: "", kind: "direct", url: "", description: "", pricing_note: "" }}
        open={adding}
        onOpenChange={setAdding}
      />
    </div>
  );
}
