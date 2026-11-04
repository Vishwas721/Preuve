"use client";

import { Check, Copy, RefreshCw, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { toast } from "sonner";

import { useDossier } from "@/components/dossier/DossierProvider";
import { ErrorState } from "@/components/dossier/layout";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EvidenceBalance } from "@/components/viz/EvidenceBalance";
import { relativeTime } from "@/lib/format";
import { STATE_LABELS } from "@/lib/states";
import { cn } from "@/lib/utils";

const STEP_LABELS: Record<string, string> = {
  hypothesis: "Structuring the hypothesis and open questions",
  icps: "Proposing candidate customer profiles",
};

function RunStatus() {
  const { analysis, research, startAnalysis } = useDossier();
  const run = analysis?.latest_run;
  const verifying = research?.imports.find((i) => i.status === "queued" || i.status === "verifying");

  if (verifying) {
    return (
      <StatusStrip tone="busy">
        Verifying a research import — Preuve is fetching every cited page and checking each quote.
      </StatusStrip>
    );
  }
  if (run && (run.status === "queued" || run.status === "running")) {
    return (
      <StatusStrip tone="busy">
        {run.status === "queued" ? "Waiting for the worker…" : `${STEP_LABELS[run.step ?? ""] ?? "Working"}…`}
      </StatusStrip>
    );
  }
  if (run?.status === "failed") {
    return (
      <StatusStrip tone="error">
        Analysis failed{run.error ? `: ${run.error}` : "."} Anything generated earlier was kept.{" "}
        <button className="underline underline-offset-4" onClick={() => startAnalysis(run.kind)}>
          Try again
        </button>
      </StatusStrip>
    );
  }
  return null;
}

function StatusStrip({ tone, children }: { tone: "busy" | "error"; children: ReactNode }) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn(
        "relative overflow-hidden rounded-md border px-4 py-2.5 text-sm",
        tone === "busy" ? "border-viz-seq/30 bg-viz-seq/5" : "border-status-critical/40 bg-status-critical/5",
      )}
    >
      {tone === "busy" && (
        <motion.span
          aria-hidden
          className="absolute inset-y-0 left-0 w-1/3 bg-gradient-to-r from-transparent via-viz-seq/15 to-transparent"
          animate={{ x: ["-100%", "300%"] }}
          transition={{ repeat: Infinity, duration: 1.8, ease: "easeInOut" }}
        />
      )}
      <span className="relative">{children}</span>
    </div>
  );
}

function FolderTabs() {
  const { id, research, analysis, prospects } = useDossier();
  const pathname = usePathname();
  const base = `/ideas/${id}`;
  const tabs = [
    { href: base, label: "Overview", count: analysis ? analysis.unknowns.length : null, countLabel: "questions" },
    { href: `${base}/evidence`, label: "Evidence", count: research?.evidence.length ?? null, countLabel: "exhibits" },
    { href: `${base}/landscape`, label: "Landscape", count: research?.competitors.length ?? null, countLabel: "alternatives" },
    { href: `${base}/prospects`, label: "Prospects", count: prospects?.length ?? null, countLabel: "companies" },
    { href: `${base}/outreach`, label: "Outreach", count: null, countLabel: "" },
    { href: `${base}/replies`, label: "Replies", count: null, countLabel: "" },
    { href: `${base}/interviews`, label: "Interviews", count: null, countLabel: "" },
    { href: `${base}/verdict`, label: "Verdict", count: null, countLabel: "" },
  ];
  return (
    <nav aria-label="Case sections" className="-mb-px flex gap-1 overflow-x-auto pt-2">
      {tabs.map((t) => {
        const active = pathname === t.href;
        return (
          <Link
            key={t.href}
            href={t.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "group relative shrink-0 rounded-t-md border px-4 pt-2 pb-2.5 text-sm transition-colors",
              active
                ? "z-10 border-b-paper bg-paper text-foreground"
                : "border-transparent text-muted-foreground hover:border-border hover:bg-paper/50 hover:text-foreground",
            )}
          >
            <span className={cn(active && "font-medium")}>{t.label}</span>
            {t.count !== null && (
              <span className="ml-2 font-mono text-[11px] text-muted-foreground" aria-label={`${t.count} ${t.countLabel}`}>
                {t.count}
              </span>
            )}
            {active && <motion.span layoutId="tab-ink" className="absolute inset-x-3 top-0 h-[2px] rounded-b bg-foreground" />}
          </Link>
        );
      })}
    </nav>
  );
}

function ResearchCommand() {
  const { id } = useDossier();
  const [copied, setCopied] = useState(false);
  const command = `/research-idea ${id}`;
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(command).then(() => {
          setCopied(true);
          toast.success("Copied — paste it into Claude Code to research this case.");
          setTimeout(() => setCopied(false), 1500);
        });
      }}
      className="group flex w-full items-center gap-2 rounded-md border border-dashed bg-background/60 px-2.5 py-2 text-left font-mono text-[11px] text-muted-foreground hover:text-foreground"
      aria-label="Copy the research command for Claude Code"
    >
      <span className="truncate">{command}</span>
      {copied ? <Check className="ml-auto size-3.5 shrink-0" /> : <Copy className="ml-auto size-3.5 shrink-0" />}
    </button>
  );
}

function CaseRail() {
  const { analysis, research, prospects } = useDossier();
  if (!analysis || !research || !prospects) {
    return <Skeleton className="h-96 w-full" />;
  }
  const ev = research.evidence;
  const tally = {
    supports: ev.filter((e) => e.stance === "supports").length,
    contradicts: ev.filter((e) => e.stance === "contradicts").length,
    neutral: ev.filter((e) => e.stance === "neutral").length,
  };
  const verified = ev.filter((e) => e.verification === "verified").length;
  const answered = analysis.unknowns.filter((u) => u.status === "answered").length;
  const findings = new Map(research.findings.map((f) => [f.unknown_id, f.status]));
  const next = analysis.unknowns
    .filter((u) => u.status === "open" && findings.get(u.id) !== "answered")
    .sort((a, b) => ["high", "medium", "low"].indexOf(a.priority) - ["high", "medium", "low"].indexOf(b.priority))
    .slice(0, 3);
  const scores = prospects.map((p) => p.score ?? 0);
  const lastImport = research.imports.find((i) => i.status === "done");

  return (
    <aside className="sheet space-y-6 self-start p-5 lg:sticky lg:top-20" aria-label="Case file">
      <div>
        <p className="eyebrow mb-2">Evidence balance</p>
        <EvidenceBalance {...tally} size="lg" />
        <p className="mt-2 text-xs text-muted-foreground">
          {verified} of {ev.length} exhibits verified against their source pages.
        </p>
      </div>

      <dl className="grid grid-cols-3 gap-3 border-y rule py-4">
        <div>
          <dt className="eyebrow !text-[9px]">Answered</dt>
          <dd className="mt-1 font-display text-2xl leading-none tabular-nums">
            {answered}
            <span className="text-base text-muted-foreground">/{analysis.unknowns.length}</span>
          </dd>
        </div>
        <div>
          <dt className="eyebrow !text-[9px]">Alternatives</dt>
          <dd className="mt-1 font-display text-2xl leading-none tabular-nums">{research.competitors.length}</dd>
        </div>
        <div>
          <dt className="eyebrow !text-[9px]">Best lead</dt>
          <dd className="mt-1 font-display text-2xl leading-none tabular-nums">
            {scores.length ? Math.max(...scores) : "—"}
          </dd>
        </div>
      </dl>

      <div>
        <p className="eyebrow mb-2">Next to prove</p>
        {next.length === 0 ? (
          <p className="text-sm text-muted-foreground">No open high-priority questions.</p>
        ) : (
          <ol className="space-y-2.5">
            {next.map((u, i) => (
              <li key={u.id} className="grid grid-cols-[1.5rem_1fr] gap-1 text-sm leading-snug">
                <span className="font-mono text-[11px] text-muted-foreground">{String(i + 1).padStart(2, "0")}</span>
                <span>{u.question}</span>
              </li>
            ))}
          </ol>
        )}
      </div>

      <div>
        <p className="eyebrow mb-2">Research</p>
        <p className="mb-2 text-xs text-muted-foreground">
          {lastImport
            ? `Last verified import ${relativeTime(lastImport.finished_at ?? lastImport.created_at)} (method v${lastImport.method_version}).`
            : "No research yet. Run this in Claude Code:"}
        </p>
        <ResearchCommand />
      </div>
    </aside>
  );
}

export function DossierFrame({ children }: { children: ReactNode }) {
  const { idea, analysis, error, refresh, startAnalysis, busy } = useDossier();
  const [starting, setStarting] = useState(false);

  if (error && !idea) {
    return (
      <main className="mx-auto w-full max-w-7xl px-4 py-12 sm:px-6">
        <ErrorState message={`Couldn't open this case: ${error}`} onRetry={refresh} />
      </main>
    );
  }

  async function analyze() {
    setStarting(true);
    try {
      await startAnalysis("full");
      toast("Analysis started", { description: "Hypothesis, open questions and customer profiles." });
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setStarting(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-7xl px-4 pb-24 sm:px-6">
      <header className="pt-10">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            {idea ? (
              <>
                <p className="eyebrow">
                  Case file · {idea.target_market} · {STATE_LABELS[idea.state]}
                </p>
                <h1 className="mt-2 font-display text-4xl leading-[1.02] tracking-tight sm:text-6xl">{idea.title}</h1>
                <p className="mt-3 max-w-3xl text-sm text-muted-foreground">{idea.description}</p>
              </>
            ) : (
              <>
                <Skeleton className="h-3 w-48" />
                <Skeleton className="mt-3 h-12 w-96 max-w-full" />
              </>
            )}
          </div>
          <Button variant="outline" onClick={analyze} disabled={busy || starting || !idea}>
            {analysis?.hypothesis ? <RefreshCw /> : <Sparkles />}
            {analysis?.hypothesis ? "Re-analyze" : "Analyze"}
          </Button>
        </div>
        <div className="mt-5 space-y-2">
          <RunStatus />
        </div>
      </header>

      <div className="mt-6 border-b rule">
        <FolderTabs />
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)] gap-8 pt-8 lg:grid-cols-[minmax(0,1fr)_19rem]">
        <div className="min-w-0">{children}</div>
        <CaseRail />
      </div>
    </main>
  );
}
