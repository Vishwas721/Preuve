"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AuthCard, FormError } from "@/components/shell/AuthCard";
import { useSession } from "@/components/shell/SessionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, type InvitationPublic } from "@/lib/api";

/** Opening an invitation link: sign up with the invited email, or accept while signed in. */
export default function InvitePage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const { me, refresh } = useSession();
  const [inv, setInv] = useState<InvitationPublic | null>(null);
  const [invalid, setInvalid] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.getInvitation(token).then(setInv, (e: Error) => setInvalid(e.message));
  }, [token]);

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await refresh();
      router.replace("/");
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  if (invalid) {
    return (
      <AuthCard eyebrow="Invitation" title="This link doesn't work" kicker={invalid}>
        <Button asChild variant="outline">
          <Link href="/login">Sign in</Link>
        </Button>
      </AuthCard>
    );
  }
  if (!inv) return <AuthCard eyebrow="Invitation" title="Opening…">{null}</AuthCard>;

  const kicker = `You're invited to “${inv.workspace_name}” as ${inv.role === "owner" ? "an owner" : "a member"}.`;
  const here = `/invite/${token}`;

  if (me) {
    const same = me.user.email === inv.email;
    return (
      <AuthCard eyebrow="Invitation" title="Join the workspace" kicker={kicker}>
        <div className="space-y-4">
          <FormError message={error} />
          {same ? (
            <Button className="w-full" disabled={busy} onClick={() => run(() => api.acceptInvitation(token))}>
              Join as {me.user.email}
            </Button>
          ) : (
            <p className="text-sm">
              This invitation is for <strong>{inv.email}</strong>, but you&apos;re signed in as {me.user.email}. Sign out
              and open the link again.
            </p>
          )}
        </div>
      </AuthCard>
    );
  }

  if (inv.account_exists) {
    return (
      <AuthCard eyebrow="Invitation" title="Sign in to join" kicker={kicker}>
        <p className="mb-4 text-sm">
          There&apos;s already an account for <strong>{inv.email}</strong>. Sign in, then this page lets you join.
        </p>
        <Button asChild className="w-full">
          <Link href={`/login?next=${encodeURIComponent(here)}`}>Sign in</Link>
        </Button>
      </AuthCard>
    );
  }

  return (
    <AuthCard eyebrow="Invitation" title="Create your account" kicker={kicker}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          void run(() => api.signupWithInvitation(token, { name, password }));
        }}
      >
        <FormError message={error} />
        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input id="email" value={inv.email} readOnly disabled />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="name">Your name</Label>
          <Input id="name" autoComplete="name" required maxLength={200} value={name} onChange={(e) => setName(e.target.value)} />
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
          <p className="text-xs text-muted-foreground">At least 10 characters.</p>
        </div>
        <Button type="submit" className="w-full" disabled={busy}>
          {busy ? "Creating…" : "Create account and join"}
        </Button>
      </form>
    </AuthCard>
  );
}
