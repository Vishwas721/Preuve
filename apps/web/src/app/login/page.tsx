"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { AuthCard, FormError } from "@/components/shell/AuthCard";
import { useSession } from "@/components/shell/SessionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";

/** Only same-site paths, so a crafted ?next= can't send people elsewhere. */
function safeNext(next: string | null): string {
  // "//host" and "/\host" are protocol-relative to browsers; only plain paths are allowed.
  return next && /^\/(?![/\\])/.test(next) ? next : "/";
}

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { refresh } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.authStatus().then(
      (s) => {
        if (s.needs_setup) router.replace("/setup");
        else if (s.signed_in) router.replace(safeNext(params.get("next")));
      },
      () => setError("Can't reach the Preuve API. Is it running?"),
    );
  }, [router, params]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.login({ email, password });
      await refresh();
      router.replace(safeNext(params.get("next")));
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <AuthCard eyebrow="Preuve" title="Sign in" kicker="Evidence before you build.">
      <form onSubmit={submit} className="space-y-4">
        <FormError message={error} />
        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <Button type="submit" className="w-full" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </Button>
        <p className="text-xs text-muted-foreground">
          New here? Ask a workspace owner for an invitation link. Forgot your password? The instance owner can
          reset it.
        </p>
      </form>
    </AuthCard>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
