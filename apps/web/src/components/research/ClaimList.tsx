import type { Claim } from "@/lib/api";

/** Evidence citation link; jumps to the evidence item on the idea page. */
export function Cite({ id, refs }: { id: string; refs: Record<string, string> }) {
  return (
    <a
      href={`#ev-${id}`}
      className="mr-1 text-xs underline underline-offset-2 opacity-60 hover:opacity-100"
    >
      [{refs[id] ?? "evidence"}]
    </a>
  );
}

/** Claims with their kind and citations (PRD §12: facts, inferences and assumptions never blur). */
export function ClaimList({ claims, refs }: { claims: Claim[]; refs: Record<string, string> }) {
  return (
    <ul className="flex flex-col gap-1">
      {claims.map((c, i) => (
        <li key={i}>
          {c.statement}{" "}
          {c.evidence_ids.map((id) => (
            <Cite key={id} id={id} refs={refs} />
          ))}
          {c.kind !== "fact" && <span className="text-xs opacity-50">({c.kind})</span>}
        </li>
      ))}
    </ul>
  );
}
