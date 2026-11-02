"use client";

import { MoreHorizontal, Plus, RefreshCw } from "lucide-react";
import { motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { useDossier } from "@/components/dossier/DossierProvider";
import { EmptyState, SectionHeading } from "@/components/dossier/layout";
import { Provenance, Stamp } from "@/components/dossier/marks";
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
import { ScoreBar, ScoreFigure } from "@/components/viz/ScoreBar";
import { api, type Criterion, type ICP, type Ratings } from "@/lib/api";

const CRITERIA: { key: Criterion; label: string; weight: number; question: string }[] = [
  { key: "pain_likelihood", label: "Pain likelihood", weight: 30, question: "How strongly do they feel the problem?" },
  { key: "ability_to_pay", label: "Ability to pay", weight: 25, question: "Budget and buying authority?" },
  { key: "reachability", label: "Reachability", weight: 20, question: "Findable and contactable publicly?" },
  { key: "frequency_urgency", label: "Urgency", weight: 15, question: "How often, how pressing?" },
  { key: "segment_size", label: "Segment size", weight: 10, question: "Enough of them in the market?" },
];

function sizeLabel(icp: Pick<ICP, "size_min" | "size_max">): string {
  if (icp.size_min && icp.size_max) return `${icp.size_min}–${icp.size_max} employees`;
  if (icp.size_min) return `${icp.size_min}+ employees`;
  if (icp.size_max) return `up to ${icp.size_max} employees`;
  return "any size";
}

function RatingsFields({ value, onChange }: { value: Ratings; onChange: (r: Ratings) => void }) {
  return (
    <div className="space-y-4">
      {CRITERIA.map(({ key, label, weight, question }) => (
        <fieldset key={key} className="space-y-1.5">
          <legend className="flex w-full items-baseline justify-between text-sm font-medium">
            {label} <span className="font-mono text-[11px] text-muted-foreground">weight {weight}</span>
          </legend>
          <p className="text-xs text-muted-foreground">{question}</p>
          <div className="flex gap-2">
            <Select
              value={String(value[key].rating)}
              onValueChange={(v) => onChange({ ...value, [key]: { ...value[key], rating: Number(v) } })}
            >
              <SelectTrigger aria-label={`${label} rating`} className="w-24">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[1, 2, 3, 4, 5].map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n} / 5
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              required
              aria-label={`${label} rationale`}
              value={value[key].rationale}
              onChange={(e) => onChange({ ...value, [key]: { ...value[key], rationale: e.target.value } })}
            />
          </div>
        </fieldset>
      ))}
    </div>
  );
}

function ratingsOf(icp: ICP): Ratings {
  return Object.fromEntries(
    icp.score_breakdown.map((c) => [c.criterion, { rating: c.rating, rationale: c.rationale }]),
  ) as Ratings;
}

function RatingsSheet({ icp, open, onOpenChange }: { icp: ICP; open: boolean; onOpenChange: (o: boolean) => void }) {
  const { id, refresh } = useDossier();
  const [ratings, setRatings] = useState<Ratings>(() => ratingsOf(icp));
  async function save(e: FormEvent) {
    e.preventDefault();
    try {
      await api.updateIcp(id, icp.id, { ratings });
      toast.success("Ratings updated, score recalculated");
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
            <SheetTitle className="font-display text-2xl font-normal">Rate “{icp.name}”</SheetTitle>
            <SheetDescription>The score is computed from these ratings and the fixed weights.</SheetDescription>
          </SheetHeader>
          <div className="flex-1 px-4">
            <RatingsFields value={ratings} onChange={setRatings} />
          </div>
          <SheetFooter>
            <Button type="submit">Save ratings</Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}

function AddProfileSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { id, refresh } = useDossier();
  const [form, setForm] = useState({ name: "", company_type: "", geography: "", size_min: "", size_max: "" });
  const [ratings, setRatings] = useState<Ratings>(
    () =>
      Object.fromEntries(CRITERIA.map(({ key }) => [key, { rating: 3, rationale: "Set by you" }])) as Ratings,
  );
  async function save(e: FormEvent) {
    e.preventDefault();
    try {
      await api.createIcp(id, {
        name: form.name,
        company_type: form.company_type,
        geography: form.geography,
        size_min: form.size_min ? Number(form.size_min) : null,
        size_max: form.size_max ? Number(form.size_max) : null,
        ratings,
      });
      toast.success("Profile added");
      onOpenChange(false);
      await refresh();
    } catch (err) {
      toast.error((err as Error).message);
    }
  }
  const field = (k: keyof typeof form, label: string, type = "text") => (
    <div className="space-y-1.5">
      <Label htmlFor={`p-${k}`}>{label}</Label>
      <Input
        id={`p-${k}`}
        type={type}
        min={type === "number" ? 1 : undefined}
        required={!k.startsWith("size")}
        value={form[k]}
        onChange={(e) => setForm({ ...form, [k]: e.target.value })}
      />
    </div>
  );
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <form onSubmit={save} className="flex h-full flex-col">
          <SheetHeader>
            <SheetTitle className="font-display text-2xl font-normal">Add a customer profile</SheetTitle>
            <SheetDescription>Your own hypothesis about who to sell to.</SheetDescription>
          </SheetHeader>
          <div className="flex-1 space-y-4 px-4">
            {field("name", "Name")}
            {field("company_type", "Company type")}
            {field("geography", "Geography")}
            <div className="grid grid-cols-2 gap-3">
              {field("size_min", "Min employees", "number")}
              {field("size_max", "Max employees", "number")}
            </div>
            <RatingsFields value={ratings} onChange={setRatings} />
          </div>
          <SheetFooter>
            <Button type="submit">Add profile</Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}

function ProfileCard({ icp, index }: { icp: ICP; index: number }) {
  const { id, refresh } = useDossier();
  const [rating, setRating] = useState(false);

  async function patch(data: Parameters<typeof api.updateIcp>[2], message: string) {
    try {
      await api.updateIcp(id, icp.id, data);
      toast(message);
      await refresh();
    } catch (err) {
      toast.error((err as Error).message);
    }
  }

  return (
    <motion.article
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06 }}
      className="sheet relative flex flex-col gap-4 p-5"
    >
      {icp.is_primary && <Stamp tone="ink" className="absolute -top-2.5 right-12 bg-paper">Primary target</Stamp>}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="eyebrow">Profile {String.fromCharCode(65 + index)}</p>
          <h3 className="mt-1 font-display text-2xl leading-tight">{icp.name}</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {icp.company_type} · {sizeLabel(icp)} · {icp.geography}
          </p>
        </div>
        <div className="flex items-start gap-1">
          <ScoreFigure score={icp.hypothesis_score} label="hypothesis" />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${icp.name}`}>
                <MoreHorizontal />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {!icp.is_primary && (
                <DropdownMenuItem onSelect={() => patch({ is_primary: true }, "Primary target changed")}>
                  Make primary target
                </DropdownMenuItem>
              )}
              <DropdownMenuItem onSelect={() => setRating(true)}>Edit ratings</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive" onSelect={() => patch({ status: "dismissed" }, "Profile dismissed")}>
                Dismiss
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5 text-xs">
        {(icp.roles.users ?? []).map((r) => (
          <span key={`u-${r}`} className="rounded-full border px-2 py-0.5">
            <span className="text-muted-foreground">uses · </span>
            {r}
          </span>
        ))}
        {(icp.roles.buyers ?? []).map((r) => (
          <span key={`b-${r}`} className="rounded-full border border-foreground/30 px-2 py-0.5">
            <span className="text-muted-foreground">buys · </span>
            {r}
          </span>
        ))}
      </div>

      <div className="space-y-1">
        {icp.score_breakdown.map((c) => {
          const meta = CRITERIA.find((x) => x.key === c.criterion);
          return (
            <ScoreBar
              key={c.criterion}
              label={meta?.label ?? c.criterion}
              value={c.points}
              max={c.weight}
              detail={
                <span>
                  <span className="font-mono">{c.rating}/5</span> — {c.rationale}
                </span>
              }
            />
          );
        })}
      </div>

      {icp.signals.length > 0 && (
        <div className="border-t rule pt-3">
          <p className="eyebrow mb-1.5">How to spot them</p>
          <ul className="flex flex-wrap gap-1.5">
            {icp.signals.map((s) => (
              <li key={s} className="rounded bg-muted px-2 py-0.5 text-xs">
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="mt-auto">
        <Provenance source={icp.source} />
      </div>
      {rating && <RatingsSheet icp={icp} open={rating} onOpenChange={setRating} />}
    </motion.article>
  );
}

export function ProfilesSection() {
  const { analysis, startAnalysis, busy } = useDossier();
  const [adding, setAdding] = useState(false);
  const icps = analysis?.icps ?? [];
  return (
    <section aria-labelledby="profiles-title" className="space-y-5">
      <SectionHeading
        index="03"
        title={<span id="profiles-title">Who to sell to</span>}
        kicker="Candidate customer profiles, scored by a fixed rubric. Hypotheses until prospects and replies say otherwise."
      >
        <Button variant="ghost" size="sm" onClick={() => setAdding(true)}>
          <Plus /> Add profile
        </Button>
        {analysis?.hypothesis && (
          <Button
            variant="outline"
            size="sm"
            disabled={busy}
            onClick={() => startAnalysis("icps").then(() => toast("Regenerating profiles…"), (e: Error) => toast.error(e.message))}
          >
            <RefreshCw /> Regenerate
          </Button>
        )}
      </SectionHeading>
      {icps.length === 0 ? (
        <EmptyState title="No profiles yet.">Generated with the analysis, or add your own.</EmptyState>
      ) : (
        <div className="grid gap-5 xl:grid-cols-2">
          {icps.map((icp, i) => (
            <ProfileCard key={icp.id} icp={icp} index={i} />
          ))}
        </div>
      )}
      <AddProfileSheet open={adding} onOpenChange={setAdding} />
    </section>
  );
}
