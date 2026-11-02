"use client";

import { ArrowRight, ChevronDown } from "lucide-react";
import { motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, type IdeaInput } from "@/lib/api";
import { cn } from "@/lib/utils";

const OPTIONAL: { key: keyof IdeaInput; label: string; placeholder: string }[] = [
  { key: "industry", label: "Industry", placeholder: "Construction" },
  { key: "customer_type", label: "Customer type", placeholder: "Mid-size general contractors" },
  { key: "business_model", label: "Business model", placeholder: "B2B SaaS subscription" },
  { key: "known_competitors", label: "Known competitors", placeholder: "Procore, spreadsheets…" },
  { key: "assumptions", label: "Your assumptions", placeholder: "PMs would pay to save time…" },
];

const MARKETS = ["United States", "United Kingdom", "European Union", "Canada", "Australia", "India", "Global"];

function Step({ n, title, children }: { n: string; title: string; children: ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Number(n) * 0.08, duration: 0.4 }}
      className="grid gap-3 sm:grid-cols-[4rem_1fr]"
    >
      <span className="eyebrow pt-2">{n}</span>
      <div className="space-y-2">
        <p className="text-sm font-medium">{title}</p>
        {children}
      </div>
    </motion.div>
  );
}

export default function NewCase() {
  const router = useRouter();
  const [form, setForm] = useState<IdeaInput>({ title: "", description: "", target_market: "United States" });
  const [more, setMore] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const set = (k: keyof IdeaInput) => (v: string) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const payload = Object.fromEntries(
        Object.entries(form).map(([k, v]) => [k, typeof v === "string" && v.trim() === "" ? null : v]),
      ) as IdeaInput;
      const idea = await api.createIdea(payload);
      await api.analyze(idea.id);
      toast.success("Case opened", { description: "Analysis is running — the hypothesis appears in a minute." });
      router.push(`/ideas/${idea.id}`);
    } catch (err) {
      toast.error((err as Error).message);
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-3xl px-4 pt-12 pb-24 sm:px-6 sm:pt-16">
      <motion.header initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mb-10">
        <p className="eyebrow mb-3">New case · intake</p>
        <h1 className="font-display text-5xl leading-[0.95] tracking-tight sm:text-6xl">
          What are you thinking of <span className="italic">building?</span>
        </h1>
        <p className="mt-4 max-w-xl text-muted-foreground">
          Write it the way you&apos;d explain it to a friend. Preuve turns it into testable assumptions —
          then evidence, not enthusiasm, decides.
        </p>
      </motion.header>

      <form onSubmit={submit} className="sheet space-y-8 p-6 sm:p-8">
        <Step n="01" title="The idea">
          <label htmlFor="idea" className="sr-only">
            What are you thinking of building?
          </label>
          <textarea
            id="idea"
            required
            rows={4}
            value={form.description}
            onChange={(e) => set("description")(e.target.value)}
            placeholder="An AI system that helps construction companies automate progress reports…"
            className={cn(
              "w-full resize-none bg-transparent font-display text-2xl leading-[2.25rem] outline-none placeholder:text-muted-foreground/60",
              // ruled lines like a legal pad
              "bg-[linear-gradient(transparent_calc(2.25rem-1px),var(--rule)_calc(2.25rem-1px))] bg-[length:100%_2.25rem]",
            )}
          />
        </Step>

        <Step n="02" title="Give the case a name">
          <Input
            required
            maxLength={200}
            aria-label="Case name"
            value={form.title}
            onChange={(e) => set("title")(e.target.value)}
            placeholder="Construction progress automation"
            className="h-10 text-base"
          />
        </Step>

        <Step n="03" title="Where will you sell it?">
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Target market">
            {MARKETS.map((m) => (
              <button
                key={m}
                type="button"
                role="radio"
                aria-checked={form.target_market === m}
                onClick={() => set("target_market")(m)}
                className={cn(
                  "rounded-full border px-3 py-1 text-sm transition-colors",
                  form.target_market === m
                    ? "border-foreground bg-foreground text-background"
                    : "hover:border-foreground/40",
                )}
              >
                {m}
              </button>
            ))}
          </div>
        </Step>

        <Step n="04" title="Why do you think it matters? (optional)">
          <Input
            aria-label="Why it matters"
            value={form.why_it_matters ?? ""}
            onChange={(e) => set("why_it_matters")(e.target.value)}
            placeholder="Project managers spend too much time creating weekly reports."
            className="h-10"
          />
        </Step>

        <div className="sm:pl-[4.75rem]">
          <button
            type="button"
            onClick={() => setMore((m) => !m)}
            aria-expanded={more}
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ChevronDown className={cn("size-4 transition-transform", more && "rotate-180")} /> Add context you already have
          </button>
          {more && (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className="mt-4 grid gap-4 sm:grid-cols-2">
              {OPTIONAL.map(({ key, label, placeholder }) => (
                <div key={key} className="space-y-1.5">
                  <Label htmlFor={`o-${key}`}>{label}</Label>
                  <Input
                    id={`o-${key}`}
                    value={(form[key] as string | null | undefined) ?? ""}
                    onChange={(e) => set(key)(e.target.value)}
                    placeholder={placeholder}
                  />
                </div>
              ))}
            </motion.div>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4 border-t rule pt-6">
          <p className="max-w-sm text-xs text-muted-foreground">
            Opening the case starts the analysis: a hypothesis, open questions and customer profiles — all
            labelled as assumptions.
          </p>
          <Button type="submit" size="lg" className="h-11 px-5" disabled={submitting}>
            {submitting ? "Opening…" : "Open the case"} <ArrowRight />
          </Button>
        </div>
      </form>
    </main>
  );
}
