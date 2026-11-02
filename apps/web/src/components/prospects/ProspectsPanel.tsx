"use client";

import { useCallback, useEffect, useState } from "react";

import { Cite } from "@/components/research/ClaimList";
import { btnLink, btnSecondary, card, sectionTitle, select } from "@/components/ui";
import { api, type ProspectDetail, type ProspectStatus, type ProspectSummary } from "@/lib/api";

const STATUS_LABELS: Record<ProspectStatus, string> = {
  new: "New",
  shortlisted: "Shortlisted",
  excluded: "Excluded",
};

function scoreTone(score: number | null): string {
  if (score === null) return "bg-black/5 dark:bg-white/10";
  if (score >= 70) return "bg-green-600/15 text-green-800 dark:text-green-300";
  if (score >= 45) return "bg-amber-500/15 text-amber-800 dark:text-amber-300";
  return "bg-black/5 dark:bg-white/10";
}

function DeleteContact({ onConfirm }: { onConfirm: () => void }) {
  const [asking, setAsking] = useState(false);
  if (!asking) {
    return (
      <button className={btnLink} onClick={() => setAsking(true)}>
        Delete
      </button>
    );
  }
  return (
    <span className="text-xs">
      Permanently delete this person&apos;s data?{" "}
      <button className="text-red-600 underline" onClick={onConfirm}>
        Delete
      </button>{" "}
      <button className="underline" onClick={() => setAsking(false)}>
        Keep
      </button>
    </span>
  );
}

function ProspectDetailView({
  ideaId,
  id,
  refs,
  onChange,
}: {
  ideaId: string;
  id: string;
  refs: Record<string, string>;
  onChange: () => void;
}) {
  const [detail, setDetail] = useState<ProspectDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.getProspect(ideaId, id).then(setDetail, (e: Error) => setError(e.message));
  }, [ideaId, id]);
  useEffect(load, [load]);

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!detail) return <p className="text-sm opacity-70">Loading…</p>;

  return (
    <div className="flex flex-col gap-4 py-3 text-sm">
      <p className="opacity-80">{detail.description}</p>
      <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
        <div>
          <dt className="inline opacity-60">Size: </dt>
          <dd className="inline">{detail.size_signal ?? "unknown"}</dd>
        </div>
        <div>
          <dt className="inline opacity-60">Technologies: </dt>
          <dd className="inline">{detail.technologies.join(", ") || "—"}</dd>
        </div>
      </dl>

      <div>
        <h4 className="text-xs font-medium uppercase tracking-wide opacity-60">
          Score breakdown ({detail.score}/100)
        </h4>
        <table className="mt-1 w-full text-left">
          <tbody>
            {detail.components.map((c) => (
              <tr key={c.key} className="border-t border-black/5 align-top dark:border-white/10">
                <td className="w-36 py-1.5 pr-2">{c.label}</td>
                <td className="w-20 py-1.5 pr-2 tabular-nums">
                  {c.points}/{c.max}
                </td>
                <td className="py-1.5 opacity-80">
                  {c.reason}{" "}
                  {c.evidence_ids.map((eid) => (
                    <Cite key={eid} id={eid} refs={refs} />
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div>
        <h4 className="text-xs font-medium uppercase tracking-wide opacity-60">
          Contacts ({detail.contacts_list.length})
        </h4>
        {detail.contacts_list.length === 0 ? (
          <p className="mt-1 opacity-60">No contacts found on public company pages.</p>
        ) : (
          <ul className="mt-1 flex flex-col gap-1.5">
            {detail.contacts_list.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="font-medium">{c.name}</span>
                <span className="opacity-80">{c.role}</span>
                {c.email && <span className="opacity-80">{c.email}</span>}
                <a
                  href={c.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs underline underline-offset-2 opacity-60 hover:opacity-100"
                >
                  source
                </a>
                <DeleteContact
                  onConfirm={async () => {
                    try {
                      await api.deleteContact(ideaId, c.id);
                      load();
                      onChange();
                    } catch (err) {
                      setError((err as Error).message);
                    }
                  }}
                />
              </li>
            ))}
          </ul>
        )}
        <p className="mt-1 text-xs opacity-50">
          Only people named on the company&apos;s own public pages. Emails appear only when printed
          there.
        </p>
      </div>
    </div>
  );
}

export function ProspectsPanel({
  ideaId,
  evidenceRefs,
}: {
  ideaId: string;
  evidenceRefs: Record<string, string>;
}) {
  const [rows, setRows] = useState<ProspectSummary[] | null>(null);
  const [status, setStatus] = useState<ProspectStatus | "">("");
  const [minScore, setMinScore] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .listProspects(ideaId, {
        status: status || undefined,
        min_score: minScore ? Number(minScore) : undefined,
      })
      .then(setRows, (e: Error) => setError(e.message));
  }, [ideaId, status, minScore]);
  useEffect(load, [load]);

  async function setRowStatus(id: string, value: ProspectStatus) {
    try {
      await api.updateProspect(ideaId, id, { status: value });
      load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function rescore() {
    try {
      await api.rescoreProspects(ideaId);
      load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section className={card}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className={sectionTitle}>Prospects</h2>
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Filter by status"
            className={select}
            value={status}
            onChange={(e) => setStatus(e.target.value as ProspectStatus | "")}
          >
            <option value="">All statuses</option>
            {Object.entries(STATUS_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
          <input
            aria-label="Minimum score"
            type="number"
            min={0}
            max={100}
            placeholder="Min score"
            className={`${select} w-28`}
            value={minScore}
            onChange={(e) => setMinScore(e.target.value)}
          />
          <button className={btnSecondary} onClick={rescore}>
            Rescore
          </button>
        </div>
      </div>
      <p className="mt-1 text-sm opacity-70">
        Scored 0–100 in code from verified evidence (PRD §16). A judgement without stored evidence
        earns no points.
      </p>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      {rows === null ? (
        <p className="mt-3 text-sm opacity-70">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="mt-3 text-sm opacity-70">
          No prospects yet. Run{" "}
          <code className="rounded bg-black/5 px-1 dark:bg-white/10">/research-idea {ideaId}</code>{" "}
          (method v3) to find companies.
        </p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="text-xs opacity-60">
              <tr>
                <th className="py-2 font-medium">Score</th>
                <th className="py-2 font-medium">Company</th>
                <th className="py-2 font-medium">Location</th>
                <th className="py-2 font-medium">Best contact</th>
                <th className="py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <ProspectRow
                  key={p.id}
                  p={p}
                  open={open === p.id}
                  onToggle={() => setOpen(open === p.id ? null : p.id)}
                  onStatus={(v) => setRowStatus(p.id, v)}
                  detail={
                    <ProspectDetailView
                      ideaId={ideaId}
                      id={p.id}
                      refs={evidenceRefs}
                      onChange={load}
                    />
                  }
                />
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs opacity-60">{rows.length} prospects</p>
        </div>
      )}
    </section>
  );
}

function ProspectRow({
  p,
  open,
  onToggle,
  onStatus,
  detail,
}: {
  p: ProspectSummary;
  open: boolean;
  onToggle: () => void;
  onStatus: (v: ProspectStatus) => void;
  detail: React.ReactNode;
}) {
  return (
    <>
      <tr className="border-t border-black/5 dark:border-white/10">
        <td className="py-2 pr-2">
          <span className={`rounded px-2 py-0.5 tabular-nums ${scoreTone(p.score)}`}>
            {p.score ?? "—"}
          </span>
        </td>
        <td className="py-2 pr-2">
          <button
            className="text-left font-medium hover:underline"
            onClick={onToggle}
            aria-expanded={open}
          >
            {open ? "▾" : "▸"} {p.name}
          </button>
          <a
            href={p.website}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-2 text-xs opacity-60 hover:underline"
          >
            {p.domain}
          </a>
        </td>
        <td className="py-2 pr-2 opacity-80">{p.location ?? "—"}</td>
        <td className="py-2 pr-2 opacity-80">
          {p.top_contact_role ?? "—"}
          {p.contacts > 1 ? ` +${p.contacts - 1}` : ""}
        </td>
        <td className="py-2">
          <select
            aria-label={`Status of ${p.name}`}
            className="bg-transparent text-sm"
            value={p.status}
            onChange={(e) => onStatus(e.target.value as ProspectStatus)}
          >
            {Object.entries(STATUS_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={5} className="pb-2">
            {detail}
          </td>
        </tr>
      )}
    </>
  );
}
