"use client";

import Link from "next/link";

import { useDossier } from "@/components/dossier/DossierProvider";
import { KindMark } from "@/components/dossier/marks";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Claim } from "@/lib/api";
import { domain } from "@/lib/format";
import { cn } from "@/lib/utils";

/** A citation chip: "EX-04". Hover previews the quote; click jumps to the exhibit. */
export function Cite({ id, className }: { id: string; className?: string }) {
  const { id: ideaId, exhibit, evidenceById } = useDossier();
  const ev = evidenceById[id];
  const chip = (
    <Link
      href={`/ideas/${ideaId}/evidence#ev-${id}`}
      className={cn(
        "mx-0.5 inline-flex items-center rounded-[3px] border border-viz-seq/30 bg-viz-seq/[0.07] px-1 align-[1px] font-mono text-[10px] leading-4 text-viz-seq transition-colors hover:bg-viz-seq/15",
        className,
      )}
    >
      {exhibit(id)}
    </Link>
  );
  if (!ev) return chip;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{chip}</TooltipTrigger>
      <TooltipContent className="max-w-sm p-3">
        <p className="font-display text-sm italic leading-snug">&ldquo;{ev.quote}&rdquo;</p>
        <p className="mt-1.5 font-mono text-[10px] opacity-70">{domain(ev.url)}</p>
      </TooltipContent>
    </Tooltip>
  );
}

/** Claims with their kind and citations. Facts, inferences and assumptions never blur (PRD §12). */
export function ClaimList({ claims, className }: { claims: Claim[]; className?: string }) {
  return (
    <ul className={cn("space-y-2", className)}>
      {claims.map((c, i) => (
        <li key={i} className="grid grid-cols-[5.5rem_1fr] gap-3 text-sm leading-relaxed">
          <KindMark kind={c.kind} className="pt-[3px]" />
          <span>
            {c.statement}
            {c.evidence_ids.map((eid) => (
              <Cite key={eid} id={eid} />
            ))}
          </span>
        </li>
      ))}
    </ul>
  );
}
