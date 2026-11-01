import type { AnalysisRun } from "@/lib/api";

const STEP_LABELS: Record<string, string> = {
  hypothesis: "Structuring the hypothesis and unknowns…",
  icps: "Proposing candidate ICPs…",
};

export function isActive(run: AnalysisRun | null): boolean {
  return run?.status === "queued" || run?.status === "running";
}

export function RunBanner({ run, onRetry }: { run: AnalysisRun | null; onRetry: () => void }) {
  if (!run) return null;

  if (isActive(run)) {
    const label =
      run.status === "queued" ? "Waiting for the worker…" : (STEP_LABELS[run.step ?? ""] ?? "Working…");
    return (
      <div
        role="status"
        className="flex items-center gap-3 rounded-lg border border-black/10 bg-black/[.03] px-4 py-3 text-sm dark:border-white/15 dark:bg-white/[.05]"
      >
        <span aria-hidden className="h-2 w-2 animate-pulse rounded-full bg-amber-500" />
        {label}
      </div>
    );
  }

  if (run.status === "failed") {
    return (
      <div
        role="alert"
        className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-red-500/30 bg-red-500/5 px-4 py-3 text-sm"
      >
        <span>
          Analysis failed{run.error ? `: ${run.error}` : "."} Anything already generated was kept.
        </span>
        <button onClick={onRetry} className="underline">
          Try again
        </button>
      </div>
    );
  }

  return null;
}
