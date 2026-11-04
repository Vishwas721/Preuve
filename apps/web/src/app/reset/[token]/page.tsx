"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AuthCard, FormError } from "@/components/shell/AuthCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";

/** A one-time password-reset link from the instance owner (Phase 5C). */
export default function ResetPage() {
  const { token } = useParams<{ token: string }>();
  const [email, setEmail] = useState<string | null>(null);
  const [invalid, setInvalid] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.resetInfo(token).then(
      (r) => setEmail(r.email),
      (e: Error) => setInvalid(e.message),
    );
  }, [token]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.useResetLink(token, password);
      setDone(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (invalid) {
    return (
      <AuthCard eyebrow="Password reset" title="This link doesn't work" kicker={invalid}>
        <p className="text-sm text-muted-foreground">Ask the person who runs this Preuve for a new link.</p>
      </AuthCard>
    );
  }
  if (done) {
    return (
      <AuthCard eyebrow="Password reset" title="Password changed" kicker="You were signed out everywhere.">
        <Button asChild className="w-full">
          <Link href="/login">Sign in</Link>
        </Button>
      </AuthCard>
    );
  }
  return (
    <AuthCard eyebrow="Password reset" title="Choose a new password" kicker={email ? `For ${email}.` : "Checking the link…"}>
      <form onSubmit={submit} className="space-y-4">
        <FormError message={error} />
        <div className="space-y-1.5">
          <Label htmlFor="password">New password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={10}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">At least 10 characters.</p>
        </div>
        <Button type="submit" className="w-full" disabled={busy || !email}>
          {busy ? "Saving…" : "Set password"}
        </Button>
      </form>
    </AuthCard>
  );
}
