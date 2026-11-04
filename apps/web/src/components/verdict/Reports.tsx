"use client";

import { Download, FileText, Trash2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { useDossier } from "@/components/dossier/DossierProvider";
import { EmptyState, ErrorState, SectionHeading, SheetSkeleton } from "@/components/dossier/layout";
import { Button } from "@/components/ui/button";
import { RECOMMENDATION } from "@/components/verdict/DecisionPanel";
import { api, type ValidationReport } from "@/lib/api";
import { relativeTime } from "@/lib/format";

const POLL_MS = 2500;

/** Generated validation reports (PRD §44). Generating one first snapshots the current score. */
export function Reports({ onGenerated }: { onGenerated: () => void }) {
  const { id } = useDossier();
  const [rows, setRows] = useState<ValidationReport[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    () =>
      api.listReports(id).then(
        (r) => {
          setRows(r);
          setError(null);
        },
        (e: Error) => setError(e.message),
      ),
    [id],
  );
  useEffect(() => {
    load();
  }, [load]);

  const pending = rows?.some((r) => r.status === "queued" || r.status === "running");
  useEffect(() => {
    if (!pending) return;
    const t = setInterval(load, POLL_MS);
    return () => clearInterval(t);
  }, [pending, load]);

  async function generate() {
    setBusy(true);
    try {
      await api.createReport(id);
      onGenerated(); // the score may have been recomputed
      await load();
      toast("Report queued", { description: "The summary is written on the local model." });
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(rid: string) {
    try {
      await api.deleteReport(rid);
      await load();
    } catch (err) {
      toast.error((err as Error).message);
    }
  }

  return (
    <section className="space-y-5" aria-labelledby="reports-title">
      <SectionHeading
        title={<span id="reports-title">Validation reports</span>}
        kicker="Numbers and verdict come from the score; a model only writes a short cited summary."
      >
        <Button size="sm" variant="outline" onClick={generate} disabled={busy || !!pending}>
          <FileText /> Generate report
        </Button>
      </SectionHeading>
      {error && !rows ? (
        <ErrorState message={error} onRetry={load} />
      ) : !rows ? (
        <SheetSkeleton lines={2} />
      ) : rows.length === 0 ? (
        <EmptyState title="No reports yet.">Generate one to share or print the verdict with its evidence.</EmptyState>
      ) : (
        <ol className="sheet divide-y divide-border overflow-hidden">
          {rows.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">
                  {r.total !== null ? `${r.total}/100` : "—"}
                  {r.recommendation && ` · ${RECOMMENDATION[r.recommendation].label}`}
                </p>
                <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  {r.status === "done"
                    ? `Generated ${relativeTime(r.generated_at ?? r.created_at)} · ${r.summary.length} cited summary lines${r.dropped.length ? ` · ${r.dropped.length} rejected` : ""}`
                    : r.status === "failed"
                      ? `Failed${r.error ? `: ${r.error}` : ""}`
                      : "Writing the summary…"}
                </p>
              </div>
              {r.status === "done" && (
                <>
                  <Button asChild size="sm" variant="ghost">
                    <Link href={`/reports/${r.id}`}>Open</Link>
                  </Button>
                  <Button asChild size="sm" variant="ghost">
                    <a href={api.reportMarkdownUrl(r.id)} download>
                      <Download /> .md
                    </a>
                  </Button>
                </>
              )}
              <Button variant="ghost" size="icon" aria-label="Delete report" onClick={() => remove(r.id)}>
                <Trash2 />
              </Button>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
