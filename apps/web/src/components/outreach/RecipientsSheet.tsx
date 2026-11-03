"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { useDossier } from "@/components/dossier/DossierProvider";
import { EmptyState } from "@/components/dossier/layout";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type Campaign, type Recipient } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Pick people at the idea's prospects; each becomes one draft in the campaign. */
export function RecipientsSheet({
  campaign,
  open,
  onOpenChange,
  onDrafted,
}: {
  campaign: Campaign;
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onDrafted: () => void;
}) {
  const { id } = useDossier();
  const [rows, setRows] = useState<Recipient[] | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    let live = true;
    api.listRecipients(id).then(
      (r) => live && setRows(r),
      (e: Error) => toast.error(e.message),
    );
    return () => {
      live = false;
      setPicked(new Set());
    };
  }, [open, id]);

  const toggle = (cid: string) =>
    setPicked((p) => {
      const next = new Set(p);
      if (next.has(cid)) next.delete(cid);
      else next.add(cid);
      return next;
    });

  async function draft() {
    setBusy(true);
    try {
      const r = await api.createDrafts(id, campaign.id, [...picked]);
      toast(`Drafting ${r.created.length} message${r.created.length === 1 ? "" : "s"}`, {
        description: r.skipped.length ? r.skipped.map((s) => s.reason).join(" · ") : undefined,
      });
      onDrafted();
      onOpenChange(false);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <p className="eyebrow">{campaign.name}</p>
          <SheetTitle className="font-display text-3xl font-normal">Add recipients</SheetTitle>
          <SheetDescription>
            People named on verified public pages. Best-scored companies first.
          </SheetDescription>
        </SheetHeader>
        <div className="px-4">
          {!rows ? (
            <Skeleton className="h-40" />
          ) : rows.length === 0 ? (
            <EmptyState title="No contacts yet.">
              Contacts come from prospect research: people named in a verified quote.
            </EmptyState>
          ) : (
            <ul className="divide-y divide-border rounded-lg border">
              {rows.map((r) => {
                const inCampaign = r.campaign_ids.includes(campaign.id);
                const disabled = inCampaign || r.suppressed;
                return (
                  <li key={r.contact_id}>
                    <label
                      className={cn(
                        "grid cursor-pointer grid-cols-[1.25rem_3rem_minmax(0,1fr)] items-center gap-3 px-3 py-3 hover:bg-accent/50",
                        disabled && "cursor-not-allowed opacity-55",
                      )}
                    >
                      <input
                        type="checkbox"
                        className="accent-foreground"
                        disabled={disabled}
                        checked={picked.has(r.contact_id)}
                        onChange={() => toggle(r.contact_id)}
                        aria-label={`Draft a message to ${r.name}`}
                      />
                      <span className="font-display text-2xl leading-none tabular-nums">{r.score ?? "—"}</span>
                      <span className="min-w-0">
                        <span className="block truncate font-medium">
                          {r.name} <span className="font-normal text-muted-foreground">· {r.role}</span>
                        </span>
                        <span className="block truncate font-mono text-[11px] text-muted-foreground">
                          {r.company_name}
                          {r.email ? ` · ${r.email}` : " · no public email"}
                          {inCampaign && " · already in this campaign"}
                          {!inCampaign && r.campaign_ids.length > 0 && " · in another campaign"}
                          {r.suppressed && " · suppressed"}
                        </span>
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        <SheetFooter>
          <Button onClick={draft} disabled={busy || picked.size === 0}>
            Draft {picked.size || ""} message{picked.size === 1 ? "" : "s"}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
