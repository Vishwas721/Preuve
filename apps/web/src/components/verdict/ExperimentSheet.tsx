"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { useDossier } from "@/components/dossier/DossierProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { api, type Campaign, type Cohort, type Experiment } from "@/lib/api";

const ANY = "any";
const EMPTY: Cohort = { label: "", campaign_ids: [], icp_id: null, role_contains: "" };

function CohortFields({
  name,
  value,
  onChange,
  campaigns,
}: {
  name: string;
  value: Cohort;
  onChange: (c: Cohort) => void;
  campaigns: Campaign[];
}) {
  const { analysis } = useDossier();
  const icps = analysis?.icps ?? [];
  const p = name.toLowerCase().replace(/\s+/g, "-");
  return (
    <fieldset className="space-y-3 rounded-md border p-3">
      <legend className="eyebrow px-1">{name}</legend>
      <div className="space-y-1.5">
        <Label htmlFor={`${p}-label`}>Label</Label>
        <Input
          id={`${p}-label`}
          required
          maxLength={100}
          placeholder="e.g. Operations directors"
          value={value.label}
          onChange={(e) => onChange({ ...value, label: e.target.value })}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor={`${p}-role`}>Contact role contains</Label>
        <Input
          id={`${p}-role`}
          maxLength={100}
          placeholder="e.g. director (blank = any role)"
          value={value.role_contains}
          onChange={(e) => onChange({ ...value, role_contains: e.target.value })}
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Campaign</Label>
          <Select
            value={value.campaign_ids[0] ?? ANY}
            onValueChange={(v) => onChange({ ...value, campaign_ids: v === ANY ? [] : [v] })}
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any campaign</SelectItem>
              {campaigns.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Customer profile</Label>
          <Select
            value={value.icp_id ?? ANY}
            onValueChange={(v) => onChange({ ...value, icp_id: v === ANY ? null : v })}
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any profile</SelectItem>
              {icps.map((i) => (
                <SelectItem key={i.id} value={i.id}>
                  {i.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
    </fieldset>
  );
}

/** Define an experiment (PRD §28): a hypothesis and one or two cohorts of sent outreach. */
export function ExperimentSheet({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onCreated: (e: Experiment) => void;
}) {
  const { id } = useDossier();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [hypothesis, setHypothesis] = useState("");
  const [a, setA] = useState<Cohort>(EMPTY);
  const [b, setB] = useState<Cohort | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    let live = true;
    api.listCampaigns(id).then(
      (c) => live && setCampaigns(c),
      (e: Error) => toast.error(e.message),
    );
    return () => {
      live = false;
    };
  }, [open, id]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const row = await api.createExperiment(id, { hypothesis, cohort_a: a, cohort_b: b });
      setHypothesis("");
      setA(EMPTY);
      setB(null);
      onCreated(row);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <form onSubmit={submit} className="flex min-h-full flex-col">
          <SheetHeader>
            <SheetTitle className="font-display text-2xl font-normal">New experiment</SheetTitle>
            <SheetDescription>
              Results are counted from outreach already sent and its replies. You write the conclusion.
            </SheetDescription>
          </SheetHeader>
          <div className="flex-1 space-y-4 px-4">
            <div className="space-y-1.5">
              <Label htmlFor="hypothesis">Hypothesis</Label>
              <Textarea
                id="hypothesis"
                required
                maxLength={2000}
                placeholder="Operations directors are better buyers than project managers."
                value={hypothesis}
                onChange={(e) => setHypothesis(e.target.value)}
              />
            </div>
            <CohortFields name="Cohort A" value={a} onChange={setA} campaigns={campaigns} />
            {b ? (
              <>
                <CohortFields name="Cohort B" value={b} onChange={setB} campaigns={campaigns} />
                <Button type="button" variant="ghost" size="sm" onClick={() => setB(null)}>
                  Remove cohort B
                </Button>
              </>
            ) : (
              <Button type="button" variant="outline" size="sm" onClick={() => setB(EMPTY)}>
                Compare with a second cohort
              </Button>
            )}
          </div>
          <SheetFooter>
            <Button type="submit" disabled={busy}>
              Start experiment
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}
