"use client";

import { useState, type FormEvent } from "react";

import { AssumptionBadge } from "@/components/AssumptionBadge";
import { btnLink, btnPrimary, card, input, sectionTitle, select } from "@/components/ui";
import {
  api,
  type Finding,
  type FindingStatus,
  type Priority,
  type Unknown,
  type UnknownCategory,
} from "@/lib/api";

const CATEGORIES: Record<UnknownCategory, string> = {
  frequency: "Frequency",
  cost: "Cost",
  current_solution: "Current solution",
  buyer: "Buyer",
  budget: "Budget",
  alternatives: "Alternatives",
  urgency: "Urgency",
  other: "Other",
};
const PRIORITY_ORDER: Record<Priority, number> = { high: 0, medium: 1, low: 2 };
const PRIORITY_STYLE: Record<Priority, string> = {
  high: "bg-red-500/10 text-red-700 dark:text-red-300",
  medium: "bg-amber-500/10 text-amber-700 dark:text-amber-300",
  low: "bg-black/5 dark:bg-white/10",
};

const FINDING_LABELS: Record<FindingStatus, { label: string; style: string }> = {
  answered: { label: "Answered by research", style: "text-green-700 dark:text-green-400" },
  partially_answered: {
    label: "Partially answered by research",
    style: "text-amber-700 dark:text-amber-300",
  },
  no_evidence_found: { label: "No evidence found", style: "opacity-70" },
};

/** Latest research finding for an unknown; claims link to the evidence they cite. */
function FindingBlock({ finding, refs }: { finding: Finding; refs: Record<string, string> }) {
  const { label, style } = FINDING_LABELS[finding.status];
  return (
    <div className="rounded-md bg-black/[.03] px-3 py-2 text-sm dark:bg-white/[.05]">
      <p className={`text-xs font-medium ${style}`}>{label}</p>
      {finding.summary.length > 0 && (
        <ul className="mt-1 flex flex-col gap-1">
          {finding.summary.map((c, i) => (
            <li key={i}>
              {c.statement}{" "}
              {c.evidence_ids.map((id) => (
                <a
                  key={id}
                  href={`#ev-${id}`}
                  className="text-xs underline underline-offset-2 opacity-60 hover:opacity-100"
                >
                  [{refs[id] ?? "evidence"}]
                </a>
              ))}
              {c.kind !== "fact" && <span className="ml-1 text-xs opacity-50">({c.kind})</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function UnknownRow({
  ideaId,
  unknown,
  finding,
  refs,
  onChange,
}: {
  ideaId: string;
  unknown: Unknown;
  finding?: Finding;
  refs: Record<string, string>;
  onChange: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(unknown.question);
  const [error, setError] = useState<string | null>(null);

  async function patch(data: Parameters<typeof api.updateUnknown>[2]) {
    setError(null);
    try {
      await api.updateUnknown(ideaId, unknown.id, data);
      setEditing(false);
      onChange();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const answered = unknown.status === "answered";
  return (
    <li className="flex flex-col gap-2 border-t border-black/5 py-3 first:border-t-0 dark:border-white/10">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className={`rounded px-1.5 py-0.5 ${PRIORITY_STYLE[unknown.priority]}`}>
          {unknown.priority}
        </span>
        <span className="opacity-60">{CATEGORIES[unknown.category]}</span>
        <AssumptionBadge source={unknown.source} />
        {answered && <span className="text-green-700 dark:text-green-400">✓ answered</span>}
      </div>
      {editing ? (
        <form
          className="flex gap-2"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            patch({ question: text });
          }}
        >
          <input required className={input} value={text} onChange={(e) => setText(e.target.value)} />
          <button className={btnPrimary}>Save</button>
        </form>
      ) : (
        <p className={`text-sm ${answered ? "opacity-60 line-through" : ""}`}>{unknown.question}</p>
      )}
      {finding && <FindingBlock finding={finding} refs={refs} />}
      <div className="flex flex-wrap gap-3">
        {!editing && (
          <button className={btnLink} onClick={() => setEditing(true)}>
            Edit
          </button>
        )}
        <select
          aria-label="Priority"
          className="bg-transparent text-sm opacity-70"
          value={unknown.priority}
          onChange={(e) => patch({ priority: e.target.value as Priority })}
        >
          <option value="high">High priority</option>
          <option value="medium">Medium priority</option>
          <option value="low">Low priority</option>
        </select>
        <button
          className={btnLink}
          onClick={() => patch({ status: answered ? "open" : "answered" })}
        >
          {answered ? "Reopen" : "Mark answered"}
        </button>
        <button className={btnLink} onClick={() => patch({ status: "dropped" })}>
          Remove
        </button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </li>
  );
}

export function UnknownsPanel({
  ideaId,
  unknowns,
  findings = [],
  evidenceRefs = {},
  onChange,
}: {
  ideaId: string;
  unknowns: Unknown[];
  findings?: Finding[];
  /** evidence id -> its ref label, for citation links */
  evidenceRefs?: Record<string, string>;
  onChange: () => void;
}) {
  const findingFor = Object.fromEntries(findings.map((f) => [f.unknown_id, f]));
  const [question, setQuestion] = useState("");
  const [category, setCategory] = useState<UnknownCategory>("other");
  const [priority, setPriority] = useState<Priority>("medium");
  const [error, setError] = useState<string | null>(null);

  const sorted = [...unknowns].sort(
    (a, b) =>
      Number(a.status === "answered") - Number(b.status === "answered") ||
      PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority],
  );

  async function add(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.createUnknown(ideaId, { question, category, priority });
      setQuestion("");
      onChange();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section className={card}>
      <h2 className={sectionTitle}>Unknowns · research plan</h2>
      <p className="mt-1 text-sm opacity-70">
        Questions research and customer conversations must answer before you build.
      </p>
      {sorted.length === 0 ? (
        <p className="mt-3 text-sm opacity-70">No unknowns yet.</p>
      ) : (
        <ul className="mt-3">
          {sorted.map((u) => (
            <UnknownRow
              key={u.id}
              ideaId={ideaId}
              unknown={u}
              finding={findingFor[u.id]}
              refs={evidenceRefs}
              onChange={onChange}
            />
          ))}
        </ul>
      )}

      <form onSubmit={add} className="mt-4 flex flex-col gap-2 border-t border-black/10 pt-4 dark:border-white/15">
        <span className="text-xs font-medium opacity-70">Add an unknown</span>
        <input
          required
          className={input}
          placeholder="How do they currently handle…?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <div className="flex flex-wrap gap-2">
          <select
            aria-label="Category"
            className={select}
            value={category}
            onChange={(e) => setCategory(e.target.value as UnknownCategory)}
          >
            {Object.entries(CATEGORIES).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select
            aria-label="Priority"
            className={select}
            value={priority}
            onChange={(e) => setPriority(e.target.value as Priority)}
          >
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <button className={btnPrimary}>Add</button>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </form>
    </section>
  );
}
