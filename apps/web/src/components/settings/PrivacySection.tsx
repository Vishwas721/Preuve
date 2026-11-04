"use client";

// Settings → Privacy (Phase 5B, PRD §37): look up a person by email (what this workspace holds),
// export it as JSON, erase it; and the privacy & provenance check.

import { Download, Search, ShieldCheck, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { SectionHeading } from "@/components/dossier/layout";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, type PersonSummary, type PrivacyFinding } from "@/lib/api";
import { shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";

function PersonLookup() {
  const [email, setEmail] = useState("");
  const [person, setPerson] = useState<PersonSummary | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);

  async function look(e?: React.FormEvent) {
    e?.preventDefault();
    setBusy(true);
    try {
      setPerson(await api.findPerson(email.trim()));
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function erase() {
    if (!person?.email) return;
    setBusy(true);
    try {
      const r = await api.erasePerson(person.email);
      toast("Erased", {
        description: `${r.contacts} contacts, ${r.replies} replies, ${r.messages} messages. The address is suppressed.`,
      });
      setPerson(await api.findPerson(person.email));
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
      setConfirm(false);
    }
  }

  const rows: [string, number][] = person
    ? [
        ["Contacts", person.contacts.length],
        ["Emails sent", person.messages],
        ["Replies", person.replies],
        ["Interviews", person.interviews],
        ["WTP records", person.wtp_records],
      ]
    : [];

  return (
    <div className="space-y-4">
      <p className="eyebrow">A person&apos;s data</p>
      <form onSubmit={look} className="flex flex-wrap gap-2">
        <Input
          type="email"
          required
          aria-label="Email address to look up"
          placeholder="their@email.com"
          className="min-w-0 flex-1"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Button type="submit" size="sm" className="h-9" disabled={busy}>
          <Search /> Look up
        </Button>
      </form>

      {person && (
        <div className="space-y-4 rounded-md border p-4" aria-live="polite">
          {person.nothing_found ? (
            <p className="text-sm">
              This workspace holds nothing about <span className="font-mono">{person.email}</span>.
              {person.suppressed && " The address is suppressed, so it won't be emailed."}
            </p>
          ) : (
            <>
              <dl className="grid grid-cols-3 gap-3 sm:grid-cols-5">
                {rows.map(([label, n]) => (
                  <div key={label}>
                    <dt className="eyebrow !text-[9px]">{label}</dt>
                    <dd className="mt-1 font-display text-2xl leading-none tabular-nums">{n}</dd>
                  </div>
                ))}
              </dl>
              {person.contacts.length > 0 && (
                <ul className="space-y-1.5 text-sm">
                  {person.contacts.map((c) => (
                    <li key={c.id} className="min-w-0">
                      <span className="font-medium">{c.name}</span>, {c.role} at {c.company}
                      <span className="text-muted-foreground"> · case “{c.idea_title}”</span>
                      <span className="block truncate font-mono text-[11px] text-muted-foreground">
                        from {c.source_url} · collected {shortDate(c.collected_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              <p className="text-xs text-muted-foreground">
                {person.suppressed ? "Suppressed: Preuve won't email this address." : "Not suppressed."}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button asChild size="sm" variant="outline">
                  <a href={api.personExportUrl(person.email ?? "")} download>
                    <Download /> Export JSON
                  </a>
                </Button>
                <Button size="sm" variant="outline" onClick={() => setConfirm(true)} disabled={busy}>
                  <Trash2 /> Erase this person
                </Button>
              </div>
            </>
          )}
        </div>
      )}

      <AlertDialog open={confirm} onOpenChange={setConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Erase {person?.email}?</AlertDialogTitle>
            <AlertDialogDescription>
              Deletes their contacts, replies, interview notes and WTP records, every exhibit and stored page that
              names them, and reports that quoted them. Sent emails are redacted. The address is suppressed and
              remembered as a hash, so they aren&apos;t emailed or re-imported. This can&apos;t be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => void erase()}>Erase</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

const SEVERITY = {
  high: "border-status-critical/40 bg-status-critical/5",
  medium: "border-status-warning/40 bg-status-warning/5",
  low: "border-border",
} as const;

function PrivacyCheck() {
  const [findings, setFindings] = useState<PrivacyFinding[] | null>(null);

  const load = useCallback(
    () =>
      api.privacyCheck().then(
        (r) => setFindings(r.findings),
        (e: Error) => toast.error(e.message),
      ),
    [],
  );
  useEffect(() => {
    void load();
  }, [load]);

  async function remove(ideaId: string, contactId: string) {
    try {
      await api.deleteContact(ideaId, contactId);
      toast("Contact deleted", { description: "Their data was erased and the address suppressed." });
      await load();
    } catch (err) {
      toast.error((err as Error).message);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <p className="eyebrow">Privacy &amp; provenance check</p>
        <Button size="sm" variant="ghost" onClick={() => void load()}>
          Run again
        </Button>
      </div>
      {findings === null ? (
        <p className="text-sm text-muted-foreground">Checking…</p>
      ) : findings.length === 0 ? (
        <p className="flex items-center gap-2 text-sm">
          <ShieldCheck className="size-4 text-status-good-ink" aria-hidden /> No issues found. Every exhibit and
          contact has its source, and nothing is kept past its time.
        </p>
      ) : (
        <ul className="space-y-2">
          {findings.map((f, i) => (
            <li key={i} className={cn("rounded-md border p-3 text-sm", SEVERITY[f.severity])}>
              <p>
                <span className="mr-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  {f.kind} · {f.severity}
                </span>
                {f.message}
              </p>
              {f.contacts && (
                <ul className="mt-2 space-y-1">
                  {f.contacts.map((c) => (
                    <li key={c.id} className="flex flex-wrap items-center gap-2">
                      <span className="min-w-0 flex-1 truncate">
                        {c.name} <span className="text-muted-foreground">· {c.company}</span>
                      </span>
                      <Button size="sm" variant="ghost" onClick={() => void remove(c.idea_id, c.id)}>
                        Delete
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function PrivacySection() {
  return (
    <section aria-labelledby="privacy" className="space-y-4">
      <SectionHeading
        title={<span id="privacy">Privacy</span>}
        kicker="Answer access and deletion requests, and check that every piece of data has a source and isn't kept too long."
      />
      <div className="sheet space-y-8 p-5">
        <PersonLookup />
        <div className="border-t rule pt-6">
          <PrivacyCheck />
        </div>
      </div>
    </section>
  );
}
