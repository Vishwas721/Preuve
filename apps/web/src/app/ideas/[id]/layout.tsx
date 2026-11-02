"use client";

import { useParams } from "next/navigation";
import type { ReactNode } from "react";

import { DossierFrame } from "@/components/dossier/DossierFrame";
import { DossierProvider } from "@/components/dossier/DossierProvider";

/** Every section of a case shares one data load, the header, folder tabs and the case rail. */
export default function CaseLayout({ children }: { children: ReactNode }) {
  const { id } = useParams<{ id: string }>();
  return (
    <DossierProvider id={id}>
      <DossierFrame>{children}</DossierFrame>
    </DossierProvider>
  );
}
