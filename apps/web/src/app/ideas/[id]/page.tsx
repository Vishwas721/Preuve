"use client";

import { HypothesisSection } from "@/components/overview/HypothesisSection";
import { ProfilesSection } from "@/components/overview/ProfilesSection";
import { QuestionsSection } from "@/components/overview/QuestionsSection";

/** Case overview: the hypothesis, the open questions and who to sell to. */
export default function CaseOverview() {
  return (
    <div className="space-y-14">
      <HypothesisSection />
      <QuestionsSection />
      <ProfilesSection />
    </div>
  );
}
