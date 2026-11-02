"use client";

import { useState, type FormEvent } from "react";

import { Cite, ClaimList } from "@/components/research/ClaimList";
import {
  btnLink,
  btnPrimary,
  btnSecondary,
  card,
  input,
  sectionTitle,
  select,
} from "@/components/ui";
import {
  api,
  type Competitor,
  type CompetitorInput,
  type CompetitorKind,
  type Evidence,
  type IdeaResearch,
} from "@/lib/api";

const KINDS: { key: CompetitorKind; label: string; hint: string }[] = [
  { key: "direct", label: "Direct competitors", hint: "Products solving the same problem" },
  { key: "indirect", label: "Indirect competitors", hint: "Software solving part of it" },
  { key: "manual", label: "Manual workarounds", hint: "Spreadsheets, email, chat, paper" },
  { key: "service", label: "Services", hint: "Consultants, agencies, outsourced providers" },
];

const EMPTY: CompetitorInput = {
  name: "",
  kind: "direct",
  url: "",
  description: "",
  pricing_note: "",
};

function clean(form: CompetitorInput): CompetitorInput {
  return {
    ...form,
    url: form.url?.trim() || null,
    pricing_note: form.pricing_note?.trim() || null,
  };
}

function CompetitorForm({
  initial,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  initial: CompetitorInput;
  submitLabel: string;
  onSubmit: (data: CompetitorInput) => Promise<void>;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<CompetitorInput>(initial);
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof CompetitorInput) => (v: string) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await onSubmit(clean(form));
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
        <input
          required
          aria-label="Name"
          placeholder="Name"
          className={input}
          value={form.name}
          onChange={(e) => set("name")(e.target.value)}
        />
        <select
          aria-label="Kind"
          className={select}
          value={form.kind}
          onChange={(e) => set("kind")(e.target.value)}
        >
          {KINDS.map((k) => (
            <option key={k.key} value={k.key}>
              {k.label}
            </option>
          ))}
        </select>
      </div>
      <input
        aria-label="Website"
        placeholder="https://… (optional)"
        className={input}
        value={form.url ?? ""}
        onChange={(e) => set("url")(e.target.value)}
      />
      <textarea
        required
        aria-label="What it covers"
        placeholder="What part of the problem it covers"
        rows={2}
        className={input}
        value={form.description}
        onChange={(e) => set("description")(e.target.value)}
      />
      <input
        aria-label="Pricing"
        placeholder="Public pricing (optional)"
        className={input}
        value={form.pricing_note ?? ""}
        onChange={(e) => set("pricing_note")(e.target.value)}
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex gap-2">
        <button className={btnPrimary}>{submitLabel}</button>
        <button type="button" className={btnSecondary} onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function CompetitorCard({
  ideaId,
  comp,
  evidenceById,
  refs,
  onChange,
}: {
  ideaId: string;
  comp: Competitor;
  evidenceById: Record<string, Evidence>;
  refs: Record<string, string>;
  onChange: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const linked = comp.evidence_ids.map((id) => evidenceById[id]).filter(Boolean);
  const onlyUnverifiable =
    linked.length > 0 && linked.every((e) => e.verification === "unverifiable");

  async function dismiss() {
    try {
      await api.updateCompetitor(ideaId, comp.id, { status: "dismissed" });
      onChange();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (editing) {
    return (
      <li className="rounded-md border border-black/10 p-3 dark:border-white/15">
        <CompetitorForm
          initial={{ ...comp, url: comp.url ?? "", pricing_note: comp.pricing_note ?? "" }}
          submitLabel="Save"
          onCancel={() => setEditing(false)}
          onSubmit={async (data) => {
            await api.updateCompetitor(ideaId, comp.id, data);
            setEditing(false);
            onChange();
          }}
        />
      </li>
    );
  }

  return (
    <li className="flex flex-col gap-1.5 rounded-md border border-black/10 p-3 text-sm dark:border-white/15">
      <div className="flex flex-wrap items-center gap-2">
        {comp.url ? (
          <a
            href={comp.url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium underline-offset-2 hover:underline"
          >
            {comp.name}
          </a>
        ) : (
          <span className="font-medium">{comp.name}</span>
        )}
        <span
          className={`rounded-full border px-2 py-0.5 text-xs ${
            comp.source === "user"
              ? "border-sky-500/40 bg-sky-500/10 text-sky-700 dark:text-sky-300"
              : "border-violet-500/40 bg-violet-500/10 text-violet-700 dark:text-violet-300"
          }`}
        >
          {comp.source === "user"
            ? "Added by you"
            : comp.user_edited
              ? "From research · edited by you"
              : "From research"}
        </span>
        {onlyUnverifiable && (
          <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-xs text-amber-700 dark:text-amber-300">
            Only unverifiable evidence
          </span>
        )}
      </div>
      <p className="opacity-90">{comp.description}</p>
      {comp.pricing_note && <p className="text-xs opacity-70">Pricing: {comp.pricing_note}</p>}
      {comp.sentiment.length > 0 && (
        <div className="text-sm">
          <p className="text-xs font-medium opacity-60">What customers say</p>
          <ClaimList claims={comp.sentiment} refs={refs} />
        </div>
      )}
      <div className="flex flex-wrap items-center gap-3 text-xs">
        {comp.evidence_ids.length > 0 ? (
          <span className="opacity-70">
            Evidence:{" "}
            {comp.evidence_ids.map((id) => (
              <Cite key={id} id={id} refs={refs} />
            ))}
          </span>
        ) : (
          <span className="opacity-60">No linked evidence (added by you)</span>
        )}
        <button className={btnLink} onClick={() => setEditing(true)}>
          Edit
        </button>
        <button className={btnLink} onClick={dismiss}>
          Dismiss
        </button>
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </li>
  );
}

export function SolutionsPanel({
  ideaId,
  research,
  onChange,
}: {
  ideaId: string;
  research: IdeaResearch;
  onChange: () => void;
}) {
  const [adding, setAdding] = useState(false);
  const evidenceById = Object.fromEntries(research.evidence.map((e) => [e.id, e]));
  const refs = Object.fromEntries(research.evidence.map((e) => [e.id, e.ref]));

  return (
    <section className={card}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className={sectionTitle}>How it&apos;s solved today</h2>
        <button className={btnSecondary} onClick={() => setAdding((a) => !a)}>
          {adding ? "Cancel" : "Add alternative"}
        </button>
      </div>

      <div className="mt-3 text-sm">
        {research.current_solutions.length > 0 ? (
          <ClaimList claims={research.current_solutions} refs={refs} />
        ) : (
          <p>No evidence found.</p>
        )}
      </div>

      {adding && (
        <div className="mt-4 rounded-md border border-dashed border-black/20 p-3 dark:border-white/25">
          <CompetitorForm
            initial={EMPTY}
            submitLabel="Add"
            onCancel={() => setAdding(false)}
            onSubmit={async (data) => {
              await api.createCompetitor(ideaId, data);
              setAdding(false);
              onChange();
            }}
          />
        </div>
      )}

      <div className="mt-5 flex flex-col gap-5">
        {KINDS.map(({ key, label, hint }) => {
          const items = research.competitors.filter((c) => c.kind === key);
          return (
            <div key={key}>
              <h3 className="text-sm font-medium">
                {label} <span className="opacity-50">({items.length})</span>
                <span className="ml-2 text-xs font-normal opacity-50">{hint}</span>
              </h3>
              {items.length === 0 ? (
                <p className="mt-1 text-sm opacity-60">No evidence found.</p>
              ) : (
                <ul className="mt-2 flex flex-col gap-2">
                  {items.map((c) => (
                    <CompetitorCard
                      key={c.id}
                      ideaId={ideaId}
                      comp={c}
                      evidenceById={evidenceById}
                      refs={refs}
                      onChange={onChange}
                    />
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
