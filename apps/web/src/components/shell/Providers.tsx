"use client";

import { ThemeProvider } from "next-themes";
import type { ReactNode } from "react";

import { SessionProvider } from "@/components/shell/SessionProvider";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <TooltipProvider delayDuration={150}>
        <SessionProvider>{children}</SessionProvider>
        <Toaster position="bottom-right" />
      </TooltipProvider>
    </ThemeProvider>
  );
}
