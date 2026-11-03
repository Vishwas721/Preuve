"use client";

import { Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/dossier/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type Suppression, type SuppressionReason } from "@/lib/api";
import { shortDate } from "@/lib/format";

const REASON: Record<SuppressionReason, string> = {
  unsubscribed: "Unsubscribed",
  bounced: "Bounced",
  manual: "Added by you",
  deletion_request: "Deletion request",
};

/** The global do-not-contact list. Only entries you added by hand can be removed. */
export function SuppressionSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const [rows, setRows] = useState<Suppression[] | null>(null);
  const [email, setEmail] = useState("");
  const [note, setNote] = useState("");

  const load = useCallback(() => api.listSuppressions().then(setRows, (e: Error) => toast.error(e.message)), []);
  useEffect(() => {
    if (open) load();
  }, [open, load]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.addSuppression(email.trim(), note.trim());
      setEmail("");
      setNote("");
      toast("Address suppressed");
      await load();
    } catch (err) {
      toast.error((err as Error).message);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <p className="eyebrow">All campaigns · all cases</p>
          <SheetTitle className="font-display text-3xl font-normal">Do not contact</SheetTitle>
          <SheetDescription>
            Nothing is ever sent to these addresses. Someone replied “stop”? Add them here.
          </SheetDescription>
        </SheetHeader>
        <div className="space-y-5 px-4 pb-8">
          <form onSubmit={add} className="flex flex-wrap gap-2">
            <Input
              aria-label="Email to suppress"
              type="email"
              required
              placeholder="name@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="min-w-48 flex-1"
            />
            <Input aria-label="Note" placeholder="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} className="min-w-32 flex-1" />
            <Button type="submit" variant="outline">
              Suppress
            </Button>
          </form>
          {!rows ? (
            <Skeleton className="h-24" />
          ) : rows.length === 0 ? (
            <EmptyState title="The list is empty.">Unsubscribes, bounces and deletion requests land here.</EmptyState>
          ) : (
            <ul className="divide-y divide-border rounded-lg border">
              {rows.map((s) => (
                <li key={s.id} className="flex items-center gap-3 px-3 py-2.5">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-mono text-sm">{s.email}</span>
                    <span className="block text-xs text-muted-foreground">
                      {REASON[s.reason]} · {shortDate(s.created_at)}
                      {s.note ? ` · ${s.note}` : ""}
                    </span>
                  </span>
                  {s.reason === "manual" && (
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Remove ${s.email}`}
                      onClick={() =>
                        api.deleteSuppression(s.id).then(load, (e: Error) => toast.error(e.message))
                      }
                    >
                      <Trash2 />
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
