"use client";

import { FilePlus2, FolderOpen, Layers, Moon, Scale, Search, Sun, Users } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";
import { api, type PortfolioItem } from "@/lib/api";

const SECTIONS = [
  { slug: "", label: "Overview", icon: FolderOpen },
  { slug: "/evidence", label: "Evidence", icon: Scale },
  { slug: "/landscape", label: "Landscape", icon: Layers },
  { slug: "/prospects", label: "Prospects", icon: Users },
];

/** ⌘K / Ctrl+K: jump to any case, any section of the open case, or run an action. */
export function CommandMenu({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const router = useRouter();
  const params = useParams<{ id?: string }>();
  const { resolvedTheme, setTheme } = useTheme();
  const [cases, setCases] = useState<PortfolioItem[]>([]);

  useEffect(() => {
    if (open) api.portfolio().then(setCases, () => setCases([]));
  }, [open]);

  function go(href: string) {
    onOpenChange(false);
    router.push(href);
  }

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Search Preuve"
      description="Jump to a case, a section, or an action"
    >
      <Command>
        <CommandInput placeholder="Search cases and sections…" />
        <CommandList>
          <CommandEmpty>Nothing matches.</CommandEmpty>
          {params.id && (
            <>
              <CommandGroup heading="This case">
                {SECTIONS.map(({ slug, label, icon: Icon }) => (
                  <CommandItem key={label} onSelect={() => go(`/ideas/${params.id}${slug}`)}>
                    <Icon /> {label}
                  </CommandItem>
                ))}
              </CommandGroup>
              <CommandSeparator />
            </>
          )}
          <CommandGroup heading="Cases">
            {cases.map((c) => (
              <CommandItem
                key={c.id}
                value={`${c.title} ${c.target_market}`}
                onSelect={() => go(`/ideas/${c.id}`)}
              >
                <Search />
                <span className="truncate">{c.title}</span>
                <CommandShortcut>{c.target_market}</CommandShortcut>
              </CommandItem>
            ))}
          </CommandGroup>
          <CommandSeparator />
          <CommandGroup heading="Actions">
            <CommandItem onSelect={() => go("/ideas/new")}>
              <FilePlus2 /> Open a new case
            </CommandItem>
            <CommandItem
              onSelect={() => {
                setTheme(resolvedTheme === "dark" ? "light" : "dark");
                onOpenChange(false);
              }}
            >
              {resolvedTheme === "dark" ? <Sun /> : <Moon />} Switch to{" "}
              {resolvedTheme === "dark" ? "paper" : "ink"} theme
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>
    </CommandDialog>
  );
}
