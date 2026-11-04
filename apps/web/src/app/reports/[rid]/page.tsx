"use client";

import { ArrowLeft, Download, Printer } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { ErrorState, SheetSkeleton } from "@/components/dossier/layout";
import { Button } from "@/components/ui/button";
import { ReportMarkdown } from "@/components/verdict/ReportMarkdown";
import { api, type ValidationReport } from "@/lib/api";

/** A validation report on its own page, laid out to print (browser "Save as PDF"). */
export default function ReportPage() {
  const { rid } = useParams<{ rid: string }>();
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    () =>
      api.getReport(rid).then(
        (r) => {
          setReport(r);
          setError(null);
        },
        (e: Error) => setError(e.message),
      ),
    [rid],
  );
  useEffect(() => {
    load();
  }, [load]);

  return (
    <main className="mx-auto w-full max-w-3xl px-4 pb-24 pt-8 sm:px-6 print:max-w-none print:p-0">
      <div className="mb-6 flex flex-wrap items-center gap-2 print:hidden">
        {report && (
          <Button asChild variant="ghost" size="sm">
            <Link href={`/ideas/${report.idea_id}/verdict`}>
              <ArrowLeft /> Back to the verdict
            </Link>
          </Button>
        )}
        <div className="flex-1" />
        {report?.status === "done" && (
          <>
            <Button variant="outline" size="sm" onClick={() => window.print()}>
              <Printer /> Print / PDF
            </Button>
            <Button asChild variant="outline" size="sm">
              <a href={api.reportMarkdownUrl(report.id)} download>
                <Download /> Markdown
              </a>
            </Button>
          </>
        )}
      </div>

      {error && !report ? (
        <ErrorState message={error} onRetry={load} />
      ) : !report ? (
        <SheetSkeleton lines={10} />
      ) : report.status !== "done" ? (
        <ErrorState
          message={report.status === "failed" ? `Report failed: ${report.error ?? "unknown error"}` : "Still writing this report…"}
          onRetry={load}
        />
      ) : (
        <div className="sheet p-6 sm:p-10 print:border-0 print:p-0 print:shadow-none">
          <ReportMarkdown content={report.content} />
          {report.dropped.some((d) => d.statement) && (
            <details className="mt-8 border-t rule pt-4 text-xs text-muted-foreground print:hidden">
              <summary className="cursor-pointer">
                {report.dropped.filter((d) => d.statement).length} summary sentences rejected by the checks
              </summary>
              <ul className="mt-2 space-y-1">
                {report.dropped
                  .filter((d) => d.statement)
                  .map((d, i) => (
                    <li key={i}>
                      &ldquo;{d.statement}&rdquo; — {d.reason}
                    </li>
                  ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </main>
  );
}
