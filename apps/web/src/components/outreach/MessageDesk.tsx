"use client";

import { AlertTriangle, ExternalLink, Loader2, MailX, RotateCcw, Send, Sparkles, Undo2, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { ClaimList } from "@/components/dossier/Cite";
import { useDossier } from "@/components/dossier/DossierProvider";
import { EmptyState, ErrorState } from "@/components/dossier/layout";
import { VerificationStamp } from "@/components/dossier/marks";
import { StatusStamp } from "@/components/outreach/StatusStamp";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { api, type OutreachMessage, type OutreachSettings } from "@/lib/api";
import { domain, relativeTime, shortDate } from "@/lib/format";

/** PRD §42: prospect, why selected, evidence, subject, message — Edit / Approve & send / Reject. */
export function MessageDesk({
  messageId,
  version,
  settings,
  onChanged,
}: {
  messageId: string;
  /** Changes when the ledger sees a newer server copy (e.g. drafting finished). */
  version: string;
  settings: OutreachSettings | null;
  onChanged: () => void;
}) {
  const { id, exhibit } = useDossier();
  const [m, setM] = useState<OutreachMessage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [to, setTo] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);

  const adopt = useCallback((msg: OutreachMessage) => {
    setM(msg);
    setTo(msg.to_email ?? "");
    setSubject(msg.subject);
    setBody(msg.body);
  }, []);

  const load = useCallback(
    () =>
      api.getMessage(id, messageId).then(
        (msg) => {
          adopt(msg);
          setError(null);
        },
        (e: Error) => setError(e.message),
      ),
    [id, messageId, adopt],
  );
  useEffect(() => {
    load();
  }, [load, version]);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!m || m.id !== messageId) return <Skeleton className="h-96" />;

  const editable = m.status === "draft" || m.status === "approved";
  const dirty = (m.to_email ?? "") !== to.trim().toLowerCase() || m.subject !== subject || m.body !== body;
  const canSend = !!settings?.sending_enabled && !!settings.sender_ready;

  async function act<T>(fn: () => Promise<T>, done?: string): Promise<T | undefined> {
    setBusy(true);
    try {
      const r = await fn();
      if (done) toast(done);
      return r;
    } catch (e) {
      toast.error((e as Error).message);
      return undefined;
    } finally {
      setBusy(false);
      onChanged();
    }
  }

  const save = async () => {
    const msg = await api.updateMessage(id, m.id, { to_email: to.trim() || null, subject, body });
    adopt(msg);
    return msg;
  };

  const approve = (andSend: boolean) =>
    act(async () => {
      if (dirty) await save();
      const msg = await api.messageAction(id, m.id, "approve");
      adopt(msg);
      if (andSend) {
        await api.sendCampaign(id, m.campaign_id, [m.id]);
        toast("Approved and queued", { description: "The send job re-checks every safety rule first." });
      } else toast("Approved");
    });

  const action = (a: "reject" | "reopen" | "bounce" | "redraft", done: string) =>
    act(async () => adopt(await api.messageAction(id, m.id, a)), done);

  return (
    <article className="grid gap-5 lg:grid-cols-[minmax(0,19rem)_minmax(0,1fr)]" aria-label={`Message to ${m.to_name}`}>
      {/* ---- the prospect & the evidence ---- */}
      <aside className="space-y-5">
        <section className="sheet space-y-3 p-4">
          <p className="eyebrow">Recipient</p>
          <div>
            <p className="font-display text-2xl leading-tight">{m.to_name}</p>
            {m.prospect && (
              <p className="text-sm text-ink-soft">
                {m.prospect.contact_role ?? "role unknown"} · {m.prospect.name}
              </p>
            )}
          </div>
          {m.prospect && (
            <div className="flex items-center gap-3">
              <span className="font-display text-3xl leading-none tabular-nums">{m.prospect.score ?? "—"}</span>
              <span className="h-1.5 flex-1 rounded-full bg-viz-track" aria-hidden>
                <span className="block h-full rounded-full bg-viz-seq" style={{ width: `${m.prospect.score ?? 0}%` }} />
              </span>
              <span className="font-mono text-[10px] text-muted-foreground">lead score</span>
            </div>
          )}
          {m.prospect?.contact_source_url && (
            <a
              href={m.prospect.contact_source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 font-mono text-[11px] text-muted-foreground underline-offset-4 hover:underline"
            >
              <ExternalLink className="size-3" aria-hidden /> named on {domain(m.prospect.contact_source_url)}
            </a>
          )}
        </section>

        <section className="sheet space-y-3 p-4">
          <p className="eyebrow">Why selected</p>
          {m.why_selected.length ? (
            <ClaimList claims={m.why_selected} />
          ) : (
            <p className="text-sm text-muted-foreground">No evidence found.</p>
          )}
        </section>

        <section className="sheet space-y-3 p-4">
          <p className="eyebrow">Cited in this message</p>
          {m.cited_evidence.length === 0 ? (
            <p className="text-sm text-muted-foreground">No evidence found.</p>
          ) : (
            <ul className="space-y-4">
              {m.cited_evidence.map((e) => (
                <li key={e.id} className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] text-viz-seq">{exhibit(e.id)}</span>
                    <VerificationStamp verification={e.verification} />
                  </div>
                  <blockquote className="font-display text-base italic leading-snug">&ldquo;{e.quote}&rdquo;</blockquote>
                  <a
                    href={e.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block truncate font-mono text-[10px] text-muted-foreground hover:underline"
                  >
                    {domain(e.url)} · fetched {shortDate(e.fetched_at)}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </section>
      </aside>

      {/* ---- the letter ---- */}
      <section className="sheet flex min-w-0 flex-col gap-4 p-5">
        <div className="flex flex-wrap items-center gap-3">
          <StatusStamp status={m.status} />
          <span className="font-mono text-[11px] text-muted-foreground">
            {m.sent_at
              ? `sent ${relativeTime(m.sent_at)}`
              : m.approved_at
                ? `approved ${relativeTime(m.approved_at)}`
                : `updated ${relativeTime(m.updated_at)}`}
            {m.user_edited && " · edited by you"}
          </span>
          {m.status === "draft" && !m.user_edited && !m.draft_error && (
            <span className="inline-flex items-center gap-1 rounded-full border border-dashed px-2 py-0.5 text-[11px] text-muted-foreground">
              <Sparkles className="size-3" aria-hidden /> AI draft — read it before approving
            </span>
          )}
        </div>

        {m.status === "drafting" ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 py-16 text-muted-foreground" aria-live="polite">
            <Loader2 className="size-6 animate-spin" aria-hidden />
            <p className="text-sm">Drafting from verified evidence only…</p>
            {m.stale && (
              <>
                <p className="text-xs">This is taking too long; the job may have been lost.</p>
                <Button variant="outline" size="sm" onClick={() => action("redraft", "Redrafting")} disabled={busy}>
                  <RotateCcw /> Redraft
                </Button>
              </>
            )}
          </div>
        ) : m.redacted_at ? (
          <EmptyState title="Deleted on request.">
            The person’s data was removed on {shortDate(m.redacted_at)}. The record keeps its date, status, cited
            evidence and content hash <code className="font-mono text-[10px] break-all">{m.content_hash}</code>.
          </EmptyState>
        ) : (
          <>
            {m.draft_error && <ErrorState message={m.draft_error} />}
            {m.send_error && m.status !== "sent" && <ErrorState message={m.send_error} />}
            {m.blocked_reason && m.status === "blocked" && <ErrorState message={`Blocked: ${m.blocked_reason}`} />}

            {m.status === "sent" || m.status === "bounced" ? (
              <SentRecord m={m} />
            ) : (
              <div className="space-y-4">
                <div className="grid gap-1.5">
                  <Label htmlFor="m-to">To</Label>
                  <Input
                    id="m-to"
                    type="email"
                    value={to}
                    disabled={!editable || busy}
                    onChange={(e) => setTo(e.target.value)}
                    placeholder="Their work email"
                    className="font-mono"
                  />
                  <p className="text-xs text-muted-foreground">
                    {m.to_email_source === "public_page"
                      ? "Printed on their verified source page."
                      : "No public email was found. Only enter an address you obtained legitimately."}
                  </p>
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="m-subject">Subject</Label>
                  <Input id="m-subject" value={subject} maxLength={200} disabled={!editable || busy} onChange={(e) => setSubject(e.target.value)} />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="m-body">Message</Label>
                  <Textarea
                    id="m-body"
                    rows={11}
                    value={body}
                    disabled={!editable || busy}
                    onChange={(e) => setBody(e.target.value)}
                    className="font-display text-[17px] leading-relaxed"
                  />
                  <p className="text-xs text-muted-foreground">
                    On send, a footer adds your name ({settings?.sender_name || "not set"}), the campaign’s research
                    purpose and a reply-“stop” / unsubscribe line.
                  </p>
                </div>

                {m.checks.length > 0 && (
                  <ul className="space-y-1 rounded-md border border-status-warning/40 bg-status-warning/5 p-3 text-sm" aria-label="Draft checks">
                    {m.checks.map((c) => (
                      <li key={c} className="flex gap-2">
                        <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-status-warning-ink" aria-hidden />
                        {c}
                      </li>
                    ))}
                  </ul>
                )}
                {m.status === "approved" && (
                  <p className="text-xs text-muted-foreground">Editing an approved message sends it back to draft.</p>
                )}
              </div>
            )}

            <div className="mt-auto flex flex-wrap items-center gap-2 border-t rule pt-4">
              {m.status === "draft" && (
                <>
                  <Button onClick={() => approve(true)} disabled={busy || !canSend} title={canSend ? undefined : "Sending is not configured"}>
                    <Send /> Approve &amp; send
                  </Button>
                  <Button variant="outline" onClick={() => approve(false)} disabled={busy}>
                    Approve only
                  </Button>
                  {dirty && (
                    <Button variant="ghost" onClick={() => act(save, "Saved")} disabled={busy}>
                      Save draft
                    </Button>
                  )}
                  <Button variant="ghost" onClick={() => action("redraft", "Redrafting")} disabled={busy}>
                    <RotateCcw /> Redraft
                  </Button>
                  <Button variant="ghost" className="ml-auto" onClick={() => action("reject", "Rejected")} disabled={busy}>
                    <X /> Reject
                  </Button>
                </>
              )}
              {m.status === "approved" && (
                <>
                  <Button
                    onClick={() =>
                      act(() => api.sendCampaign(id, m.campaign_id, [m.id]), "Queued for sending")
                    }
                    disabled={busy || !canSend || dirty}
                  >
                    <Send /> Send now
                  </Button>
                  {dirty && (
                    <Button variant="outline" onClick={() => act(save, "Back to draft — approve again")} disabled={busy}>
                      Save (back to draft)
                    </Button>
                  )}
                  <Button variant="ghost" className="ml-auto" onClick={() => action("reject", "Rejected")} disabled={busy}>
                    <X /> Reject
                  </Button>
                </>
              )}
              {m.status === "rejected" && (
                <Button variant="outline" onClick={() => action("reopen", "Back to draft")} disabled={busy}>
                  <Undo2 /> Reopen as draft
                </Button>
              )}
              {m.status === "sent" && (
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="ghost" disabled={busy}>
                      <MailX /> Record a bounce
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Record a bounce?</AlertDialogTitle>
                      <AlertDialogDescription>
                        Use this when a bounce notice arrived by email. {m.to_email} goes on the suppression list.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction onClick={() => action("bounce", "Bounce recorded")}>Record bounce</AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              )}
            </div>
          </>
        )}
      </section>
    </article>
  );
}

/** Exactly what went out, with its headers and hash (PRD §19: every sent message is stored). */
function SentRecord({ m }: { m: OutreachMessage }) {
  const h = m.sent_headers ?? {};
  return (
    <div className="space-y-3">
      <dl className="grid grid-cols-[4.5rem_1fr] gap-x-3 gap-y-1 font-mono text-[12px]">
        {["From", "To", "Subject", "Date"].map((k) =>
          h[k] ? (
            <div key={k} className="contents">
              <dt className="text-muted-foreground">{k}</dt>
              <dd className="min-w-0 break-words">{h[k]}</dd>
            </div>
          ) : null,
        )}
      </dl>
      <pre className="max-h-[28rem] overflow-auto whitespace-pre-wrap rounded-md border bg-background/60 p-4 font-display text-[16px] leading-relaxed">
        {m.sent_body}
      </pre>
      <p className="font-mono text-[10px] break-all text-muted-foreground">
        sha256 {m.content_hash} · {m.provider_message_id}
      </p>
    </div>
  );
}
