"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { api, type IdeaInput } from "@/lib/api";

const OPTIONAL_FIELDS: { key: keyof IdeaInput; label: string; placeholder: string }[] = [
  { key: "industry", label: "Industry", placeholder: "Construction" },
  { key: "customer_type", label: "Customer type", placeholder: "Mid-size general contractors" },
  { key: "business_model", label: "Business model", placeholder: "B2B SaaS subscription" },
  { key: "known_competitors", label: "Known competitors", placeholder: "Procore, spreadsheets…" },
  { key: "assumptions", label: "Your assumptions", placeholder: "PMs would pay to save time…" },
];

const input =
  "w-full rounded-md border border-black/15 bg-transparent px-3 py-2 text-sm outline-none focus:border-black/40 dark:border-white/20 dark:focus:border-white/50";

export default function NewIdeaPage() {
  const router = useRouter();
  const [form, setForm] = useState<IdeaInput>({
    title: "",
    description: "",
    target_market: "United States",
  });
  const [analyze, setAnalyze] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = (key: keyof IdeaInput) => (value: string) =>
    setForm((f) => ({ ...f, [key]: value }));

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      // Send optional fields only when filled in.
      const payload = Object.fromEntries(
        Object.entries(form).map(([k, v]) => [k, typeof v === "string" && v.trim() === "" ? null : v]),
      ) as IdeaInput;
      const idea = await api.createIdea(payload);
      if (analyze) await api.analyze(idea.id);
      router.push(`/ideas/${idea.id}`);
    } catch (err) {
      setError((err as Error).message);
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-10">
      <header>
        <Link href="/" className="text-sm opacity-70 hover:opacity-100">
          ← Ideas
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">New idea</h1>
        <p className="text-sm opacity-70">
          Describe it in your own words. Preuve turns it into testable assumptions, not conclusions.
        </p>
      </header>

      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">Name</span>
          <input
            required
            maxLength={200}
            className={input}
            value={form.title}
            onChange={(e) => set("title")(e.target.value)}
            placeholder="Construction progress automation"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">What are you thinking of building?</span>
          <textarea
            required
            rows={4}
            className={input}
            value={form.description}
            onChange={(e) => set("description")(e.target.value)}
            placeholder="AI tool that automates construction progress reports."
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">Target market</span>
          <input
            required
            maxLength={100}
            className={input}
            value={form.target_market}
            onChange={(e) => set("target_market")(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">Why do you think this matters?</span>
          <textarea
            rows={2}
            className={input}
            value={form.why_it_matters ?? ""}
            onChange={(e) => set("why_it_matters")(e.target.value)}
            placeholder="Project managers spend too much time creating reports."
          />
        </label>

        <details className="rounded-md border border-black/10 p-3 dark:border-white/15">
          <summary className="cursor-pointer text-sm font-medium">Optional context</summary>
          <div className="mt-3 flex flex-col gap-3">
            {OPTIONAL_FIELDS.map(({ key, label, placeholder }) => (
              <label key={key} className="flex flex-col gap-1">
                <span className="text-sm">{label}</span>
                <input
                  className={input}
                  value={(form[key] as string | null | undefined) ?? ""}
                  onChange={(e) => set(key)(e.target.value)}
                  placeholder={placeholder}
                />
              </label>
            ))}
          </div>
        </details>

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={analyze} onChange={(e) => setAnalyze(e.target.checked)} />
          Analyze right away (hypothesis, unknowns, candidate ICPs)
        </label>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="self-start rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background disabled:opacity-50"
        >
          {submitting ? "Creating…" : "Create idea"}
        </button>
      </form>
    </main>
  );
}
