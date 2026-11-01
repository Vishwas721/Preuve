"use client";

import { useState, type FormEvent } from "react";

import { AssumptionBadge } from "@/components/AssumptionBadge";
import { btnLink, btnPrimary, card, input, sectionTitle } from "@/components/ui";
import { api, type Priority, type Unknown, type UnknownCategory } from "@/lib/api";

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

function UnknownRow({
  ideaId,
  unknown,
  onChange,
}: {
  ideaId: string;
  unknown: Unknown;
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
  onChange,
}: {
  ideaId: string;
  unknowns: Unknown[];
  onChange: () => void;
}) {
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
            <UnknownRow key={u.id} ideaId={ideaId} unknown={u} onChange={onChange} />
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
            className={`${input} w-auto`}
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
            className={`${input} w-auto`}
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
