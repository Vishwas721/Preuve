"use client";

import { useDossier } from "@/components/dossier/DossierProvider";
import { SectionHeading } from "@/components/dossier/layout";
import { domain, shortDate } from "@/lib/format";

/** Every research import: what came in, what was verified, what was rejected and why. */
export function ResearchLog() {
  const { research } = useDossier();
  const imports = research?.imports ?? [];
  if (imports.length === 0) return null;
  return (
    <section className="space-y-4" aria-labelledby="log-title">
      <SectionHeading
        title={<span id="log-title">Research log</span>}
        kicker="Each import from Claude Code, as Preuve verified it. Rejected quotes never enter the case."
      />
      <ol className="relative space-y-6 border-l rule pl-6">
        {imports.map((imp) => {
          const c = imp.report.counts;
          const rejected = imp.report.rejected ?? [];
          const dropped = imp.report.dropped_claims ?? [];
          return (
            <li key={imp.id} className="relative">
              <span className="absolute top-1.5 -left-[29px] size-2.5 rounded-full border-2 border-background bg-foreground" />
              <p className="eyebrow">
                {shortDate(imp.created_at)} · method v{imp.method_version} · schema {imp.schema_version}
              </p>
              {imp.status === "done" && c ? (
                <p className="mt-1 text-sm">
                  <span className="font-mono">{c.verified}</span> verified ·{" "}
                  <span className="font-mono">{c.unverifiable}</span> unverifiable ·{" "}
                  <span className="font-mono">{c.rejected}</span> rejected
                  {imp.report.duplicates?.length ? (
                    <span className="text-muted-foreground"> · {imp.report.duplicates.length} already known</span>
                  ) : null}
                </p>
              ) : (
                <p className="mt-1 text-sm capitalize">
                  {imp.status}
                  {imp.error ? ` — ${imp.error}` : ""}
                </p>
              )}
              {(rejected.length > 0 || dropped.length > 0) && (
                <details className="mt-2 text-xs text-muted-foreground">
                  <summary className="cursor-pointer">What didn&apos;t pass verification</summary>
                  <ul className="mt-2 space-y-1 pl-4">
                    {rejected.map((r) => (
                      <li key={r.ref} className="list-disc">
                        Rejected {r.ref}: {r.reason} ({domain(r.url)})
                      </li>
                    ))}
                    {dropped.map((d, i) => (
                      <li key={i} className="list-disc">
                        Dropped claim: {d.statement}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
