"use client";

import { useState, type FormEvent } from "react";

import { AssumptionBadge } from "@/components/AssumptionBadge";
import { btnLink, btnPrimary, btnSecondary, card, input, sectionTitle } from "@/components/ui";
import { api, type Hypothesis, type HypothesisFields } from "@/lib/api";

const FIELDS: { key: keyof HypothesisFields; label: string; long?: boolean }[] = [
  { key: "problem", label: "Problem", long: true },
  { key: "users", label: "Who feels it" },
  { key: "buyer", label: "Who pays" },
  { key: "decision_maker", label: "Who decides" },
  { key: "economic_value", label: "Economic value", long: true },
  { key: "geography", label: "Geography" },
  { key: "industry", label: "Industry" },
];

function pick(h: Hypothesis): HypothesisFields {
  return Object.fromEntries(FIELDS.map(({ key }) => [key, h[key]])) as unknown as HypothesisFields;
}

export function HypothesisPanel({
  ideaId,
  hypothesis,
  onChange,
}: {
  ideaId: string;
  hypothesis: Hypothesis | null;
  onChange: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<HypothesisFields | null>(null);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<Hypothesis[] | null>(null);

  if (!hypothesis) {
    return (
      <section className={card}>
        <h2 className={sectionTitle}>Hypothesis</h2>
        <p className="mt-3 text-sm opacity-70">Not analyzed yet.</p>
      </section>
    );
  }

  function startEdit() {
    setDraft(pick(hypothesis!));
    setNote("");
    setError(null);
    setEditing(true);
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!draft) return;
    setSaving(true);
    setError(null);
    try {
      await api.editHypothesis(ideaId, { ...draft, change_note: note || undefined });
      setEditing(false);
      setHistory(null);
      onChange();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function toggleHistory() {
    if (history) return setHistory(null);
    try {
      setHistory(await api.hypothesisVersions(ideaId));
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section className={card}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className={sectionTitle}>Hypothesis</h2>
          <span className="text-xs opacity-60">v{hypothesis.version}</span>
          <AssumptionBadge source={hypothesis.source} />
        </div>
        {!editing && (
          <div className="flex gap-3">
            <button className={btnLink} onClick={toggleHistory}>
              {history ? "Hide history" : "History"}
            </button>
            <button className={btnSecondary} onClick={startEdit}>
              Edit
            </button>
          </div>
        )}
      </div>

      {editing && draft ? (
        <form onSubmit={save} className="mt-4 flex flex-col gap-3">
          {FIELDS.map(({ key, label, long }) => (
            <label key={key} className="flex flex-col gap-1">
              <span className="text-xs font-medium opacity-70">{label}</span>
              {long ? (
                <textarea
                  required
                  rows={2}
                  className={input}
                  value={draft[key]}
                  onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
                />
              ) : (
                <input
                  required
                  className={input}
                  value={draft[key]}
                  onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
                />
              )}
            </label>
          ))}
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium opacity-70">What changed? (optional)</span>
            <input className={input} value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex gap-2">
            <button type="submit" className={btnPrimary} disabled={saving}>
              {saving ? "Saving…" : "Save as new version"}
            </button>
            <button type="button" className={btnSecondary} onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <dl className="mt-4 grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
          {FIELDS.map(({ key, label, long }) => (
            <div key={key} className={long ? "sm:col-span-2" : undefined}>
              <dt className="text-xs font-medium opacity-60">{label}</dt>
              <dd>{hypothesis[key]}</dd>
            </div>
          ))}
        </dl>
      )}

      {error && !editing && <p className="mt-3 text-sm text-red-600">{error}</p>}

      {history && (
        <ol className="mt-4 flex flex-col gap-2 border-t border-black/10 pt-4 text-sm dark:border-white/15">
          {history.map((v) => (
            <li key={v.id} className="flex flex-col">
              <span className="text-xs opacity-60">
                v{v.version} · {v.source === "ai" ? "AI" : "You"} ·{" "}
                {new Date(v.created_at).toLocaleString()}
                {v.change_note ? ` · ${v.change_note}` : ""}
              </span>
              <span>{v.problem}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
