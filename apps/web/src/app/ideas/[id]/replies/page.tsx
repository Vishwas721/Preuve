"use client";

import { ChevronRight, ClipboardPaste, Inbox, RefreshCw } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { useDossier } from "@/components/dossier/DossierProvider";
import { EmptyState, ErrorState, SectionHeading, SheetSkeleton } from "@/components/dossier/layout";
import { ActionStamp, SentimentMark } from "@/components/replies/marks";
import { PasteReplySheet } from "@/components/replies/PasteReplySheet";
import { ReplySheet } from "@/components/replies/ReplySheet";
import { Button } from "@/components/ui/button";
import { EvidenceBalance } from "@/components/viz/EvidenceBalance";
import { api, type InboxStatus, type ReplyDashboard, type ReplySummary } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const POLL_MS = 2500;

export default function RepliesPage() {
  const { id, refresh } = useDossier();
  const params = useSearchParams();
  const [rows, setRows] = useState<ReplySummary[] | null>(null);
  const [dash, setDash] = useState<ReplyDashboard | null>(null);
  const [inbox, setInbox] = useState<InboxStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(params.get("r"));
  const [pasting, setPasting] = useState(false);
  const [checkingUntil, setCheckingUntil] = useState(0);

  const load = useCallback(
    () =>
      Promise.all([api.listReplies(id), api.replyDashboard(id), api.inboxStatus()]).then(
        ([r, d, i]) => {
          setRows(r);
          setDash(d);
          setInbox(i);
          setError(null);
        },
        (e: Error) => setError(e.message),
      ),
    [id],
  );
  useEffect(() => {
    load();
  }, [load]);

  const working = !!rows?.some((r) => r.status === "queued" || r.status === "analyzing");
  const [now, setNow] = useState(0);
  const checking = now < checkingUntil;
  useEffect(() => {
    if (!working && !checking) return;
    const t = setInterval(() => {
      setNow(Date.now());
      load();
    }, POLL_MS);
    return () => clearInterval(t);
  }, [working, checking, load]);

  const onChanged = useCallback(() => {
    load();
  }, [load]);

  if (error && !rows) return <ErrorState message={error} onRetry={load} />;
  if (!rows || !dash) return <SheetSkeleton lines={6} />;

  return (
    <div className="space-y-6">
      <SectionHeading
        title="Replies"
        kicker="What prospects actually wrote back. Only their exact words become evidence."
      >
        {inbox?.enabled && (
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              api.checkInbox().then(
                () => {
                  toast("Checking the mailbox…");
                  setCheckingUntil(Date.now() + 20_000);
                  setNow(Date.now());
                },
                (e: Error) => toast.error(e.message),
              )
            }
          >
            <RefreshCw className={cn(checking && "animate-spin")} /> Check inbox now
          </Button>
        )}
        <Button size="sm" onClick={() => setPasting(true)}>
          <ClipboardPaste /> Paste a reply
        </Button>
      </SectionHeading>

      <MailboxStrip inbox={inbox} />
      <DashboardPanel d={dash} onOpen={setOpenId} />

      {rows.length === 0 ? (
        <EmptyState title="No replies yet.">
          {inbox?.enabled
            ? "Replies to your outreach are picked up from the mailbox every few minutes. You can also paste one."
            : "Paste replies as they arrive, or set IMAP_HOST in .env to read them from the mailbox."}
        </EmptyState>
      ) : (
        <ol className="sheet divide-y divide-border overflow-hidden" aria-label="Replies">
          {rows.map((r) => {
            const c = r.classification;
            return (
              <li key={r.id}>
                <button
                  onClick={() => setOpenId(r.id)}
                  className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-4 px-4 py-3.5 text-left transition-colors hover:bg-accent/50 focus-visible:bg-accent focus-visible:outline-none sm:grid-cols-[minmax(0,1fr)_9rem_8rem_auto]"
                >
                  <span className="min-w-0">
                    <span className="block truncate font-display text-xl leading-tight">
                      {r.from_name || r.from_email || "Unknown sender"}
                    </span>
                    <span className="block truncate text-sm text-ink-soft">
                      {c?.pain.quote ? `“${c.pain.quote}”` : r.subject || "—"}
                    </span>
                    <span className="block font-mono text-[11px] text-muted-foreground">
                      {r.channel === "imap" ? "mailbox" : "pasted"} · {relativeTime(r.received_at)}
                      {r.status === "queued" || r.status === "analyzing" ? " · classifying…" : ""}
                      {r.status === "failed" ? " · classification failed" : ""}
                    </span>
                  </span>
                  <span className="hidden sm:block">{c && <SentimentMark sentiment={c.sentiment} />}</span>
                  <span className="hidden sm:block">
                    <ActionStamp action={c?.recommended_action.value} optOut={r.opt_out} />
                  </span>
                  <ChevronRight className="size-4 text-muted-foreground" aria-hidden />
                </button>
              </li>
            );
          })}
        </ol>
      )}

      <PasteReplySheet
        open={pasting}
        onOpenChange={setPasting}
        onCreated={(r) => {
          setPasting(false);
          setOpenId(r.id);
          load();
        }}
      />
      <ReplySheet
        replyId={openId}
        onOpenChange={(o) => !o && setOpenId(null)}
        onChanged={() => {
          onChanged();
          refresh();
        }}
      />
    </div>
  );
}

function MailboxStrip({ inbox }: { inbox: InboxStatus | null }) {
  if (!inbox) return null;
  const last = inbox.last_poll;
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border px-4 py-3 text-sm",
        !inbox.enabled && "border-dashed",
      )}
    >
      <span className="inline-flex min-w-0 items-center gap-2">
        <Inbox className="size-4 shrink-0 text-muted-foreground" aria-hidden />
        {inbox.enabled ? (
          <span className="min-w-0 font-mono text-xs [overflow-wrap:anywhere]">{inbox.mailbox}</span>
        ) : (
          <span className="text-muted-foreground">Mailbox polling is off (set IMAP_HOST in .env).</span>
        )}
      </span>
      {last && (
        <span className="font-mono text-xs text-muted-foreground">
          checked {relativeTime(last.at)} · {last.reply} new · {last.bounce} bounces · {last.unmatched} not outreach
          {last.error ? ` · ${last.error}` : ""}
        </span>
      )}
      <span className="ml-auto text-xs text-muted-foreground">Read-only · processed on your local model</span>
    </div>
  );
}

function Tile({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="flex flex-col-reverse">
      <dt className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
        {hint && <span className="block normal-case tracking-normal">{hint}</span>}
      </dt>
      <dd className="font-display text-3xl leading-none tabular-nums">{value}</dd>
    </div>
  );
}

function DashboardPanel({ d, onOpen }: { d: ReplyDashboard; onOpen: (id: string) => void }) {
  const rate = d.reply_rate === null ? "—" : `${Math.round(d.reply_rate * 100)}%`;
  return (
    <section className="sheet grid gap-6 p-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]" aria-label="Response dashboard">
      <div className="space-y-5">
        <dl className="grid grid-cols-3 gap-x-4 gap-y-5 font-mono text-xs sm:grid-cols-4">
          <Tile label="Sent" value={d.sent} />
          <Tile label="Replies" value={d.replies} hint={`${rate} reply rate`} />
          <Tile label="Problem confirmed" value={d.problem_confirmed} />
          <Tile label="Interview worth it" value={d.interview_recommended} />
          <Tile label="Interviews done" value={d.interviews_done} />
          <Tile label="Said they'd pay" value={d.stated_strong} />
          <Tile label="Pilot or better" value={d.pilot_or_better} hint="actual commitments" />
          <Tile label="Opted out" value={d.opt_outs} />
        </dl>
        <div>
          <p className="eyebrow mb-2">Tone of replies</p>
          <EvidenceBalance
            supports={d.positive}
            contradicts={d.negative}
            neutral={d.neutral}
            labels={{ supports: "Positive", contradicts: "Negative", neutral: "Neutral" }}
          />
        </div>
      </div>
      <div className="space-y-4">
        <div>
          <p className="eyebrow mb-2">Most common pain, in their words</p>
          {d.top_pains.length === 0 ? (
            <p className="text-sm text-muted-foreground">No evidence found.</p>
          ) : (
            <ul className="space-y-2">
              {d.top_pains.map((p) => (
                <li key={p.id}>
                  <button onClick={() => onOpen(p.id)} className="text-left">
                    <span className="font-display text-[1.05rem] italic leading-snug hover:underline">“{p.quote}”</span>
                    <span className="ml-2 font-mono text-[11px] text-muted-foreground">{p.from}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <CountList title="How often" items={d.frequencies} />
          <CountList title="Used today" items={d.current_solutions} />
        </div>
      </div>
    </section>
  );
}

function CountList({ title, items }: { title: string; items: { value: string; count: number }[] }) {
  return (
    <div>
      <p className="eyebrow mb-1.5">{title}</p>
      {items.length === 0 ? (
        <p className="text-muted-foreground">Not said yet.</p>
      ) : (
        <ul className="space-y-1">
          {items.map((i) => (
            <li key={i.value} className="flex justify-between gap-2">
              <span className="truncate">{i.value}</span>
              <span className="font-mono text-xs text-muted-foreground">{i.count}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
