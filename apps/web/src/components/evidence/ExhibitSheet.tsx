"use client";

import { ExternalLink, MessageSquareQuote } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { useDossier } from "@/components/dossier/DossierProvider";
import { KindMark, VerificationStamp } from "@/components/dossier/marks";
import { SOURCE_LABELS, STANCE } from "@/components/evidence/ExhibitCard";
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
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { api, type Evidence, type EvidenceKind, type Relevance, type Stance } from "@/lib/api";
import { shortDate, sourceHref, sourceName } from "@/lib/format";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[7.5rem_1fr] gap-3 border-b rule py-2.5 text-sm last:border-b-0">
      <dt className="eyebrow pt-0.5">{label}</dt>
      <dd className="min-w-0">{children}</dd>
    </div>
  );
}

export function ExhibitSheet({
  ev,
  label,
  onOpenChange,
}: {
  ev: Evidence | null;
  label: string;
  onOpenChange: (o: boolean) => void;
}) {
  const { id, refresh, analysis } = useDossier();
  const [busy, setBusy] = useState(false);
  const questions = Object.fromEntries((analysis?.unknowns ?? []).map((u) => [u.id, u.question]));

  async function patch(data: Partial<Pick<Evidence, "dismissed" | "kind" | "stance" | "relevance">>, msg: string) {
    if (!ev) return;
    setBusy(true);
    try {
      await api.updateEvidence(id, ev.id, data);
      toast(msg);
      await refresh();
      if (data.dismissed) onOpenChange(false);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet open={ev !== null} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        {ev && (
          <>
            <SheetHeader>
              <div className="flex items-center justify-between gap-3 pr-8">
                <span className="font-mono text-sm font-semibold tracking-wider">{label}</span>
                <VerificationStamp verification={ev.verification} />
              </div>
              <SheetTitle className="sr-only">Exhibit {label}</SheetTitle>
              <SheetDescription className="sr-only">{ev.statement}</SheetDescription>
            </SheetHeader>

            <div className="space-y-6 px-4 pb-8">
              <blockquote className="border-l-2 border-foreground/30 pl-4 font-display text-2xl italic leading-snug">
                &ldquo;{ev.quote}&rdquo;
              </blockquote>
              <p className="text-[0.95rem] leading-relaxed">{ev.statement}</p>

              {(() => {
                const src = sourceHref(id, ev);
                return src.internal ? (
                  <Button asChild variant="outline" size="sm">
                    <Link href={src.href}>
                      <MessageSquareQuote /> {ev.title ?? sourceName(ev)}
                    </Link>
                  </Button>
                ) : (
                  <Button asChild variant="outline" size="sm">
                    <a href={src.href} target="_blank" rel="noopener noreferrer">
                      <ExternalLink /> {ev.title ?? sourceName(ev)}
                    </a>
                  </Button>
                );
              })()}

              <dl>
                <Row label="Kind">
                  <KindMark kind={ev.kind} />
                </Row>
                <Row label="Stance">{STANCE[ev.stance].label}</Row>
                <Row label="Source">
                  {ev.origin === "research" ? SOURCE_LABELS[ev.source_type] : "First-party"} ·{" "}
                  <span className="font-mono text-xs">{sourceName(ev)}</span>
                </Row>
                {ev.company_name && <Row label="Company">{ev.company_name}</Row>}
                {ev.published_at && <Row label="Published">{shortDate(ev.published_at)}</Row>}
                <Row label="Checked">
                  {shortDate(ev.fetched_at)}
                  {ev.origin !== "research"
                    ? ` — ${ev.verification_note ?? "quote found verbatim"}`
                    : ev.verification === "verified"
                    ? " — quote found on the page"
                    : ` — page could not be fetched${ev.verification_note ? ` (${ev.verification_note})` : ""}`}
                </Row>
                <Row label="Answers">
                  {ev.unknown_ids.length === 0 ? (
                    <span className="text-muted-foreground">Not linked to a question</span>
                  ) : (
                    <ul className="list-disc space-y-1 pl-4">
                      {ev.unknown_ids.map((u) => (
                        <li key={u}>{questions[u] ?? "A removed question"}</li>
                      ))}
                    </ul>
                  )}
                </Row>
                {ev.user_edited && ev.original_labels && (
                  <Row label="Relabelled">
                    <span className="text-muted-foreground">
                      originally {ev.original_labels.kind} · {ev.original_labels.stance} · {ev.original_labels.relevance}
                    </span>
                  </Row>
                )}
              </dl>

              <div className="space-y-3 rounded-lg border border-dashed p-4">
                <p className="eyebrow">Your judgement</p>
                <p className="text-xs text-muted-foreground">
                  Relabel if the researcher read this wrong. Originals are kept.
                </p>
                <div className="grid grid-cols-3 gap-2">
                  <Select value={ev.stance} onValueChange={(v) => patch({ stance: v as Stance }, "Stance updated")} disabled={busy}>
                    <SelectTrigger aria-label="Stance" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="supports">Supports</SelectItem>
                      <SelectItem value="contradicts">Argues against</SelectItem>
                      <SelectItem value="neutral">Context</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={ev.kind} onValueChange={(v) => patch({ kind: v as EvidenceKind }, "Kind updated")} disabled={busy}>
                    <SelectTrigger aria-label="Kind" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="fact">Fact</SelectItem>
                      <SelectItem value="inference">Inference</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select
                    value={ev.relevance}
                    onValueChange={(v) => patch({ relevance: v as Relevance }, "Relevance updated")}
                    disabled={busy}
                  >
                    <SelectTrigger aria-label="Relevance" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="high">High</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="low">Low</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="destructive" size="sm" disabled={busy}>
                      Dismiss exhibit
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Dismiss {label}?</AlertDialogTitle>
                      <AlertDialogDescription>
                        It leaves the case and stops counting toward the evidence balance and lead scores.
                        The record is kept for audit.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Keep it</AlertDialogCancel>
                      <AlertDialogAction onClick={() => patch({ dismissed: true }, `${label} dismissed`)}>
                        Dismiss
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
