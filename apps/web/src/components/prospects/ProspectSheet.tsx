"use client";

import { ExternalLink, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { Cite } from "@/components/dossier/Cite";
import { useDossier } from "@/components/dossier/DossierProvider";
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
import { Skeleton } from "@/components/ui/skeleton";
import { ScoreBar } from "@/components/viz/ScoreBar";
import { api, type ProspectDetail, type ProspectStatus } from "@/lib/api";

export function ProspectSheet({
  companyId,
  onOpenChange,
  onChanged,
}: {
  companyId: string | null;
  onOpenChange: (o: boolean) => void;
  onChanged: () => void;
}) {
  const { id, refresh } = useDossier();
  const [detail, setDetail] = useState<ProspectDetail | null>(null);

  const load = useCallback(
    () =>
      companyId
        ? api.getProspect(id, companyId).then(setDetail, (e: Error) => toast.error(e.message))
        : Promise.resolve(),
    [id, companyId],
  );
  useEffect(() => {
    load();
  }, [load]);

  async function after(message: string) {
    toast(message);
    await Promise.all([load(), refresh()]);
    onChanged();
  }

  const shown = detail && detail.id === companyId ? detail : null;

  return (
    <Sheet open={companyId !== null} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        {!shown ? (
          <div className="space-y-3 p-6">
            <Skeleton className="h-8 w-2/3" />
            <Skeleton className="h-40" />
          </div>
        ) : (
          <>
            <SheetHeader>
              <p className="eyebrow">Prospect · {shown.location ?? "location not evidenced"}</p>
              <SheetTitle className="font-display text-3xl font-normal leading-tight">{shown.name}</SheetTitle>
              <SheetDescription>{shown.description}</SheetDescription>
            </SheetHeader>
            <div className="space-y-7 px-4 pb-8">
              <div className="flex flex-wrap items-center gap-2">
                <Button asChild variant="outline" size="sm">
                  <a href={shown.website} target="_blank" rel="noopener noreferrer">
                    <ExternalLink /> {shown.domain}
                  </a>
                </Button>
                <Select
                  value={shown.status}
                  onValueChange={(v) =>
                    api.updateProspect(id, shown.id, { status: v as ProspectStatus }).then(
                      () => after(`Marked ${v}`),
                      (e: Error) => toast.error(e.message),
                    )
                  }
                >
                  <SelectTrigger size="sm" aria-label="Status" className="w-36">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="new">New</SelectItem>
                    <SelectItem value="shortlisted">Shortlisted</SelectItem>
                    <SelectItem value="excluded">Excluded</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <section aria-labelledby="breakdown">
                <div className="mb-3 flex items-end justify-between">
                  <h3 id="breakdown" className="eyebrow">
                    Lead score
                  </h3>
                  <span className="font-display text-4xl leading-none tabular-nums">
                    {shown.score ?? "—"}
                    <span className="text-lg text-muted-foreground">/100</span>
                  </span>
                </div>
                <ul className="space-y-3">
                  {shown.components.map((c) => (
                    <li key={c.key}>
                      <ScoreBar label={c.label} value={c.points} max={c.max} />
                      <p className="mt-0.5 pl-[calc(9rem+0.75rem)] text-xs leading-relaxed text-muted-foreground max-sm:pl-0">
                        {c.reason}
                        {c.evidence_ids.map((e) => (
                          <Cite key={e} id={e} />
                        ))}
                      </p>
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-[11px] text-muted-foreground">
                  Computed in code from stored evidence (PRD §16). A judgement with no evidence earns no points.
                </p>
              </section>

              <section aria-labelledby="facts">
                <h3 id="facts" className="eyebrow mb-2">
                  What we know
                </h3>
                <dl className="space-y-1.5 text-sm">
                  <div>
                    <dt className="inline text-muted-foreground">Size: </dt>
                    <dd className="inline">{shown.size_signal ?? "unknown — not stated publicly"}</dd>
                  </div>
                  <div>
                    <dt className="inline text-muted-foreground">Technology: </dt>
                    <dd className="inline">{shown.technologies.join(", ") || "no public evidence"}</dd>
                  </div>
                  <div>
                    <dt className="inline text-muted-foreground">Exhibits: </dt>
                    <dd className="inline">
                      {shown.evidence_ids.map((e) => (
                        <Cite key={e} id={e} />
                      ))}
                    </dd>
                  </div>
                </dl>
              </section>

              <section aria-labelledby="people">
                <h3 id="people" className="eyebrow mb-2">
                  Contacts ({shown.contacts_list.length})
                </h3>
                {shown.contacts_list.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No one named on the company&apos;s own public pages.</p>
                ) : (
                  <ul className="divide-y divide-border rounded-md border">
                    {shown.contacts_list.map((c) => (
                      <li key={c.id} className="flex items-center gap-3 px-3 py-2.5 text-sm">
                        <div className="min-w-0 flex-1">
                          <p className="font-medium">{c.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {c.role}
                            {c.email ? ` · ${c.email}` : ""} ·{" "}
                            <a href={c.source_url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">
                              source
                            </a>
                          </p>
                        </div>
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button variant="ghost" size="icon-sm" aria-label={`Delete ${c.name}`}>
                              <Trash2 />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Delete {c.name}?</AlertDialogTitle>
                              <AlertDialogDescription>
                                This permanently deletes this person&apos;s data from Preuve and rescores the company.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Keep</AlertDialogCancel>
                              <AlertDialogAction
                                onClick={() =>
                                  api.deleteContact(id, c.id).then(
                                    () => after(`${c.name} deleted`),
                                    (e: Error) => toast.error(e.message),
                                  )
                                }
                              >
                                Delete permanently
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="mt-2 text-[11px] text-muted-foreground">
                  Only people named on the company&apos;s own public pages, with their name in a verified quote.
                  Emails appear only when printed there.
                </p>
              </section>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
