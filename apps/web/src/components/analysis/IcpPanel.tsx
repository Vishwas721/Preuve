"use client";

import { useState, type FormEvent } from "react";

import { AssumptionBadge } from "@/components/AssumptionBadge";
import { btnLink, btnPrimary, btnSecondary, card, input, sectionTitle } from "@/components/ui";
import { api, type Criterion, type ICP, type Ratings } from "@/lib/api";

const CRITERIA: { key: Criterion; label: string; weight: number }[] = [
  { key: "pain_likelihood", label: "Pain likelihood", weight: 30 },
  { key: "ability_to_pay", label: "Ability to pay", weight: 25 },
  { key: "reachability", label: "Reachability", weight: 20 },
  { key: "frequency_urgency", label: "Frequency / urgency", weight: 15 },
  { key: "segment_size", label: "Segment size", weight: 10 },
];

function defaultRatings(): Ratings {
  return Object.fromEntries(
    CRITERIA.map(({ key }) => [key, { rating: 3, rationale: "Set by you" }]),
  ) as Ratings;
}

function ratingsOf(icp: ICP): Ratings {
  return Object.fromEntries(
    icp.score_breakdown.map((c) => [c.criterion, { rating: c.rating, rationale: c.rationale }]),
  ) as Ratings;
}

function sizeLabel(icp: Pick<ICP, "size_min" | "size_max">): string {
  if (icp.size_min && icp.size_max) return `${icp.size_min}–${icp.size_max} employees`;
  if (icp.size_min) return `${icp.size_min}+ employees`;
  if (icp.size_max) return `up to ${icp.size_max} employees`;
  return "Any size";
}

function RatingsEditor({ value, onChange }: { value: Ratings; onChange: (r: Ratings) => void }) {
  return (
    <div className="flex flex-col gap-2">
      {CRITERIA.map(({ key, label, weight }) => (
        <div key={key} className="grid gap-2 sm:grid-cols-[10rem_5rem_1fr] sm:items-center">
          <span className="text-sm">
            {label} <span className="opacity-50">({weight})</span>
          </span>
          <select
            aria-label={`${label} rating`}
            className={input}
            value={value[key].rating}
            onChange={(e) =>
              onChange({ ...value, [key]: { ...value[key], rating: Number(e.target.value) } })
            }
          >
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                {n} / 5
              </option>
            ))}
          </select>
          <input
            aria-label={`${label} rationale`}
            required
            className={input}
            value={value[key].rationale}
            onChange={(e) =>
              onChange({ ...value, [key]: { ...value[key], rationale: e.target.value } })
            }
          />
        </div>
      ))}
    </div>
  );
}

function IcpCard({ ideaId, icp, onChange }: { ideaId: string; icp: ICP; onChange: () => void }) {
  const [editing, setEditing] = useState(false);
  const [ratings, setRatings] = useState<Ratings>(() => ratingsOf(icp));
  const [error, setError] = useState<string | null>(null);

  async function patch(data: Parameters<typeof api.updateIcp>[2]) {
    setError(null);
    try {
      await api.updateIcp(ideaId, icp.id, data);
      setEditing(false);
      onChange();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <article className="flex flex-col gap-3 rounded-md border border-black/10 p-4 dark:border-white/15">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium">{icp.name}</h3>
            {icp.is_primary && (
              <span className="rounded-full bg-foreground px-2 py-0.5 text-xs text-background">
                Primary
              </span>
            )}
            <AssumptionBadge source={icp.source} />
          </div>
          <p className="text-sm opacity-70">
            {icp.company_type} · {sizeLabel(icp)} · {icp.geography}
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-semibold tabular-nums">{icp.hypothesis_score}</div>
          <div className="text-xs opacity-60">hypothesis score</div>
        </div>
      </div>

      {(icp.roles.users?.length || icp.roles.buyers?.length) && (
        <p className="text-sm">
          <span className="opacity-60">Users:</span> {icp.roles.users?.join(", ") || "—"}{" "}
          <span className="opacity-60">· Buyers:</span> {icp.roles.buyers?.join(", ") || "—"}
        </p>
      )}
      {icp.signals.length > 0 && (
        <ul className="flex flex-wrap gap-1.5">
          {icp.signals.map((s) => (
            <li key={s} className="rounded bg-black/5 px-2 py-0.5 text-xs dark:bg-white/10">
              {s}
            </li>
          ))}
        </ul>
      )}

      {editing ? (
        <form
          className="flex flex-col gap-3"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            patch({ ratings });
          }}
        >
          <RatingsEditor value={ratings} onChange={setRatings} />
          <div className="flex gap-2">
            <button className={btnPrimary}>Save ratings</button>
            <button type="button" className={btnSecondary} onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Score breakdown</caption>
          <tbody>
            {icp.score_breakdown.map((c) => (
              <tr key={c.criterion} className="border-t border-black/5 align-top dark:border-white/10">
                <td className="w-40 py-1.5 pr-2">
                  {CRITERIA.find((x) => x.key === c.criterion)?.label}
                </td>
                <td className="w-24 py-1.5 pr-2 tabular-nums opacity-80">
                  {c.rating}/5 · {c.points}/{c.weight}
                </td>
                <td className="py-1.5 opacity-80">{c.rationale}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="flex flex-wrap gap-3">
        {!icp.is_primary && (
          <button className={btnLink} onClick={() => patch({ is_primary: true })}>
            Make primary
          </button>
        )}
        {!editing && (
          <button
            className={btnLink}
            onClick={() => {
              setRatings(ratingsOf(icp));
              setEditing(true);
            }}
          >
            Edit ratings
          </button>
        )}
        <button className={btnLink} onClick={() => patch({ status: "dismissed" })}>
          Dismiss
        </button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </article>
  );
}

function AddIcpForm({ ideaId, onDone }: { ideaId: string; onDone: () => void }) {
  const [name, setName] = useState("");
  const [companyType, setCompanyType] = useState("");
  const [geography, setGeography] = useState("");
  const [sizeMin, setSizeMin] = useState("");
  const [sizeMax, setSizeMax] = useState("");
  const [ratings, setRatings] = useState<Ratings>(defaultRatings);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.createIcp(ideaId, {
        name,
        company_type: companyType,
        geography,
        size_min: sizeMin ? Number(sizeMin) : null,
        size_max: sizeMax ? Number(sizeMax) : null,
        ratings,
      });
      onDone();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded-md border border-dashed border-black/20 p-4 dark:border-white/25">
      <div className="grid gap-2 sm:grid-cols-2">
        <input required className={input} placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
        <input required className={input} placeholder="Company type" value={companyType} onChange={(e) => setCompanyType(e.target.value)} />
        <input required className={input} placeholder="Geography" value={geography} onChange={(e) => setGeography(e.target.value)} />
        <div className="flex gap-2">
          <input type="number" min={1} className={input} placeholder="Min employees" value={sizeMin} onChange={(e) => setSizeMin(e.target.value)} />
          <input type="number" min={1} className={input} placeholder="Max employees" value={sizeMax} onChange={(e) => setSizeMax(e.target.value)} />
        </div>
      </div>
      <RatingsEditor value={ratings} onChange={setRatings} />
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button className={`${btnPrimary} self-start`}>Add ICP</button>
    </form>
  );
}

export function IcpPanel({
  ideaId,
  icps,
  canRegenerate,
  busy,
  onRegenerate,
  onChange,
}: {
  ideaId: string;
  icps: ICP[];
  canRegenerate: boolean;
  busy: boolean;
  onRegenerate: () => void;
  onChange: () => void;
}) {
  const [adding, setAdding] = useState(false);

  return (
    <section className={card}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className={sectionTitle}>Candidate ICPs</h2>
        <div className="flex gap-2">
          <button className={btnSecondary} onClick={() => setAdding((a) => !a)}>
            {adding ? "Cancel" : "Add ICP"}
          </button>
          {canRegenerate && (
            <button className={btnSecondary} onClick={onRegenerate} disabled={busy}>
              Regenerate
            </button>
          )}
        </div>
      </div>
      <p className="mt-1 text-sm opacity-70">
        Scores come from a fixed rubric (pain 30, ability to pay 25, reachability 20, urgency 15,
        segment size 10). They are hypotheses until research says otherwise.
      </p>

      <div className="mt-4 flex flex-col gap-3">
        {adding && (
          <AddIcpForm
            ideaId={ideaId}
            onDone={() => {
              setAdding(false);
              onChange();
            }}
          />
        )}
        {icps.length === 0 && !adding ? (
          <p className="text-sm opacity-70">No ICPs yet.</p>
        ) : (
          icps.map((icp) => <IcpCard key={icp.id} ideaId={ideaId} icp={icp} onChange={onChange} />)
        )}
      </div>
    </section>
  );
}
