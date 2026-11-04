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
import { api, type MessageSummary, type Reply } from "@/lib/api";

const NONE = "none";

/** Paste a reply that arrived elsewhere (another inbox, LinkedIn, a call). */
export function PasteReplySheet({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onCreated: (r: Reply) => void;
}) {
  const { id } = useDossier();
  const [sent, setSent] = useState<MessageSummary[] | null>(null);
  const [messageId, setMessageId] = useState(NONE);
  const [text, setText] = useState("");
  const [fromName, setFromName] = useState("");
  const [fromEmail, setFromEmail] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    let live = true;
    api
      .listCampaigns(id)
      .then((cs) => Promise.all(cs.map((c) => api.listMessages(id, c.id))))
      .then(
        (lists) => live && setSent(lists.flat().filter((m) => m.status === "sent" || m.status === "bounced")),
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
      const r = await api.pasteReply(id, {
        text,
        message_id: messageId === NONE ? null : messageId,
        from_name: fromName.trim(),
        from_email: fromEmail.trim() || null,
      });
      toast("Reply saved", { description: "Classifying on the local model…" });
      setText("");
      setFromName("");
      setFromEmail("");
      setMessageId(NONE);
      onCreated(r);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const linked = messageId !== NONE;
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <form onSubmit={submit} className="flex h-full flex-col">
          <SheetHeader>
            <p className="eyebrow">Replies</p>
            <SheetTitle className="font-display text-3xl font-normal">Paste a reply</SheetTitle>
            <SheetDescription>
              Their words become first-party evidence, but only the parts quoted exactly. It’s processed on your
              local model.
            </SheetDescription>
          </SheetHeader>
          <div className="space-y-5 px-4">
            <div className="space-y-1.5">
              <Label htmlFor="r-msg">In reply to</Label>
              <Select value={messageId} onValueChange={setMessageId}>
                <SelectTrigger id="r-msg" className="w-full">
                  <SelectValue placeholder="Pick the email it answers" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>Not a reply to an outreach email</SelectItem>
                  {(sent ?? []).map((m) => (
                    <SelectItem key={m.id} value={m.id}>
                      {m.to_name} — {m.subject}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {!linked && (
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="r-name">From</Label>
                  <Input id="r-name" value={fromName} onChange={(e) => setFromName(e.target.value)} placeholder="Name" />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="r-email">Email</Label>
                  <Input id="r-email" type="email" value={fromEmail} onChange={(e) => setFromEmail(e.target.value)} placeholder="optional" />
                </div>
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="r-text">Their reply</Label>
              <Textarea
                id="r-text"
                required
                rows={10}
                value={text}
                onChange={(e) => setText(e.target.value)}
                className="font-display text-[17px] leading-relaxed"
                placeholder="Paste it exactly as written. Quoted history below “On … wrote:” is removed."
              />
            </div>
          </div>
          <SheetFooter>
            <Button type="submit" disabled={busy || !text.trim()}>
              Save and classify
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}
