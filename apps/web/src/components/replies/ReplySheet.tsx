"use client";

import { CalendarPlus, Loader2, RotateCcw, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { Cite } from "@/components/dossier/Cite";
import { useDossier } from "@/components/dossier/DossierProvider";
import { ErrorState } from "@/components/dossier/layout";
import { ActionStamp, Highlighted, SentimentMark, SIGNAL_LABELS } from "@/components/replies/marks";
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
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type Reply } from "@/lib/api";
import { relativeTime, shortDate } from "@/lib/format";

const POLL_MS = 2500;

export function ReplySheet({
  replyId,
  onOpenChange,
  onChanged,
}: {
  replyId: string | null;
  onOpenChange: (o: boolean) => void;
  onChanged: () => void;
}) {
  const { id, refresh, evidenceById } = useDossier();
  const router = useRouter();
  const [r, setR] = useState<Reply | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    () => (replyId ? api.getReply(id, replyId).then(setR, (e: Error) => toast.error(e.message)) : Promise.resolve()),
    [id, replyId],
  );
  useEffect(() => {
    load();
  }, [load]);

  const working = r?.status === "queued" || r?.status === "analyzing";
  useEffect(() => {
    if (!working) return;
    const t = setInterval(() => {
      load();
      onChanged();
    }, POLL_MS);
    return () => clearInterval(t);
  }, [working, load, onChanged]);

  // Once a reply is classified, its exhibits exist: reload the dossier so citations resolve.
  const missing = !!r?.evidence_ids.some((e) => !evidenceById[e]);
  useEffect(() => {
    if (r?.status === "done" && missing) refresh();
  }, [r?.status, missing, refresh]);

  const shown = r && r.id === replyId ? r : null;
  const c = shown?.classification;

  async function act(fn: () => Promise<unknown>, done: string) {
    setBusy(true);
    try {
      await fn();
      toast(done);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
      onChanged();
    }
  }

  // Which exhibit holds a signal's quote (same words).
  const exhibitFor = (quote: string) =>
    shown?.evidence_ids.find((eid) => evidenceById[eid]?.quote.trim() === quote.trim());

  return (
    <Sheet open={replyId !== null} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
        {!shown ? (
          <div className="space-y-3 p-6">
            <Skeleton className="h-8 w-2/3" />
            <Skeleton className="h-48" />
          </div>
        ) : (
          <>
            <SheetHeader>
              <p className="eyebrow">
                Reply · {shown.channel === "imap" ? "from the mailbox" : "pasted"} · {shortDate(shown.received_at)}
              </p>
              <SheetTitle className="font-display text-3xl font-normal leading-tight">
                {shown.from_name || shown.from_email || "Unknown sender"}
              </SheetTitle>
              <SheetDescription>
                {shown.company_name ?? "No company linked"}
                {shown.from_email ? ` · ${shown.from_email}` : ""}
              </SheetDescription>
            </SheetHeader>

            <div className="space-y-6 px-4 pb-8">
              <div className="flex flex-wrap items-center gap-3">
                <ActionStamp action={c?.recommended_action.value} optOut={shown.opt_out} />
                {c && <SentimentMark sentiment={c.sentiment} />}
                {shown.opt_out && (
                  <span className="text-xs text-muted-foreground">Added to Do not contact automatically.</span>
                )}
              </div>

              {shown.original && (
                <details className="rounded-md border px-3 py-2 text-sm">
                  <summary className="cursor-pointer text-muted-foreground">
                    In reply to “{shown.original.subject}”
                    {shown.original.sent_at ? `, sent ${relativeTime(shown.original.sent_at)}` : ""}
                  </summary>
                  <p className="mt-2 whitespace-pre-wrap text-ink-soft">{shown.original.body}</p>
                </details>
              )}

              <section>
                <p className="eyebrow mb-2">Their words</p>
                <blockquote className="whitespace-pre-wrap border-l-2 border-foreground/30 pl-4 font-display text-[1.2rem] leading-relaxed [overflow-wrap:anywhere]">
                  <Highlighted
                    text={shown.raw_text}
                    quotes={shown.evidence_ids.map((e) => evidenceById[e]?.quote ?? "").filter(Boolean)}
                  />
                </blockquote>
              </section>

              {working ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
                  <Loader2 className="size-4 animate-spin" aria-hidden /> Classifying on the local model…
                </div>
              ) : shown.status === "failed" ? (
                <ErrorState message={shown.error ?? "Classification failed."} />
              ) : c ? (
                <section>
                  <p className="eyebrow mb-2">What they said</p>
                  <dl className="divide-y divide-border rounded-lg border">
                    {SIGNAL_LABELS.map(([key, label]) => {
                      const item = c[key];
                      const empty = !item.quote && (item.value === "" || item.value === "unclear" || item.value === "unknown");
                      const ex = item.quote ? exhibitFor(item.quote) : undefined;
                      return (
                        <div key={key} className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)] gap-3 px-3 py-2.5 text-sm">
                          <dt className="text-muted-foreground">{label}</dt>
                          <dd className="min-w-0">
                            {empty ? (
                              <span className="text-muted-foreground">Not said</span>
                            ) : (
                              <>
                                <span className="font-medium">{item.value || "—"}</span>
                                {item.quote && (
                                  <span className="block font-display text-[15px] italic text-ink-soft">
                                    “{item.quote}”{ex && <Cite id={ex} />}
                                  </span>
                                )}
                                {!item.quote && item.value && (
                                  <span className="block text-xs text-muted-foreground">no exact quote: not stored as evidence</span>
                                )}
                              </>
                            )}
                          </dd>
                        </div>
                      );
                    })}
                  </dl>
                  <p className="mt-2 text-xs text-muted-foreground">
                    Recommended: {c.recommended_action.reason} Labels come from the local model; the quotes are checked
                    word for word against the reply.
                  </p>
                </section>
              ) : null}

              {shown.dropped.length > 0 && (
                <section className="rounded-md border border-dashed p-3 text-sm">
                  <p className="eyebrow mb-1">Not stored ({shown.dropped.length})</p>
                  <p className="mb-2 text-xs text-muted-foreground">
                    The model quoted words that aren’t in the reply, so these were dropped.
                  </p>
                  <ul className="space-y-1">
                    {shown.dropped.map((d, i) => (
                      <li key={i} className="text-muted-foreground line-through decoration-muted-foreground/50">
                        “{d.quote}”
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              <div className="flex flex-wrap gap-2 border-t rule pt-4">
                {!shown.opt_out && (
                  <Button
                    disabled={busy}
                    onClick={() =>
                      act(async () => {
                        const iv = await api.createInterview(id, {
                          contact_id: shown.contact_id,
                          response_id: shown.id,
                          interviewee_name: shown.contact_id ? "" : shown.from_name || shown.from_email || "",
                          company_name: shown.company_name ?? "",
                        });
                        router.push(`/ideas/${id}/interviews?i=${iv.id}`);
                      }, "Interview planned")
                    }
                  >
                    <CalendarPlus /> Plan an interview
                  </Button>
                )}
                <Button variant="outline" disabled={busy || working} onClick={() => act(() => api.reanalyzeReply(id, shown.id).then(load), "Reclassifying")}>
                  <RotateCcw /> Reclassify
                </Button>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="ghost" className="ml-auto" disabled={busy}>
                      <Trash2 /> Delete
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Delete this reply?</AlertDialogTitle>
                      <AlertDialogDescription>
                        The reply and the {shown.evidence_ids.length} exhibits taken from it are removed. A
                        do-not-contact entry stays.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={() =>
                          act(async () => {
                            await api.deleteReply(id, shown.id);
                            onOpenChange(false);
                            await refresh();
                          }, "Reply deleted")
                        }
                      >
                        Delete
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
