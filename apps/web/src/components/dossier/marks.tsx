// Visual vocabulary of the dossier: stamps, claim-kind marks, provenance tags.
// PRD §12: a fact, an inference and an assumption must never look alike. Each
// gets its own glyph shape *and* label, so colour is never the only signal.

import { BadgeCheck, BookOpenCheck, CircleAlert, PenLine, Sparkles } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Stamp({
  tone,
  children,
  className,
}: {
  tone: "good" | "warning" | "ink";
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "stamp",
        tone === "good" && "text-status-good-ink",
        tone === "warning" && "text-status-warning-ink",
        tone === "ink" && "text-foreground/70",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function VerificationStamp({ verification }: { verification: "verified" | "unverifiable" }) {
  return verification === "verified" ? (
    <Stamp tone="good">
      <BadgeCheck className="size-3" aria-hidden /> Verified
    </Stamp>
  ) : (
    <Stamp tone="warning">
      <CircleAlert className="size-3" aria-hidden /> Unverifiable
    </Stamp>
  );
}

const KIND = {
  fact: { glyph: "■", label: "Fact", hint: "Stated directly by the source" },
  inference: { glyph: "◩", label: "Inference", hint: "Concluded from cited sources" },
  assumption: { glyph: "□", label: "Assumption", hint: "Not supported by evidence yet" },
} as const;

export function KindMark({ kind, className }: { kind: keyof typeof KIND; className?: string }) {
  const k = KIND[kind];
  return (
    <span
      title={k.hint}
      className={cn(
        "inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.12em]",
        kind === "fact" && "text-foreground",
        kind === "inference" && "text-ink-soft",
        kind === "assumption" && "text-muted-foreground italic",
        className,
      )}
    >
      <span aria-hidden className="text-[11px] not-italic leading-none">
        {k.glyph}
      </span>
      {k.label}
    </span>
  );
}

const PROVENANCE = {
  ai: { icon: Sparkles, label: "AI draft · assumption" },
  user: { icon: PenLine, label: "Edited by you · assumption" },
  research: { icon: BookOpenCheck, label: "From research" },
} as const;

export function Provenance({ source, className }: { source: keyof typeof PROVENANCE; className?: string }) {
  const p = PROVENANCE[source];
  const Icon = p.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-dashed px-2 py-0.5 text-[11px] text-muted-foreground",
        source === "research" && "border-solid border-viz-seq/40 text-viz-seq",
        className,
      )}
    >
      <Icon className="size-3" aria-hidden />
      {p.label}
    </span>
  );
}
