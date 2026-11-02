"use client";

import { Monitor, Moon, Search, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { CommandMenu } from "@/components/shell/CommandMenu";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { api, type Health } from "@/lib/api";
import { cn } from "@/lib/utils";

function HealthDot() {
  const [health, setHealth] = useState<Health | "down" | null>(null);
  useEffect(() => {
    let alive = true;
    const check = () =>
      api.health().then(
        (h) => alive && setHealth(h),
        () => alive && setHealth("down"),
      );
    check();
    const t = setInterval(check, 30_000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  const ok = health !== null && health !== "down" && health.status === "ok";
  const label =
    health === null ? "Checking services…" : health === "down" ? "API unreachable" : ok ? "All core services up" : "Degraded";
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="flex items-center gap-1.5 rounded-full px-2 py-1 text-xs text-muted-foreground" aria-label={label}>
          <span
            aria-hidden
            className={cn(
              "size-1.5 rounded-full",
              health === null ? "bg-muted-foreground/40" : ok ? "bg-status-good" : "bg-status-critical animate-pulse",
            )}
          />
          <span className="hidden font-mono sm:inline">{ok ? "live" : health === null ? "…" : "check"}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent className="font-mono text-xs">
        <p className="mb-1 font-sans">{label}</p>
        {health && health !== "down" &&
          Object.entries(health.checks).map(([k, v]) => (
            <p key={k}>
              {v ? "●" : "○"} {k.replace("_", " ")}
            </p>
          ))}
      </TooltipContent>
    </Tooltip>
  );
}

function ThemeMenu() {
  const { theme, setTheme } = useTheme();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Theme">
          <Sun className="dark:hidden" />
          <Moon className="hidden dark:block" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuRadioGroup value={theme} onValueChange={setTheme}>
          <DropdownMenuRadioItem value="light">
            <Sun /> Paper
          </DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="dark">
            <Moon /> Ink
          </DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="system">
            <Monitor /> System
          </DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function TopBar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const nav = [
    { href: "/", label: "Case board", active: pathname === "/" },
    { href: "/ideas/new", label: "New case", active: pathname === "/ideas/new" },
  ];

  return (
    <header className="sticky top-0 z-40 border-b rule bg-background/80 backdrop-blur-md supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex h-14 w-full max-w-7xl items-center gap-4 px-4 sm:px-6">
        <Link href="/" className="group flex items-baseline gap-2" aria-label="Preuve, case board">
          <span className="font-display text-2xl leading-none tracking-tight">Preuve</span>
          <span className="eyebrow hidden translate-y-[-2px] md:inline">evidence before you build</span>
        </Link>

        <nav className="ml-2 hidden items-center gap-1 sm:flex" aria-label="Main">
          {nav.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              aria-current={n.active ? "page" : undefined}
              className={cn(
                "rounded-md px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground",
                n.active && "text-foreground underline decoration-1 underline-offset-[6px]",
              )}
            >
              {n.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-1">
          <Button
            variant="outline"
            className="hidden h-8 w-56 justify-start gap-2 bg-paper/60 text-muted-foreground md:flex"
            onClick={() => setOpen(true)}
          >
            <Search className="size-3.5" />
            <span className="text-sm">Search cases…</span>
            <kbd className="ml-auto rounded border bg-background px-1.5 font-mono text-[10px]">⌘K</kbd>
          </Button>
          <Button variant="ghost" size="icon" className="md:hidden" aria-label="Search" onClick={() => setOpen(true)}>
            <Search />
          </Button>
          <HealthDot />
          <ThemeMenu />
        </div>
      </div>
      <CommandMenu open={open} onOpenChange={setOpen} />
    </header>
  );
}
