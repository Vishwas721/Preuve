import type { ValidationState } from "@/lib/api";

/** PRD §25 validation states, as shown on folder tabs. */
export const STATE_LABELS: Record<ValidationState, string> = {
  unvalidated: "Unvalidated",
  researching: "Researching",
  early_signal: "Early signal",
  problem_validated: "Problem validated",
  solution_validation: "Solution validation",
  commercial_validation: "Commercial validation",
  mvp_ready: "MVP ready",
};
