"use client";

import { useEffect, useState } from "react";

import { api, API_URL, type Health, type Idea, type ValidationState } from "@/lib/api";

const STATE_LABELS: Record<ValidationState, string> = {
  unvalidated: "Unvalidated",
  researching: "Researching",
  early_signal: "Early signal",
  problem_validated: "Problem validated",
  solution_validation: "Solution validation",
  commercial_validation: "Commercial validation",
  mvp_ready: "MVP ready",
};

type Load<T> = { status: "loading" } | { status: "error"; message: string } | { status: "ok"; data: T };

function useLoad<T>(fn: () => Promise<T>): Load<T> {
  const [state, setState] = useState<Load<T>>({ status: "loading" });
  useEffect(() => {
    let cancelled = false;
    fn()
      .then((data) => !cancelled && setState({ status: "ok", data }))
      .catch((e: Error) => !cancelled && setState({ status: "error", message: e.message }));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return state;
}

function HealthPanel() {
  const health = useLoad<Health>(api.health);
  return (
    <section className="rounded-lg border border-black/10 p-5 dark:border-white/15">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide opacity-70">System</h2>
      {health.status === "loading" && <p className="text-sm opacity-70">Checking…</p>}
      {health.status === "error" && (
        <p className="text-sm text-red-600">
          API unreachable at {API_URL}. Is <code>uvicorn</code> running?
        </p>
      )}
      {health.status === "ok" && (
        <ul className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-5">
          {Object.entries(health.data.checks).map(([name, ok]) => (
            <li key={name} className="flex items-center gap-2">
              <span
                aria-hidden
                className={`h-2 w-2 rounded-full ${ok ? "bg-green-500" : "bg-red-500"}`}
              />
              <span>{name.replace("_", " ")}</span>
              <span className="sr-only">{ok ? "up" : "down"}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function IdeasPanel() {
  const ideas = useLoad<Idea[]>(api.listIdeas);
  return (
    <section className="rounded-lg border border-black/10 p-5 dark:border-white/15">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide opacity-70">My ideas</h2>
      {ideas.status === "loading" && <p className="text-sm opacity-70">Loading…</p>}
      {ideas.status === "error" && <p className="text-sm text-red-600">{ideas.message}</p>}
      {ideas.status === "ok" && ideas.data.length === 0 && (
        <p className="text-sm opacity-70">No ideas yet. Idea intake arrives in Phase 1A.</p>
      )}
      {ideas.status === "ok" && ideas.data.length > 0 && (
        <table className="w-full text-left text-sm">
          <thead className="opacity-70">
            <tr>
              <th className="py-2 font-medium">Idea</th>
              <th className="py-2 font-medium">Market</th>
              <th className="py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {ideas.data.map((idea) => (
              <tr key={idea.id} className="border-t border-black/5 dark:border-white/10">
                <td className="py-2">{idea.title}</td>
                <td className="py-2">{idea.target_market}</td>
                <td className="py-2">{STATE_LABELS[idea.state]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

export default function Dashboard() {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-4 py-10">
      <header>
        <h1 className="text-2xl font-semibold">Preuve</h1>
        <p className="text-sm opacity-70">Evidence before you build.</p>
      </header>
      <HealthPanel />
      <IdeasPanel />
    </main>
  );
}
