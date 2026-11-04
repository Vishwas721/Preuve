"use client";

import { AlertTriangle, Check, FileSearch, ListChecks, Loader2, Sparkles, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { Cite, ClaimList } from "@/components/dossier/Cite";
import { useDossier } from "@/components/dossier/DossierProvider";
import { EmptyState, ErrorState } from "@/components/dossier/layout";
import { Stamp } from "@/components/dossier/marks";
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { api, type Interview, type InterviewExtraction, type InterviewStatus } from "@/lib/api";
import { relativeTime, shortDate } from "@/lib/format";

const POLL_MS = 2500;

const FIELDS: [keyof Omit<InterviewExtraction, "answered_unknowns" | "willingness_to_pay">, string][] = [
  ["problem", "Problem"],
  ["workflow", "Workflow today"],
  ["frequency", "Frequency"],
  ["cost", "Cost"],
  ["alternatives", "Alternatives"],
  ["trigger", "Trigger"],
  ["buyer", "Buyer"],
  ["decision_process", "Decision process"],
  ["objections", "Objections"],
  ["desired_solution", "Desired solution"],
];

const STATUS: Record<InterviewStatus, string> = { planned: "Planned", done: "Done", cancelled: "Cancelled" };

export function InterviewDesk({ interviewId, onChanged }: { interviewId: string; onChanged: () => void }) {
  const { id, refresh, evidenceById } = useDossier();
  const [iv, setIv] = useState<Interview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [kind, setKind] = useState<"live" | "post">("live");
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    () =>
      api.getInterview(id, interviewId).then(
        (x) => {
          setIv(x);
          setError(null);
        },
        (e: Error) => setError(e.message),
      ),
    [id, interviewId],
  );
  useEffect(() => {
    load();
  }, [load]);

  const working = !!iv && [iv.guide_state, iv.extraction_state].some((s) => s === "queued" || s === "running");
  useEffect(() => {
    if (!working) return;
    const t = setInterval(load, POLL_MS);
    return () => clearInterval(t);
  }, [working, load]);

  const missing = !!iv?.evidence_ids.some((e) => !evidenceById[e]);
  useEffect(() => {
    if (iv?.extraction_state === "done" && missing) refresh();
  }, [iv?.extraction_state, missing, refresh]);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!iv || iv.id !== interviewId) return <Skeleton className="h-96" />;

  async function act(fn: () => Promise<Interview | void>, done?: string) {
    setBusy(true);
    try {
      const out = await fn();
      if (out) setIv(out);
      if (done) toast(done);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
      onChanged();
    }
  }

  const exhibitFor = (quote: string) =>
    iv.evidence_ids.find((eid) => evidenceById[eid]?.quote.trim() === quote.trim());
  const guide = iv.guide;
  const ex = iv.extraction;

  return (
    <article className="space-y-5" aria-label={`Interview with ${iv.interviewee_name}`}>
      {/* ---- header ---- */}
      <section className="sheet flex flex-wrap items-start gap-4 p-5">
        <div className="min-w-0 flex-1 basis-64">
          <p className="eyebrow">
            Interview {iv.scheduled_at ? `· ${shortDate(iv.scheduled_at)} ${new Date(iv.scheduled_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "· not scheduled"}
          </p>
          <h3 className="font-display text-3xl leading-tight">{iv.interviewee_name}</h3>
          <p className="text-sm text-ink-soft">
            {[iv.interviewee_role, iv.company_name].filter(Boolean).join(" · ") || "Role unknown"}
          </p>
          {iv.scheduling_note && <p className="mt-2 text-sm text-muted-foreground">{iv.scheduling_note}</p>}
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={iv.status}
            onValueChange={(v) => act(() => api.updateInterview(id, iv.id, { status: v as InterviewStatus }), "Status updated")}
          >
            <SelectTrigger aria-label="Interview status" className="w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(Object.keys(STATUS) as InterviewStatus[]).map((s) => (
                <SelectItem key={s} value={s}>
                  {STATUS[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="Delete interview" disabled={busy}>
                <Trash2 />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete this interview?</AlertDialogTitle>
                <AlertDialogDescription>Its notes and the exhibits taken from them are removed.</AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() =>
                    act(async () => {
                      await api.deleteInterview(id, iv.id);
                      await refresh();
                    }, "Interview deleted")
                  }
                >
                  Delete
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </section>

      {iv.error && <ErrorState message={iv.error} />}

      {/* ---- guide ---- */}
      <section className="sheet space-y-4 p-5" aria-label="Interview guide">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="eyebrow">Guide</p>
            <p className="text-sm text-muted-foreground">Questions for the open unknowns only. Learn, don’t lead.</p>
          </div>
          <Button
            variant={guide ? "outline" : "default"}
            size="sm"
            disabled={busy || iv.guide_state === "queued" || iv.guide_state === "running"}
            onClick={() => act(() => api.generateGuide(id, iv.id))}
          >
            {iv.guide_state === "queued" || iv.guide_state === "running" ? <Loader2 className="animate-spin" /> : <ListChecks />}
            {guide ? "Rewrite guide" : "Write guide"}
          </Button>
        </div>
        {!guide ? (
          iv.guide_state === "queued" || iv.guide_state === "running" ? (
            <p className="text-sm text-muted-foreground" aria-live="polite">Writing questions from the open unknowns…</p>
          ) : null
        ) : (
          <>
            <div>
              <p className="eyebrow mb-2">Already known</p>
              {guide.known.length ? <ClaimList claims={guide.known} /> : <p className="text-sm text-muted-foreground">No evidence found.</p>}
            </div>
            {guide.questions.length === 0 ? (
              <p className="text-sm text-muted-foreground">{guide.note ?? "No questions were written."}</p>
            ) : (
              <ol className="space-y-4">
                {guide.questions.map((q, i) => (
                  <li key={i} className="grid grid-cols-[1.75rem_minmax(0,1fr)] gap-2">
                    <span className="font-mono text-xs text-muted-foreground">Q{String(i + 1).padStart(2, "0")}</span>
                    <div className="space-y-1.5">
                      <p className="text-xs text-muted-foreground">Unknown: {q.unknown}</p>
                      <p className="font-display text-[1.2rem] leading-snug">“{q.question}”</p>
                      {q.flags.map((f) => (
                        <p key={f} className="flex items-center gap-1.5 text-xs text-status-warning-ink">
                          <AlertTriangle className="size-3.5" aria-hidden /> {f}
                        </p>
                      ))}
                      {q.follow_ups.length > 0 && (
                        <ul className="space-y-1 border-l pl-3 text-sm text-ink-soft">
                          {q.follow_ups.map((f, j) => (
                            <li key={j}>
                              Follow-up: {f}
                              {(q.follow_up_flags[j] ?? []).length > 0 && (
                                <span className="ml-2 text-xs text-status-warning-ink">· {q.follow_up_flags[j][0]}</span>
                              )}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            )}
            {(guide.uncovered ?? []).length > 0 && (
              <p className="text-xs text-muted-foreground">
                No question yet for: {guide.uncovered!.map((u) => u.unknown).join(" · ")}
              </p>
            )}
          </>
        )}
      </section>

      {/* ---- notes ---- */}
      <section className="sheet space-y-4 p-5" aria-label="Notes">
        <p className="eyebrow">Notes</p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            act(async () => {
              const out = await api.addInterviewNote(id, iv.id, { text: note, kind });
              setNote("");
              return out;
            });
          }}
          className="space-y-2"
        >
          <Textarea
            aria-label="New note"
            rows={4}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Write down what they say, in their words where you can."
          />
          <div className="flex flex-wrap items-center gap-2">
            <ToggleGroup type="single" variant="outline" size="sm" value={kind} onValueChange={(v) => v && setKind(v as "live" | "post")} aria-label="Note type">
              <ToggleGroupItem value="live">During the call</ToggleGroupItem>
              <ToggleGroupItem value="post">Afterwards</ToggleGroupItem>
            </ToggleGroup>
            <Button type="submit" size="sm" variant="outline" disabled={busy || !note.trim()} className="ml-auto">
              Add note
            </Button>
          </div>
        </form>
        {iv.notes.length === 0 ? (
          <p className="text-sm text-muted-foreground">No notes yet.</p>
        ) : (
          <ol className="space-y-3">
            {iv.notes.map((n) => (
              <li key={n.id} className="group rounded-md border bg-background/50 p-3">
                <div className="mb-1 flex items-center justify-between font-mono text-[11px] text-muted-foreground">
                  <span>
                    {n.kind === "live" ? "during the call" : "afterwards"} · {relativeTime(n.created_at)}
                  </span>
                  <button
                    onClick={() => act(() => api.deleteInterviewNote(id, iv.id, n.id))}
                    aria-label="Delete note"
                    className="opacity-60 hover:opacity-100"
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </div>
                <p className="whitespace-pre-wrap text-[0.95rem] leading-relaxed [overflow-wrap:anywhere]">{n.text}</p>
              </li>
            ))}
          </ol>
        )}
      </section>

      {/* ---- extraction ---- */}
      <section className="sheet space-y-4 p-5" aria-label="Extraction">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="eyebrow">What we learned</p>
            <p className="text-sm text-muted-foreground">
              Pulled from the notes on your local model. Only exact quotes become exhibits.
            </p>
          </div>
          <Button
            size="sm"
            variant={ex ? "outline" : "default"}
            disabled={busy || iv.notes.length === 0 || iv.extraction_state === "queued" || iv.extraction_state === "running"}
            onClick={() => act(() => api.extractInterview(id, iv.id))}
          >
            {iv.extraction_state === "queued" || iv.extraction_state === "running" ? <Loader2 className="animate-spin" /> : <FileSearch />}
            {ex ? "Extract again" : "Extract"}
          </Button>
        </div>
        {!ex ? (
          iv.extraction_state === "queued" || iv.extraction_state === "running" ? (
            <p className="text-sm text-muted-foreground" aria-live="polite">Reading the notes…</p>
          ) : (
            <EmptyState title="Nothing extracted yet.">Add notes, then extract.</EmptyState>
          )
        ) : (
          <>
            <dl className="divide-y divide-border rounded-lg border">
              {FIELDS.map(([key, label]) => {
                const item = ex[key];
                const cite = item.quote ? exhibitFor(item.quote) : undefined;
                return (
                  <div key={key} className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)] gap-3 px-3 py-2.5 text-sm">
                    <dt className="text-muted-foreground">{label}</dt>
                    <dd className="min-w-0">
                      {!item.value && !item.quote ? (
                        <span className="text-muted-foreground">Not covered</span>
                      ) : (
                        <>
                          <span className="font-medium">{item.value || "—"}</span>
                          {item.quote ? (
                            <span className="block font-display text-[15px] italic text-ink-soft">
                              “{item.quote}”{cite && <Cite id={cite} />}
                            </span>
                          ) : (
                            <span className="block text-xs text-muted-foreground">no exact quote: not stored as evidence</span>
                          )}
                        </>
                      )}
                    </dd>
                  </div>
                );
              })}
            </dl>

            <div>
              <p className="eyebrow mb-2">Answers to open unknowns</p>
              {ex.answered_unknowns.length === 0 ? (
                <p className="text-sm text-muted-foreground">The notes don’t clearly answer any open unknown.</p>
              ) : (
                <ul className="space-y-3">
                  {ex.answered_unknowns.map((a) => (
                    <li key={a.unknown_id} className="rounded-md border p-3">
                      <p className="text-xs text-muted-foreground">{a.unknown}</p>
                      <p className="mt-1 text-sm">{a.answer}</p>
                      <p className="mt-1 font-display text-[15px] italic text-ink-soft">
                        “{a.quote}”{a.evidence_id && evidenceById[a.evidence_id] && <Cite id={a.evidence_id} />}
                      </p>
                      <div className="mt-2 flex items-center gap-2">
                        {a.confirmed ? (
                          <Stamp tone="good">
                            <Check className="size-3" aria-hidden /> Answered
                          </Stamp>
                        ) : (
                          <>
                            <span className="inline-flex items-center gap-1 rounded-full border border-dashed px-2 py-0.5 text-[11px] text-muted-foreground">
                              <Sparkles className="size-3" aria-hidden /> AI proposal
                            </span>
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={busy}
                              onClick={() =>
                                act(async () => {
                                  const out = await api.confirmAnswered(id, iv.id, a.unknown_id);
                                  await refresh();
                                  return out;
                                }, "Marked as answered")
                              }
                            >
                              <Check /> Confirm answer
                            </Button>
                          </>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {iv.dropped.length > 0 && (
              <div className="rounded-md border border-dashed p-3 text-sm">
                <p className="eyebrow mb-1">Not stored ({iv.dropped.length})</p>
                <p className="mb-2 text-xs text-muted-foreground">Quoted words that aren’t in your notes were dropped.</p>
                <ul className="space-y-1">
                  {iv.dropped.map((d, i) => (
                    <li key={i} className="text-muted-foreground line-through decoration-muted-foreground/50">
                      “{d.quote}”
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </section>
    </article>
  );
}
