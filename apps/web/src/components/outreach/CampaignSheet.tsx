"use client";

import { useState } from "react";
import { toast } from "sonner";

import { useDossier } from "@/components/dossier/DossierProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { api, type Campaign } from "@/lib/api";

/** Open a new outreach campaign: a name, the research purpose in plain words, a daily cap. */
export function CampaignSheet({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onCreated: (c: Campaign) => void;
}) {
  const { id, analysis } = useDossier();
  const primary = analysis?.icps.find((i) => i.is_primary);
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState("");
  const [limit, setLimit] = useState(10);
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const c = await api.createCampaign(id, {
        name: name.trim(),
        purpose: purpose.trim(),
        daily_limit: limit,
        icp_id: primary?.id ?? null,
      });
      toast("Campaign opened");
      setName("");
      setPurpose("");
      onCreated(c);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <form onSubmit={submit} className="flex h-full flex-col">
          <SheetHeader>
            <p className="eyebrow">New campaign{primary ? ` · ${primary.name}` : ""}</p>
            <SheetTitle className="font-display text-3xl font-normal">Open a line of inquiry</SheetTitle>
            <SheetDescription>
              Research, not sales. Every message will be a draft until you approve it.
            </SheetDescription>
          </SheetHeader>
          <div className="space-y-5 px-4">
            <div className="space-y-1.5">
              <Label htmlFor="c-name">Name</Label>
              <Input id="c-name" required maxLength={200} value={name} onChange={(e) => setName(e.target.value)} placeholder="Weekly owner reports — PEs" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="c-purpose">Research purpose</Label>
              <Textarea
                id="c-purpose"
                required
                minLength={10}
                maxLength={600}
                rows={4}
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
                placeholder="I'm researching how mid-size contractors put together weekly owner reports. I'm not selling anything."
              />
              <p className="text-xs text-muted-foreground">
                Shown to the drafter and printed in every message’s footer, next to your name.
              </p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="c-limit">Daily limit</Label>
              <Input
                id="c-limit"
                type="number"
                min={1}
                max={50}
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="w-28 font-mono"
              />
              <p className="text-xs text-muted-foreground">Quality over volume: keep it small.</p>
            </div>
          </div>
          <SheetFooter>
            <Button type="submit" disabled={saving || name.trim() === "" || purpose.trim().length < 10}>
              Open campaign
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}
