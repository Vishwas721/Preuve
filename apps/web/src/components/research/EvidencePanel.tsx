"use client";

import { useState } from "react";

import { btnLink, card, sectionTitle } from "@/components/ui";
import {
  api,
  type Evidence,
  type IdeaResearch,
  type ResearchImport,
  type SourceType,
  type Stance,
} from "@/lib/api";

const STANCES: { key: Stance; label: string; tone: string }[] = [
  { key: "supports", label: "Supports the problem", tone: "border-l-green-600" },
  { key: "contradicts", label: "Argues against it", tone: "border-l-red-600" },
  { key: "neutral", label: "Context", tone: "border-l-black/20 dark:border-l-white/30" },
];

const SOURCE_LABELS: Record<SourceType, string> = {
  job_posting: "Job posting",
  forum: "Forum",
  review: "Review",
  news: "News",
  industry_publication: "Industry publication",
  company_site: "Company site",
  report: "Report",
  directory: "Directory",
  other: "Other",
};

function domain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function Pill({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs bg-black/5 dark:bg-white/10 ${className}`}>
      {children}
    </span>
  );
}

function EvidenceItem({
  ideaId,
  ev,
  tone,
  onChange,
}: {
  ideaId: string;
  ev: Evidence;
  tone: string;
  onChange: () => void;
}) {
  const [error, setError] = useState<string | null>(null);

  async function dismiss() {
    try {
      await api.updateEvidence(ideaId, ev.id, { dismissed: true });
      onChange();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <li id={`ev-${ev.id}`} className={`scroll-mt-6 border-l-4 py-1 pl-3 ${tone}`}>
      <blockquote className="text-sm">&ldquo;{ev.quote}&rdquo;</blockquote>
      <p className="mt-1 text-sm opacity-80">{ev.statement}</p>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {ev.verification === "verified" ? (
          <Pill className="!bg-green-600/10 text-green-700 dark:text-green-400">
            ✓ Quote verified
          </Pill>
        ) : (
          <Pill className="!bg-amber-500/10 text-amber-700 dark:text-amber-300">Unverifiable</Pill>
        )}
        <Pill>{ev.kind === "fact" ? "Fact" : "Inference"}</Pill>
        <Pill>{SOURCE_LABELS[ev.source_type]}</Pill>
        <Pill>{ev.relevance} relevance</Pill>
        {ev.company_name && <Pill>{ev.company_name}</Pill>}
        {ev.user_edited && <Pill>relabelled by you</Pill>}
        <span className="text-xs opacity-50">[{ev.ref}]</span>
      </div>
      <div className="mt-1 flex flex-wrap gap-3 text-xs">
        <a
          href={ev.url}
          target="_blank"
          rel="noopener noreferrer"
          className="underline underline-offset-2 opacity-80 hover:opacity-100"
        >
          {ev.title ? `${ev.title} — ` : ""}
          {domain(ev.url)}
        </a>
        <span className="opacity-50">
          checked {new Date(ev.fetched_at).toLocaleDateString()}
          {ev.published_at ? ` · published ${ev.published_at}` : ""}
        </span>
        <button className={btnLink} onClick={dismiss}>
          Dismiss
        </button>
      </div>
      {ev.verification === "unverifiable" && ev.verification_note && (
        <p className="mt-1 text-xs opacity-60">Why unverifiable: {ev.verification_note}</p>
      )}
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </li>
  );
}

function ImportHistory({ imports }: { imports: ResearchImport[] }) {
  return (
    <details className="mt-4 border-t border-black/10 pt-3 text-sm dark:border-white/15">
      <summary className="cursor-pointer opacity-70">Research imports ({imports.length})</summary>
      <ul className="mt-2 flex flex-col gap-3">
        {imports.map((imp) => {
          const c = imp.report.counts;
          return (
            <li key={imp.id}>
              <div className="opacity-80">
                {new Date(imp.created_at).toLocaleString()} · method v{imp.method_version} ·{" "}
                {imp.status === "done" && c
                  ? `${c.verified} verified, ${c.unverifiable} unverifiable, ${c.rejected} rejected`
                  : imp.status}
                {imp.error ? ` — ${imp.error}` : ""}
              </div>
              {!!imp.report.rejected?.length && (
                <ul className="mt-1 list-disc pl-5 text-xs opacity-70">
                  {imp.report.rejected.map((r) => (
                    <li key={r.ref}>
                      Rejected {r.ref}: {r.reason} ({domain(r.url)})
                    </li>
                  ))}
                </ul>
              )}
              {!!imp.report.dropped_claims?.length && (
                <ul className="mt-1 list-disc pl-5 text-xs opacity-70">
                  {imp.report.dropped_claims.map((d, i) => (
                    <li key={i}>Dropped claim (cited unverified evidence): {d.statement}</li>
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </details>
  );
}

export function EvidencePanel({
  ideaId,
  research,
  onChange,
}: {
  ideaId: string;
  research: IdeaResearch;
  onChange: () => void;
}) {
  const verified = research.evidence.filter((e) => e.verification === "verified");
  const unverifiable = research.evidence.filter((e) => e.verification === "unverifiable");
  const verifying = research.imports.some((i) => i.status === "queued" || i.status === "verifying");

  return (
    <section className={card}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className={sectionTitle}>Evidence</h2>
        <span className="text-xs opacity-60">
          {verified.length} verified · {unverifiable.length} unverifiable
        </span>
      </div>
      <p className="mt-1 text-sm opacity-70">
        Every quote was checked against its source page by Preuve, not just reported by the
        researcher.
      </p>

      {verifying && (
        <p role="status" className="mt-3 text-sm">
          Verifying a research import…
        </p>
      )}

      {research.evidence.length === 0 ? (
        <div className="mt-3 text-sm">
          <p>No evidence found.</p>
          {research.imports.length === 0 && (
            <p className="mt-1 opacity-70">
              To research this idea, run{" "}
              <code className="rounded bg-black/5 px-1 dark:bg-white/10">/research-idea {ideaId}</code>{" "}
              in Claude Code.
            </p>
          )}
        </div>
      ) : (
        <div className="mt-4 flex flex-col gap-5">
          {STANCES.map(({ key, label, tone }) => {
            const items = verified.filter((e) => e.stance === key);
            return (
              <div key={key}>
                <h3 className="text-sm font-medium">
                  {label} <span className="opacity-50">({items.length})</span>
                </h3>
                {items.length === 0 ? (
                  <p className="mt-1 text-sm opacity-60">No evidence found.</p>
                ) : (
                  <ul className="mt-2 flex flex-col gap-4">
                    {items.map((ev) => (
                      <EvidenceItem key={ev.id} ideaId={ideaId} ev={ev} tone={tone} onChange={onChange} />
                    ))}
                  </ul>
                )}
              </div>
            );
          })}

          {unverifiable.length > 0 && (
            <details>
              <summary className="cursor-pointer text-sm font-medium">
                Unverifiable ({unverifiable.length}){" "}
                <span className="font-normal opacity-60">
                  — Preuve couldn&apos;t fetch these pages; treat with caution
                </span>
              </summary>
              <ul className="mt-2 flex flex-col gap-4">
                {unverifiable.map((ev) => (
                  <EvidenceItem
                    key={ev.id}
                    ideaId={ideaId}
                    ev={ev}
                    tone="border-l-amber-500"
                    onChange={onChange}
                  />
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {research.imports.length > 0 && <ImportHistory imports={research.imports} />}
    </section>
  );
}
