"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AuthCard, FormError } from "@/components/shell/AuthCard";
import { useSession } from "@/components/shell/SessionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";

/** First run: create the owner account. Existing cases are kept and moved into it. */
export default function SetupPage() {
  const router = useRouter();
  const { refresh } = useSession();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.authStatus().then(
      (s) => {
        if (!s.needs_setup) router.replace("/login");
      },
      () => setError("Can't reach the Preuve API. Is it running?"),
    );
  }, [router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.setup({ name, email, password });
      await refresh();
      router.replace("/");
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <AuthCard
      eyebrow="First run"
      title="Set up Preuve"
      kicker="Create the owner account. Any cases already here move into your workspace."
    >
      <form onSubmit={submit} className="space-y-4">
        <FormError message={error} />
        <div className="space-y-1.5">
          <Label htmlFor="name">Your name</Label>
          <Input id="name" autoComplete="name" required maxLength={200} value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={10}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">At least 10 characters. A few random words work well.</p>
        </div>
        <Button type="submit" className="w-full" disabled={busy}>
          {busy ? "Setting up…" : "Create owner account"}
        </Button>
      </form>
    </AuthCard>
  );
}
