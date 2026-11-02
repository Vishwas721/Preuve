"use client";

import { History, PencilLine } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { useDossier } from "@/components/dossier/DossierProvider";
import { EmptyState, SectionHeading } from "@/components/dossier/layout";
import { Provenance } from "@/components/dossier/marks";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { api, type Hypothesis, type HypothesisFields } from "@/lib/api";
import { shortDate } from "@/lib/format";

const FIELDS: { key: keyof HypothesisFields; label: string; long?: boolean }[] = [
  { key: "problem", label: "Problem", long: true },
  { key: "users", label: "Who feels it" },
  { key: "buyer", label: "Who pays" },
  { key: "decision_maker", label: "Who decides" },
  { key: "economic_value", label: "What it's worth", long: true },
  { key: "geography", label: "Where" },
  { key: "industry", label: "Industry" },
];

function EditSheet({
  hypothesis,
  open,
  onOpenChange,
}: {
  hypothesis: Hypothesis;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const { id, refresh } = useDossier();
  const [draft, setDraft] = useState<HypothesisFields>(() => {
    const d = {} as HypothesisFields;
    for (const f of FIELDS) d[f.key] = hypothesis[f.key];
    return d;
  });
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  async function save(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const v = await api.editHypothesis(id, { ...draft, change_note: note || undefined });
      toast.success(`Saved as version ${v.version}`);
      onOpenChange(false);
      await refresh();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <form onSubmit={save} className="flex h-full flex-col">
          <SheetHeader>
            <SheetTitle className="font-display text-2xl font-normal">Revise the hypothesis</SheetTitle>
            <SheetDescription>
              Saving creates version {hypothesis.version + 1}. Earlier versions stay in the history.
            </SheetDescription>
          </SheetHeader>
          <div className="flex-1 space-y-4 px-4">
            {FIELDS.map(({ key, label, long }) => (
              <div key={key} className="space-y-1.5">
                <Label htmlFor={`h-${key}`}>{label}</Label>
                {long ? (
                  <Textarea
                    id={`h-${key}`}
                    required
                    rows={3}
                    value={draft[key]}
                    onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
                  />
                ) : (
                  <Input
                    id={`h-${key}`}
                    required
                    value={draft[key]}
                    onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
                  />
                )}
              </div>
            ))}
            <div className="space-y-1.5">
              <Label htmlFor="h-note">What changed? (optional)</Label>
              <Input id="h-note" value={note} onChange={(e) => setNote(e.target.value)} />
            </div>
          </div>
          <SheetFooter>
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : `Save as version ${hypothesis.version + 1}`}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}

function HistorySheet({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { id, analysis } = useDossier();
  const [versions, setVersions] = useState<Hypothesis[] | null>(null);
  const current = analysis?.hypothesis?.version;

  // Fetch whenever the sheet opens (the parent opens it, so onOpenChange doesn't fire then).
  useEffect(() => {
    if (open) api.hypothesisVersions(id).then(setVersions, () => setVersions([]));
  }, [open, id, current]);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle className="font-display text-2xl font-normal">How the hypothesis evolved</SheetTitle>
          <SheetDescription>Newest first. Nothing is overwritten.</SheetDescription>
        </SheetHeader>
        <ol className="relative mx-4 space-y-6 border-l rule pl-6">
          {(versions ?? []).map((v) => (
            <li key={v.id} className="relative">
              <span className="absolute top-1.5 -left-[29px] size-2.5 rounded-full border-2 border-paper bg-foreground" />
              <p className="eyebrow">
                v{v.version} · {shortDate(v.created_at)}
              </p>
              <div className="mt-1">
                <Provenance source={v.source} />
              </div>
              <p className="mt-2 font-display text-lg italic leading-snug">{v.problem}</p>
              {v.change_note && <p className="mt-1 text-xs text-muted-foreground">{v.change_note}</p>}
            </li>
          ))}
        </ol>
      </SheetContent>
    </Sheet>
  );
}

export function HypothesisSection() {
  const { analysis } = useDossier();
  const [editing, setEditing] = useState(false);
  const [history, setHistory] = useState(false);
  const h = analysis?.hypothesis;

  return (
    <section aria-labelledby="hypothesis-title" className="space-y-5">
      <SectionHeading
        index="01"
        title={<span id="hypothesis-title">The hypothesis</span>}
        kicker="What we believe, before evidence. Every line here is an assumption until research or customers confirm it."
      >
        {h && (
          <>
            <Button variant="ghost" size="sm" onClick={() => setHistory(true)}>
              <History /> v{h.version}
            </Button>
            <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
              <PencilLine /> Revise
            </Button>
          </>
        )}
      </SectionHeading>

      {!h ? (
        <EmptyState title="Not analyzed yet.">
          Press <strong>Analyze</strong> above. Preuve restructures your idea into a testable problem,
          open questions and customer profiles — labelled as assumptions.
        </EmptyState>
      ) : (
        <article className="sheet relative overflow-hidden p-6 sm:p-8">
          <span aria-hidden className="pointer-events-none absolute -top-6 left-3 font-display text-[9rem] leading-none text-foreground/[0.06]">
            &ldquo;
          </span>
          <div className="relative">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <Provenance source={h.source} />
            </div>
            <p className="font-display text-2xl leading-snug sm:text-[1.85rem]">{h.problem}</p>
            <dl className="mt-6 grid gap-x-8 gap-y-4 border-t rule pt-5 sm:grid-cols-2">
              {FIELDS.filter((f) => f.key !== "problem").map(({ key, label, long }) => (
                <div key={key} className={long ? "sm:col-span-2" : undefined}>
                  <dt className="eyebrow">{label}</dt>
                  <dd className="mt-1 text-[0.95rem] leading-relaxed">{h[key]}</dd>
                </div>
              ))}
            </dl>
            {h.change_note && h.source === "research" && (
              <p className="mt-5 border-l-2 border-viz-seq/50 pl-3 text-xs text-muted-foreground">{h.change_note}</p>
            )}
          </div>
        </article>
      )}

      {h && editing && <EditSheet key={h.version} hypothesis={h} open={editing} onOpenChange={setEditing} />}
      <HistorySheet open={history} onOpenChange={setHistory} />
    </section>
  );
}
