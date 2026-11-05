"use client";

import { HypothesisSection } from "@/components/overview/HypothesisSection";
import { ProfilesSection } from "@/components/overview/ProfilesSection";
import { QuestionsSection } from "@/components/overview/QuestionsSection";
import { ResearchScoreSection } from "@/components/overview/ResearchScoreSection";

/** Case overview: the hypothesis, the open questions, who to sell to and the research score. */
export default function CaseOverview() {
  return (
    <div className="space-y-14">
      <HypothesisSection />
      <QuestionsSection />
      <ProfilesSection />
      <ResearchScoreSection />
    </div>
  );
}
