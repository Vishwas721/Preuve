"use client";

import { Pencil, Plus, Sparkles, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { Cite } from "@/components/dossier/Cite";
import { useDossier } from "@/components/dossier/DossierProvider";
import { SectionHeading, SheetSkeleton } from "@/components/dossier/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { api, type Commitment, type Willingness, type WtpInput, type WtpSignal } from "@/lib/api";
import { shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";

const WILLINGNESS: Record<Willingness, string> = {
  unknown: "Not discussed",
  none: "Won’t pay",
  low: "Reluctant",
  some: "Open to paying",
  strong: "Says they’d pay",
};

const COMMITMENT: Record<Commitment, string> = {
  none: "None",
  verbal: "Verbal yes",
  pilot: "Pilot",
  signed: "Signed",
  paid: "Paid",
};
const LADDER: Commitment[] = ["none", "verbal", "pilot", "signed", "paid"];

/** PRD §23: stated willingness and actual commitment, never blended. */
export function WtpLedger({ version = 0 }: { version?: number }) {
  const { id, evidenceById } = useDossier();
  const [rows, setRows] = useState<WtpSignal[] | null>(null);
  const [editing, setEditing] = useState<WtpSignal | "new" | null>(null);

  const load = useCallback(() => api.listWtp(id).then(setRows, (e: Error) => toast.error(e.message)), [id]);
  useEffect(() => {
    load();
  }, [load, version]);

  return (
    <section className="space-y-4" aria-label="Willingness to pay">
      <SectionHeading
        title="Willingness to pay"
        kicker="What people say they’d pay is not a commitment. Only you can record a commitment."
      >
        <Button size="sm" variant="outline" onClick={() => setEditing("new")}>
          <Plus /> Add record
        </Button>
      </SectionHeading>
      {!rows ? (
        <SheetSkeleton lines={3} />
      ) : rows.length === 0 ? (
        <p className="rounded-lg border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
          No pricing conversations yet. Records proposed from replies and interviews appear here too.
        </p>
      ) : (
        <div className="sheet overflow-x-auto">
          <table className="w-full min-w-[44rem] text-sm">
            <thead>
              <tr className="border-b text-left font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                <th className="px-4 py-2.5 font-normal">Customer</th>
                <th className="px-3 py-2.5 font-normal">Spend today · problem cost · expected price</th>
                <th className="px-3 py-2.5 font-normal">Stated</th>
                <th className="border-l px-3 py-2.5 font-normal">Committed</th>
                <th className="px-2 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((r) => (
                <tr key={r.id} className="align-top">
                  <td className="px-4 py-3">
                    <span className="font-medium">{r.customer_label}</span>
                    {r.source === "ai" && (
                      <span className="mt-1 flex items-center gap-1 text-[11px] text-muted-foreground">
                        <Sparkles className="size-3" aria-hidden /> proposed from {r.response_id ? "a reply" : "an interview"}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-3 text-ink-soft">
                    {[r.current_spend, r.problem_cost, r.expected_price].some(Boolean) ? (
                      [r.current_spend || "—", r.problem_cost || "—", r.expected_price || "—"].join(" · ")
                    ) : (
                      <span className="text-muted-foreground">Not discussed</span>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    <span>{WILLINGNESS[r.stated_willingness]}</span>
                    {r.stated_quote && (
                      <span className="block font-display text-[14px] italic text-ink-soft">
                        “{r.stated_quote}”
                        {r.stated_evidence_id && evidenceById[r.stated_evidence_id] && <Cite id={r.stated_evidence_id} />}
                      </span>
                    )}
                  </td>
                  <td className="border-l px-3 py-3">
                    <CommitmentLadder value={r.commitment} />
                    {r.commitment !== "none" && (
                      <span className="mt-1 block text-xs text-muted-foreground">
                        {r.commitment_note}
                        {r.committed_at ? ` · ${shortDate(r.committed_at)}` : ""}
                      </span>
                    )}
                  </td>
                  <td className="px-2 py-3 text-right">
                    <Button variant="ghost" size="icon" aria-label={`Edit ${r.customer_label}`} onClick={() => setEditing(r)}>
                      <Pencil />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <WtpSheet
        row={editing}
        onOpenChange={(o) => !o && setEditing(null)}
        onSaved={() => {
          setEditing(null);
          load();
        }}
      />
    </section>
  );
}

function CommitmentLadder({ value }: { value: Commitment }) {
  const at = LADDER.indexOf(value);
  return (
    <span className="flex items-center gap-2" aria-label={`Commitment: ${COMMITMENT[value]}`}>
      <span className="flex gap-[2px]" aria-hidden>
        {LADDER.slice(1).map((step, i) => (
          <span key={step} className={cn("h-2 w-4 rounded-[2px]", i < at ? "bg-viz-seq" : "bg-viz-track")} />
        ))}
      </span>
      <span className={cn(value === "none" && "text-muted-foreground")}>{COMMITMENT[value]}</span>
    </span>
  );
}

function WtpSheet({
  row,
  onOpenChange,
  onSaved,
}: {
  row: WtpSignal | "new" | null;
  onOpenChange: (o: boolean) => void;
  onSaved: () => void;
}) {
  return (
    <Sheet open={row !== null} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        {row !== null && (
          <WtpForm key={row === "new" ? "new" : row.id} existing={row === "new" ? null : row} onSaved={onSaved} />
        )}
      </SheetContent>
    </Sheet>
  );
}

function WtpForm({ existing, onSaved }: { existing: WtpSignal | null; onSaved: () => void }) {
  const { id } = useDossier();
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState<WtpInput>(() =>
      existing
        ? {
            customer_label: existing.customer_label,
            current_spend: existing.current_spend,
            problem_cost: existing.problem_cost,
            expected_price: existing.expected_price,
            stated_willingness: existing.stated_willingness,
            stated_quote: existing.stated_quote,
            commitment: existing.commitment,
            commitment_note: existing.commitment_note,
          }
        : { stated_willingness: "unknown", commitment: "none" },
  );

  const set = (k: keyof WtpInput) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [k]: e.target.value });

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      if (existing) await api.updateWtp(id, existing.id, form);
      else await api.createWtp(id, form);
      toast("Saved");
      onSaved();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
        <form onSubmit={save} className="flex h-full flex-col">
          <SheetHeader>
            <p className="eyebrow">Willingness to pay</p>
            <SheetTitle className="font-display text-3xl font-normal">{existing ? "Edit record" : "New record"}</SheetTitle>
            <SheetDescription>Keep what they said apart from what they actually committed to.</SheetDescription>
          </SheetHeader>
          <div className="space-y-5 px-4">
            <div className="space-y-1.5">
              <Label htmlFor="w-who">Customer</Label>
              <Input id="w-who" required value={form.customer_label ?? ""} onChange={set("customer_label")} placeholder="Name, company" />
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="space-y-1.5">
                <Label htmlFor="w-spend">Spend today</Label>
                <Input id="w-spend" value={form.current_spend ?? ""} onChange={set("current_spend")} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="w-cost">Problem cost</Label>
                <Input id="w-cost" value={form.problem_cost ?? ""} onChange={set("problem_cost")} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="w-price">Expected price</Label>
                <Input id="w-price" value={form.expected_price ?? ""} onChange={set("expected_price")} />
              </div>
            </div>
            <fieldset className="space-y-3 rounded-lg border p-3">
              <legend className="eyebrow px-1">What they said</legend>
              <Select value={form.stated_willingness} onValueChange={(v) => setForm({ ...form, stated_willingness: v as Willingness })}>
                <SelectTrigger aria-label="Stated willingness" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(Object.keys(WILLINGNESS) as Willingness[]).map((w) => (
                    <SelectItem key={w} value={w}>
                      {WILLINGNESS[w]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Textarea aria-label="Their words" rows={2} value={form.stated_quote ?? ""} onChange={set("stated_quote")} placeholder="Their words, if you have them" />
            </fieldset>
            <fieldset className="space-y-3 rounded-lg border border-foreground/40 p-3">
              <legend className="eyebrow px-1">What they committed to</legend>
              <Select value={form.commitment} onValueChange={(v) => setForm({ ...form, commitment: v as Commitment })}>
                <SelectTrigger aria-label="Commitment" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LADDER.map((c) => (
                    <SelectItem key={c} value={c}>
                      {COMMITMENT[c]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Input aria-label="Commitment note" value={form.commitment_note ?? ""} onChange={set("commitment_note")} placeholder="e.g. signed LOI for a 2-site pilot" />
            </fieldset>
          </div>
          <SheetFooter className="flex-row">
            {existing && (
              <Button
                type="button"
                variant="ghost"
                onClick={() => api.deleteWtp(id, existing.id).then(onSaved, (e: Error) => toast.error(e.message))}
              >
                <Trash2 /> Delete
              </Button>
            )}
            <Button type="submit" className="ml-auto" disabled={busy || !form.customer_label?.trim()}>
              Save
            </Button>
          </SheetFooter>
        </form>
  );
}
