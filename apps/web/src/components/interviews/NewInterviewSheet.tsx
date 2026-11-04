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
import { api, type Interview, type Recipient } from "@/lib/api";

const OTHER = "other";

/** Plan an interview with a known contact, or anyone else (name and role). */
export function NewInterviewSheet({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onCreated: (i: Interview) => void;
}) {
  const { id } = useDossier();
  const [people, setPeople] = useState<Recipient[] | null>(null);
  const [contact, setContact] = useState(OTHER);
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [company, setCompany] = useState("");
  const [when, setWhen] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    let live = true;
    api.listRecipients(id).then(
      (r) => live && setPeople(r),
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
      const iv = await api.createInterview(id, {
        contact_id: contact === OTHER ? null : contact,
        interviewee_name: name.trim(),
        interviewee_role: role.trim(),
        company_name: company.trim(),
        scheduled_at: when ? new Date(when).toISOString() : null,
        scheduling_note: note.trim(),
      });
      toast("Interview planned");
      setName("");
      setRole("");
      setCompany("");
      setWhen("");
      setNote("");
      setContact(OTHER);
      onCreated(iv);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const known = contact !== OTHER;
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <form onSubmit={submit} className="flex h-full flex-col">
          <SheetHeader>
            <p className="eyebrow">Interviews</p>
            <SheetTitle className="font-display text-3xl font-normal">Plan an interview</SheetTitle>
            <SheetDescription>The guide is written from the questions this case still can’t answer.</SheetDescription>
          </SheetHeader>
          <div className="space-y-5 px-4">
            <div className="space-y-1.5">
              <Label htmlFor="i-contact">With</Label>
              <Select value={contact} onValueChange={setContact}>
                <SelectTrigger id="i-contact" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={OTHER}>Someone else…</SelectItem>
                  {(people ?? []).map((p) => (
                    <SelectItem key={p.contact_id} value={p.contact_id}>
                      {p.name} · {p.role} · {p.company_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {!known && (
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5 sm:col-span-2">
                  <Label htmlFor="i-name">Name</Label>
                  <Input id="i-name" required value={name} onChange={(e) => setName(e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="i-role">Role</Label>
                  <Input id="i-role" value={role} onChange={(e) => setRole(e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="i-company">Company</Label>
                  <Input id="i-company" value={company} onChange={(e) => setCompany(e.target.value)} />
                </div>
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="i-when">When</Label>
              <Input id="i-when" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} className="w-auto" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="i-note">Scheduling note</Label>
              <Textarea id="i-note" rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Zoom link, who suggested the time…" />
            </div>
          </div>
          <SheetFooter>
            <Button type="submit" disabled={busy || (!known && !name.trim())}>
              Plan interview
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}
