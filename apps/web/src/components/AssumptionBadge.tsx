import type { Source } from "@/lib/api";

/**
 * Everything in Phase 1A is an assumption until evidence exists (PRD §12). This badge makes that
 * visible everywhere and shows who wrote it.
 */
export function AssumptionBadge({ source }: { source: Source }) {
  const label = source === "ai" ? "Assumption · AI" : "Assumption · edited by you";
  return (
    <span
      title="Not validated yet. Research and customer conversations will confirm or reject this."
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs ${
        source === "ai"
          ? "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300"
          : "border-sky-500/40 bg-sky-500/10 text-sky-700 dark:text-sky-300"
      }`}
    >
      {label}
    </span>
  );
}
